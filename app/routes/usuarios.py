from flask import Blueprint, abort, current_app, flash, redirect, render_template, request, url_for

from app.extensions import db
from app.forms import AcaoAlteracaoForm, CriarUsuarioForm, EditarUsuarioForm, RedefinirSenhaForm
from app.models import OrigemDiretorio, PerfilUsuario, Usuario
from app.services import ldap_service, mfa_service
from app.services.diretorio_service import (
    DiretorioConfigError,
    carregar_mapa_grupo_perfil,
    resolver_perfil,
    sincronizar_usuarios,
)
from app.services.auditoria_service import registrar_auditoria
from app.utils.decorators import roles_required, usuario_atual
from app.utils.security import gerar_hash_senha

usuarios_bp = Blueprint("usuarios", __name__, url_prefix="/usuarios")

PERFIL_ADMINISTRADOR = PerfilUsuario.ADMINISTRADOR.value

PERFIS_CHOICES = [perfil.value for perfil in PerfilUsuario]


def _buscar_usuario_ou_404(usuario_id):
    usuario = db.session.get(Usuario, usuario_id)
    if usuario is None:
        abort(404)
    return usuario


def _total_administradores_ativos(excluir_id=None):
    query = Usuario.query.filter_by(perfil=PerfilUsuario.ADMINISTRADOR, ativo=True)
    if excluir_id is not None:
        query = query.filter(Usuario.id != excluir_id)
    return query.count()


def _e_ultimo_administrador_ativo(usuario):
    if usuario.perfil != PerfilUsuario.ADMINISTRADOR or not usuario.ativo:
        return False
    return _total_administradores_ativos(excluir_id=usuario.id) == 0


@usuarios_bp.route("")
@roles_required(PERFIL_ADMINISTRADOR)
def listar():
    query = Usuario.query

    busca = request.args.get("busca", "").strip()
    if busca:
        termo = f"%{busca}%"
        query = query.filter(db.or_(Usuario.nome.ilike(termo), Usuario.email.ilike(termo)))

    perfil_filtro = request.args.get("perfil")
    if perfil_filtro in PERFIS_CHOICES:
        query = query.filter(Usuario.perfil == PerfilUsuario(perfil_filtro))

    situacao_filtro = request.args.get("situacao")
    if situacao_filtro in ("1", "0"):
        query = query.filter(Usuario.ativo == (situacao_filtro == "1"))

    usuarios = query.order_by(Usuario.nome).all()

    return render_template(
        "usuarios/lista.html",
        usuarios=usuarios,
        busca=busca,
        perfil_filtro=perfil_filtro,
        situacao_filtro=situacao_filtro,
        perfis=PERFIS_CHOICES,
        form_acao=AcaoAlteracaoForm(),
    )


@usuarios_bp.route("/novo", methods=["GET", "POST"])
@roles_required(PERFIL_ADMINISTRADOR)
def novo():
    form = CriarUsuarioForm()

    if form.validate_on_submit():
        email = form.email.data.strip().lower()

        if Usuario.query.filter_by(email=email).first() is not None:
            flash(f"Já existe um usuário cadastrado com o email '{email}'.", "danger")
            return render_template("usuarios/form.html", form=form, titulo="Novo Usuário")

        novo_usuario = Usuario(
            nome=form.nome.data.strip(),
            email=email,
            senha_hash=gerar_hash_senha(form.senha.data),
            perfil=PerfilUsuario(form.perfil.data),
            ativo=(form.ativo.data == "1"),
        )
        db.session.add(novo_usuario)
        db.session.flush()

        registrar_auditoria(
            usuario=usuario_atual(),
            acao="CRIAR_USUARIO",
            tabela="usuarios",
            registro_id=novo_usuario.id,
            descricao=f"Criação do usuário '{novo_usuario.nome}' ({novo_usuario.email}), perfil {novo_usuario.perfil.value}.",
        )
        db.session.commit()

        flash(f"Usuário '{novo_usuario.nome}' criado com sucesso.", "success")
        return redirect(url_for("usuarios.listar"))

    return render_template("usuarios/form.html", form=form, titulo="Novo Usuário")


@usuarios_bp.route("/<int:usuario_id>/editar", methods=["GET", "POST"])
@roles_required(PERFIL_ADMINISTRADOR)
def editar(usuario_id):
    usuario = _buscar_usuario_ou_404(usuario_id)
    form = EditarUsuarioForm()

    if form.validate_on_submit():
        email_novo = form.email.data.strip().lower()
        nome_novo = form.nome.data.strip()
        perfil_novo = PerfilUsuario(form.perfil.data)

        email_em_uso = Usuario.query.filter(Usuario.email == email_novo, Usuario.id != usuario.id).first()
        if email_em_uso is not None:
            flash(f"Já existe outro usuário cadastrado com o email '{email_novo}'.", "danger")
            return render_template(
                "usuarios/form.html", form=form, titulo=f"Editar Usuário — {usuario.nome}", usuario=usuario
            )

        if perfil_novo != usuario.perfil and _e_ultimo_administrador_ativo(usuario):
            flash(
                "Não é possível alterar o perfil deste usuário: ele é o único "
                "ADMINISTRADOR ativo do sistema.",
                "danger",
            )
            return render_template(
                "usuarios/form.html", form=form, titulo=f"Editar Usuário — {usuario.nome}", usuario=usuario
            )

        nome_anterior, email_anterior, perfil_anterior = usuario.nome, usuario.email, usuario.perfil

        usuario.nome = nome_novo
        usuario.email = email_novo
        usuario.perfil = perfil_novo

        if nome_anterior != nome_novo or email_anterior != email_novo:
            registrar_auditoria(
                usuario=usuario_atual(),
                acao="EDITAR_USUARIO",
                tabela="usuarios",
                registro_id=usuario.id,
                descricao=f"Edição do usuário #{usuario.id}.",
                valor_anterior={"nome": nome_anterior, "email": email_anterior},
                valor_novo={"nome": nome_novo, "email": email_novo},
            )

        if perfil_anterior != perfil_novo:
            registrar_auditoria(
                usuario=usuario_atual(),
                acao="ALTERAR_PERFIL",
                tabela="usuarios",
                registro_id=usuario.id,
                descricao=f"Alteração de perfil do usuário #{usuario.id}: {perfil_anterior.value} → {perfil_novo.value}.",
                valor_anterior={"perfil": perfil_anterior.value},
                valor_novo={"perfil": perfil_novo.value},
            )

        db.session.commit()

        flash(f"Usuário '{usuario.nome}' atualizado com sucesso.", "success")
        return redirect(url_for("usuarios.listar"))

    if not form.is_submitted():
        form.nome.data = usuario.nome
        form.email.data = usuario.email
        form.perfil.data = usuario.perfil.value

    return render_template(
        "usuarios/form.html",
        form=form,
        titulo=f"Editar Usuário — {usuario.nome}",
        usuario=usuario,
        form_senha=RedefinirSenhaForm(),
        form_mfa=AcaoAlteracaoForm(),
    )


@usuarios_bp.route("/<int:usuario_id>/situacao", methods=["POST"])
@roles_required(PERFIL_ADMINISTRADOR)
def alterar_situacao(usuario_id):
    usuario = _buscar_usuario_ou_404(usuario_id)
    form = AcaoAlteracaoForm()

    if not form.validate_on_submit():
        flash("Não foi possível processar a solicitação.", "danger")
        return redirect(url_for("usuarios.listar"))

    situacao_desejada = request.form.get("acao") == "ativar"

    if situacao_desejada == usuario.ativo:
        flash("O usuário já está nessa situação.", "warning")
        return redirect(url_for("usuarios.listar"))

    if not situacao_desejada and _e_ultimo_administrador_ativo(usuario):
        flash(
            "Não é possível desativar este usuário: ele é o único "
            "ADMINISTRADOR ativo do sistema.",
            "danger",
        )
        return redirect(url_for("usuarios.listar"))

    usuario.ativo = situacao_desejada
    acao = "ATIVAR_USUARIO" if situacao_desejada else "DESATIVAR_USUARIO"

    registrar_auditoria(
        usuario=usuario_atual(),
        acao=acao,
        tabela="usuarios",
        registro_id=usuario.id,
        descricao=f"{'Ativação' if situacao_desejada else 'Desativação'} do usuário '{usuario.nome}' ({usuario.email}).",
    )
    db.session.commit()

    flash(f"Usuário '{usuario.nome}' {'ativado' if situacao_desejada else 'desativado'} com sucesso.", "success")
    return redirect(url_for("usuarios.listar"))


@usuarios_bp.route("/<int:usuario_id>/senha", methods=["POST"])
@roles_required(PERFIL_ADMINISTRADOR)
def redefinir_senha(usuario_id):
    usuario = _buscar_usuario_ou_404(usuario_id)
    form = RedefinirSenhaForm()

    if not form.validate_on_submit():
        for campo, erros in form.errors.items():
            for erro in erros:
                flash(erro, "danger")
        return redirect(url_for("usuarios.editar", usuario_id=usuario.id))

    usuario.senha_hash = gerar_hash_senha(form.nova_senha.data)

    registrar_auditoria(
        usuario=usuario_atual(),
        acao="REDEFINIR_SENHA",
        tabela="usuarios",
        registro_id=usuario.id,
        descricao=f"Redefinição administrativa da senha do usuário '{usuario.nome}' ({usuario.email}).",
    )
    db.session.commit()

    flash(f"Senha do usuário '{usuario.nome}' redefinida com sucesso.", "success")
    return redirect(url_for("usuarios.editar", usuario_id=usuario.id))


@usuarios_bp.route("/<int:usuario_id>/mfa/redefinir", methods=["POST"])
@roles_required(PERFIL_ADMINISTRADOR)
def redefinir_mfa(usuario_id):
    usuario = _buscar_usuario_ou_404(usuario_id)
    form = AcaoAlteracaoForm()
    if not form.validate_on_submit():
        flash("Não foi possível processar a solicitação.", "danger")
        return redirect(url_for("usuarios.editar", usuario_id=usuario.id))

    if not usuario.mfa_ativo and not usuario.mfa_segredo:
        flash("Este usuário ainda não cadastrou a verificação em dois fatores.", "warning")
        return redirect(url_for("usuarios.editar", usuario_id=usuario.id))

    mfa_service.redefinir(usuario)
    registrar_auditoria(
        usuario=usuario_atual(),
        acao="MFA_REDEFINIDO",
        tabela="usuarios",
        registro_id=usuario.id,
        descricao=f"MFA redefinido pelo administrador para '{usuario.nome}' ({usuario.email}); "
                  "o usuário cadastra um novo aplicativo no próximo login.",
    )
    db.session.commit()

    flash(f"MFA de '{usuario.nome}' redefinido. No próximo login ele cadastra o aplicativo de novo.", "success")
    return redirect(url_for("usuarios.editar", usuario_id=usuario.id))


def _config_ldap_resumo():
    cfg = current_app.config
    uri = cfg.get("LDAP_URI") or ""
    return {
        "configurado": bool(uri),
        "uri": uri,
        "tls": uri.lower().startswith("ldaps://") or bool(cfg.get("LDAP_USE_STARTTLS")),
        "valida_certificado": bool(cfg.get("LDAP_CA_CERT_FILE")) or uri.lower().startswith("ldaps://"),
        "base_usuarios": cfg.get("LDAP_USER_BASE") or "",
        "base_grupos": cfg.get("LDAP_GROUP_BASE") or "",
        "conta_servico": cfg.get("LDAP_BIND_DN") or "",
    }


@usuarios_bp.route("/diretorio", methods=["GET", "POST"])
@roles_required(PERFIL_ADMINISTRADOR)
def diretorio():
    form = AcaoAlteracaoForm()
    resultado, erro, mapa = None, None, {}
    try:
        mapa = carregar_mapa_grupo_perfil()
    except DiretorioConfigError as exc:
        erro = str(exc)

    if request.method == "POST":
        if not form.validate_on_submit():
            abort(400)
        gravar = request.form.get("modo") == "gravar"
        try:
            externos = ldap_service.buscar_usuarios_ldap()
            resumo = sincronizar_usuarios(
                externos, OrigemDiretorio.LDAP, desativar_ausentes=True, simular=not gravar
            )
            pessoas = []
            for externo in externos:
                perfil = resolver_perfil(externo.grupos, mapa)
                pessoas.append({
                    "uid": externo.identificador, "nome": externo.nome, "email": externo.email,
                    "grupos": externo.grupos, "perfil": perfil.value if perfil else None,
                })
            resultado = {"gravou": gravar, "resumo": resumo, "pessoas": pessoas}
            if gravar:
                registrar_auditoria(
                    usuario=usuario_atual(),
                    acao="SINCRONIZAR_LDAP",
                    tabela="usuarios",
                    descricao=(
                        f"Sincronização LDAP pela interface: {len(externos)} lido(s), "
                        f"{resumo['criados']} criado(s), {resumo['atualizados']} atualizado(s), "
                        f"{resumo['desativados']} desativado(s)."
                    ),
                )
                db.session.commit()
                flash("Sincronização concluída: as tabelas locais foram atualizadas.", "success")
        except DiretorioConfigError as exc:
            erro = str(exc)
        except Exception:
            current_app.logger.exception("Falha ao consultar o LDAP")
            erro = "Não foi possível consultar o LDAP (servidor fora do ar, certificado ou senha da conta de serviço)."

    contas = Usuario.query.filter_by(origem=OrigemDiretorio.LDAP).order_by(Usuario.nome).all()
    return render_template(
        "usuarios/diretorio.html", form=form, config=_config_ldap_resumo(), mapa=mapa,
        resultado=resultado, erro=erro, contas=contas,
    )
