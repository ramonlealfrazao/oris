"""Rotas de autenticação"""

import secrets
import time

from flask import Blueprint, abort, current_app, flash, redirect, render_template, request, session, url_for

from app.extensions import db
from app.forms import LoginForm, MfaCodigoForm
from app.services import mfa_service
from app.models import OrigemDiretorio, Usuario
from app.services.auditoria_service import registrar_auditoria
from app.services.diretorio_service import DiretorioConfigError, UsuarioExterno, provisionar_usuario_externo
from app.services.oidc_service import OidcError, concluir_autorizacao, iniciar_autorizacao, oidc_habilitado
from app.utils.decorators import usuario_atual
from app.utils.rate_limit import bloqueado, limpar_tentativas, registrar_tentativa_falha
from app.utils.security import verificar_senha

auth_bp = Blueprint("auth", __name__)

MENSAGEM_LOGIN_INVALIDO = "Email ou senha inválidos."
MENSAGEM_MUITAS_TENTATIVAS = (
    "Muitas tentativas de login para esta conta. Aguarde alguns minutos e tente novamente."
)


@auth_bp.route("/login", methods=["GET", "POST"])
def login():
    if session.get("autenticado") and session.get("usuario_id"):
        return redirect(url_for("main.index"))

    form = LoginForm()

    if form.validate_on_submit():
        email = form.email.data.strip().lower()
        senha = form.senha.data
        ip = request.remote_addr
        rate_limit_ativo = current_app.config.get("RATE_LIMIT_LOGIN_ENABLED", True)

        if rate_limit_ativo and bloqueado(ip, email):
            registrar_auditoria(
                usuario=None, acao="LOGIN_BLOQUEADO", resultado="FALHA",
                identificador_tentado=email,
                descricao="Tentativa bloqueada por excesso de tentativas de login.",
            )
            db.session.commit()
            flash(MENSAGEM_MUITAS_TENTATIVAS, "danger")
            return render_template("login.html", form=form)

        usuario = Usuario.query.filter_by(email=email).first()

        # Mensagem sempre genérica: usuário inexistente, senha errada
        # ou usuário inativo resultam na mesma resposta ao usuário.
        # Contas provisionadas por LDAP/OIDC nunca autenticam com senha
        # local: a autenticação é sempre no diretório.
        login_valido = (
            usuario is not None
            and usuario.ativo
            and usuario.origem == OrigemDiretorio.LOCAL
            and verificar_senha(senha, usuario.senha_hash)
        )

        if login_valido:
            if rate_limit_ativo:
                limpar_tentativas(ip, email)

            if mfa_service.mfa_obrigatorio():
                # Senha correta NÃO abre a sessão: só libera a segunda etapa (MFA),
                # por poucos minutos. A sessão nasce em _abrir_sessao_local().
                session.clear()
                session[CHAVE_MFA_PENDENTE] = {"usuario_id": usuario.id, "desde": time.time()}
                registrar_auditoria(
                    usuario=usuario, acao="LOGIN_PRIMEIRO_FATOR",
                    descricao="Primeiro fator correto; aguardando o segundo fator (MFA).",
                )
                db.session.commit()
                destino = "auth.login_mfa" if usuario.mfa_ativo else "auth.login_mfa_cadastrar"
                return redirect(url_for(destino))

            _abrir_sessao_local(usuario, "Login local (MFA desligado pela configuração).")
            db.session.commit()

            return redirect(url_for("main.index"))

        if rate_limit_ativo:
            registrar_tentativa_falha(ip, email)

        # O motivo real fica so na trilha de auditoria; ao usuario a mensagem e sempre
        # generica. A senha digitada NUNCA e gravada.
        if usuario is None:
            motivo = "usuário inexistente"
        elif not usuario.ativo:
            motivo = "usuário inativo"
        elif usuario.origem != OrigemDiretorio.LOCAL:
            motivo = "conta de diretório (LDAP/OIDC) não autentica com senha local"
        else:
            motivo = "senha incorreta"
        registrar_auditoria(
            usuario=usuario, acao="LOGIN_FALHA", resultado="FALHA",
            identificador_tentado=email, descricao=f"Falha de login: {motivo}.",
        )
        db.session.commit()
        flash(MENSAGEM_LOGIN_INVALIDO, "danger")

    return render_template("login.html", form=form)


# --------------------------------------------------------------------------
# MFA (TOTP) - segunda etapa do login local
# --------------------------------------------------------------------------
CHAVE_MFA_PENDENTE = "mfa_pendente"
MFA_VALIDADE_SEGUNDOS = 5 * 60
MENSAGEM_MFA_EXPIRADO = "Sua etapa de verificação expirou. Entre novamente com e-mail e senha."
MENSAGEM_MFA_INVALIDO = "Código inválido ou já utilizado."
MENSAGEM_MFA_BLOQUEADO = "Muitas tentativas de código. Aguarde alguns minutos e entre novamente."


def _abrir_sessao_local(usuario, descricao):
    session.clear()
    session["usuario_id"] = usuario.id
    session["autenticado"] = True
    session.permanent = True
    registrar_auditoria(usuario=usuario, acao="LOGIN", descricao=descricao)


def _usuario_mfa_pendente():
    """Usuário que já acertou a senha e está na segunda etapa, ou None (expirou/inválido)."""
    pendente = session.get(CHAVE_MFA_PENDENTE)
    if not isinstance(pendente, dict):
        return None
    if time.time() - float(pendente.get("desde", 0)) > MFA_VALIDADE_SEGUNDOS:
        session.pop(CHAVE_MFA_PENDENTE, None)
        return None
    usuario = db.session.get(Usuario, pendente.get("usuario_id"))
    if usuario is None or not usuario.ativo or usuario.origem != OrigemDiretorio.LOCAL:
        session.pop(CHAVE_MFA_PENDENTE, None)
        return None
    return usuario


def _chave_rate_limit_mfa(usuario):
    # Por usuário (e não por IP): trocar de IP não dá novas tentativas de adivinhar o código.
    return ("mfa", f"usuario:{usuario.id}")


def _mfa_bloqueado(usuario):
    if not current_app.config.get("RATE_LIMIT_LOGIN_ENABLED", True):
        return False
    if not bloqueado(*_chave_rate_limit_mfa(usuario)):
        return False
    registrar_auditoria(
        usuario=usuario, acao="MFA_BLOQUEADO", resultado="FALHA",
        descricao="Segunda etapa bloqueada por excesso de códigos errados.",
    )
    session.pop(CHAVE_MFA_PENDENTE, None)
    db.session.commit()
    flash(MENSAGEM_MFA_BLOQUEADO, "danger")
    return True


def _registrar_falha_mfa(usuario, etapa):
    if current_app.config.get("RATE_LIMIT_LOGIN_ENABLED", True):
        registrar_tentativa_falha(*_chave_rate_limit_mfa(usuario))
    registrar_auditoria(
        usuario=usuario, acao="MFA_FALHA", resultado="FALHA",
        descricao=f"Código MFA inválido ({etapa}).",
    )
    db.session.commit()
    flash(MENSAGEM_MFA_INVALIDO, "danger")


@auth_bp.route("/login/mfa", methods=["GET", "POST"])
def login_mfa():
    usuario = _usuario_mfa_pendente()
    if usuario is None:
        flash(MENSAGEM_MFA_EXPIRADO, "warning")
        return redirect(url_for("auth.login"))
    if not usuario.mfa_ativo:
        return redirect(url_for("auth.login_mfa_cadastrar"))

    form = MfaCodigoForm()
    if form.validate_on_submit():
        if _mfa_bloqueado(usuario):
            return redirect(url_for("auth.login"))
        codigo = form.codigo.data
        if mfa_service.parece_codigo_totp(codigo):
            valido, metodo = mfa_service.verificar_totp(usuario, codigo), "aplicativo autenticador"
        else:
            valido, metodo = mfa_service.usar_codigo_recuperacao(usuario, codigo), "código de recuperação"
        if valido:
            if current_app.config.get("RATE_LIMIT_LOGIN_ENABLED", True):
                limpar_tentativas(*_chave_rate_limit_mfa(usuario))
            restantes = mfa_service.codigos_restantes(usuario)
            descricao = f"Login local + MFA ({metodo})."
            if metodo == "código de recuperação":
                descricao += f" Restam {restantes} código(s) de recuperação."
            _abrir_sessao_local(usuario, descricao)
            db.session.commit()
            if metodo == "código de recuperação" and restantes <= 2:
                flash(
                    f"Você usou um código de recuperação e restam {restantes}. "
                    "Peça a um administrador para redefinir o seu MFA.",
                    "warning",
                )
            return redirect(url_for("main.index"))
        _registrar_falha_mfa(usuario, "login")

    return render_template("login_mfa.html", form=form, usuario=usuario)


@auth_bp.route("/login/mfa/cadastrar", methods=["GET", "POST"])
def login_mfa_cadastrar():
    usuario = _usuario_mfa_pendente()
    if usuario is None:
        flash(MENSAGEM_MFA_EXPIRADO, "warning")
        return redirect(url_for("auth.login"))
    if usuario.mfa_ativo:
        return redirect(url_for("auth.login_mfa"))

    segredo = mfa_service.preparar_cadastro(usuario)
    db.session.commit()

    form = MfaCodigoForm()
    if form.validate_on_submit():
        if _mfa_bloqueado(usuario):
            return redirect(url_for("auth.login"))
        if mfa_service.verificar_totp(usuario, form.codigo.data):
            codigos = mfa_service.ativar(usuario)
            registrar_auditoria(
                usuario=usuario, acao="MFA_ATIVADO", tabela="usuarios", registro_id=usuario.id,
                descricao="Autenticação em dois fatores (TOTP) cadastrada pelo próprio usuário.",
            )
            _abrir_sessao_local(usuario, "Login local + MFA (cadastro do aplicativo autenticador).")
            db.session.commit()
            return render_template("login_mfa_codigos.html", codigos=codigos)
        _registrar_falha_mfa(usuario, "cadastro")

    uri = mfa_service.uri_provisionamento(usuario, segredo)
    return render_template(
        "login_mfa_cadastrar.html",
        form=form,
        usuario=usuario,
        qr_svg=mfa_service.qr_code_svg(uri),
        segredo_formatado=mfa_service.formatar_segredo(segredo),
    )


MENSAGEM_SSO_NEGADO = "Não foi possível entrar com o login institucional. Procure um administrador."


def _uri_callback_oidc():
    return url_for("auth.login_oidc_callback", _external=True)


@auth_bp.route("/login/oidc")
def login_oidc():
    if not oidc_habilitado():
        abort(404)
    try:
        url, estado = iniciar_autorizacao(_uri_callback_oidc())
    except Exception:
        current_app.logger.exception("Falha ao iniciar o login OIDC")
        flash(MENSAGEM_SSO_NEGADO, "danger")
        return redirect(url_for("auth.login"))
    session["oidc_estado"] = estado
    return redirect(url)


@auth_bp.route("/login/oidc/callback")
def login_oidc_callback():
    if not oidc_habilitado():
        abort(404)

    estado = session.pop("oidc_estado", None)
    state_recebido = request.args.get("state", "")
    codigo = request.args.get("code", "")
    if (
        not estado
        or not codigo
        or not secrets.compare_digest(state_recebido.encode("utf-8"), estado["state"].encode("utf-8"))
    ):
        flash(MENSAGEM_SSO_NEGADO, "danger")
        return redirect(url_for("auth.login"))

    try:
        externo = concluir_autorizacao(codigo, estado, _uri_callback_oidc())
        if externo.uid_ldap:
            # Pessoa do LDAP (federado no Keycloak): é a MESMA conta que a
            # `flask sincronizar-ldap` cria (origem LDAP, identificador = uid).
            # Sem isso, quem já foi sincronizado era recusado por "e-mail já em uso".
            externo = UsuarioExterno(
                identificador=externo.uid_ldap, nome=externo.nome,
                email=externo.email, grupos=externo.grupos,
            )
            origem_login = OrigemDiretorio.LDAP
        else:
            origem_login = OrigemDiretorio.OIDC
        usuario = provisionar_usuario_externo(externo, origem_login)
    except (OidcError, DiretorioConfigError, OSError, ValueError, KeyError):
        current_app.logger.exception("Falha no callback OIDC")
        db.session.rollback()
        registrar_auditoria(
            usuario=None, acao="LOGIN_FALHA", resultado="FALHA",
            descricao="Falha de login via OIDC (token inválido, expirado ou provisionamento recusado).",
        )
        db.session.commit()
        flash(MENSAGEM_SSO_NEGADO, "danger")
        return redirect(url_for("auth.login"))

    if usuario is None:
        registrar_auditoria(
            usuario=None, acao="LOGIN_FALHA", resultado="FALHA",
            descricao="Login via OIDC negado: usuário sem perfil mapeado ou inativo.",
        )
        db.session.commit()
        flash(MENSAGEM_SSO_NEGADO, "danger")
        return redirect(url_for("auth.login"))

    session.clear()
    session["usuario_id"] = usuario.id
    session["autenticado"] = True
    session.permanent = True
    registrar_auditoria(
        usuario=usuario, acao="LOGIN",
        descricao="Login via OIDC (conta do LDAP)." if origem_login == OrigemDiretorio.LDAP else "Login via OIDC.",
    )
    db.session.commit()
    return redirect(url_for("main.index"))


@auth_bp.route("/logout")
def logout():
    usuario = usuario_atual()
    if usuario is not None:
        registrar_auditoria(usuario=usuario, acao="LOGOUT")
        db.session.commit()

    session.clear()
    flash("Você saiu do sistema.", "info")
    return redirect(url_for("auth.login"))
