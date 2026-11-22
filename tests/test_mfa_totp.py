import json
import time

import pyotp
import pytest

from app import create_app
from app.extensions import db
from app.models import Auditoria, OrigemDiretorio, PerfilUsuario, Usuario
from app.services import mfa_service
from app.services.criptografia_service import decifrar_texto
from app.utils import rate_limit
from app.utils.security import gerar_hash_senha
from config import TestingConfig

SENHA = "SenhaForte123!"


class ConfigMfa(TestingConfig):
    MFA_OBRIGATORIO = True


class ConfigMfaRateLimit(ConfigMfa):
    RATE_LIMIT_LOGIN_ENABLED = True


def _criar_app(config):
    app = create_app(config)
    with app.app_context():
        db.create_all()
        for i, perfil in enumerate(PerfilUsuario):
            db.session.add(Usuario(
                nome=f"Usuário {perfil.value}", email=f"u{i}@oris.com.br",
                senha_hash=gerar_hash_senha(SENHA), perfil=perfil, ativo=True,
            ))
        db.session.add(Usuario(
            nome="Admin 2", email="admin2@oris.com.br", senha_hash=gerar_hash_senha(SENHA),
            perfil=PerfilUsuario.ADMINISTRADOR, ativo=True,
        ))
        db.session.commit()
    return app


@pytest.fixture
def app():
    app = _criar_app(ConfigMfa)
    yield app
    with app.app_context():
        db.session.remove()
        db.drop_all()


@pytest.fixture
def client(app):
    return app.test_client()


def _usuario(app, email):
    with app.app_context():
        return db.session.query(Usuario).filter_by(email=email).one()


def _segredo(app, email):
    with app.app_context():
        u = db.session.query(Usuario).filter_by(email=email).one()
        return decifrar_texto(u.mfa_segredo)


def _logado(client):
    with client.session_transaction() as s:
        return bool(s.get("autenticado"))


def _senha(client, email):
    return client.post("/login", data={"email": email, "senha": SENHA})


def _cadastrar(client, app, email):
    _senha(client, email)
    client.get("/login/mfa/cadastrar")
    segredo = _segredo(app, email)
    resp = client.post("/login/mfa/cadastrar", data={"codigo": pyotp.TOTP(segredo).now()})
    assert resp.status_code == 200
    texto = resp.get_data(as_text=True)
    import re
    codigos = re.findall(r"<code class=\"fs-6\">([A-Z0-9]{4}-[A-Z0-9]{4})</code>", texto)
    assert len(codigos) == mfa_service.QTD_CODIGOS_RECUPERACAO
    return segredo, codigos


def _sair(client):
    client.get("/logout")


@pytest.mark.parametrize("indice", range(len(PerfilUsuario)))
def test_senha_correta_nao_abre_sessao_e_exige_cadastro_para_todo_perfil(client, indice):
    resp = _senha(client, f"u{indice}@oris.com.br")
    assert resp.status_code == 302
    assert resp.headers["Location"].endswith("/login/mfa/cadastrar")
    assert not _logado(client)
    assert client.get("/").status_code == 302
    assert client.get("/unidades").headers["Location"].endswith("/login")


def test_cadastro_mostra_qr_e_chave_e_guarda_segredo_cifrado(client, app):
    _senha(client, "u0@oris.com.br")
    resp = client.get("/login/mfa/cadastrar")
    texto = resp.get_data(as_text=True)
    assert resp.status_code == 200
    assert "<svg" in texto
    u = _usuario(app, "u0@oris.com.br")
    assert u.mfa_ativo is False
    assert u.mfa_segredo.startswith("oris-fernet-v1:")
    segredo = _segredo(app, "u0@oris.com.br")
    assert mfa_service.formatar_segredo(segredo) in texto
    client.get("/login/mfa/cadastrar")
    assert _segredo(app, "u0@oris.com.br") == segredo


def test_cadastro_com_codigo_certo_ativa_abre_sessao_e_audita(client, app):
    _cadastrar(client, app, "u1@oris.com.br")
    assert _logado(client)
    u = _usuario(app, "u1@oris.com.br")
    assert u.mfa_ativo is True
    assert len(json.loads(u.mfa_codigos_recuperacao)) == 8
    with app.app_context():
        acoes = [a.acao for a in Auditoria.query.filter_by(usuario_id=u.id)]
    assert "LOGIN_PRIMEIRO_FATOR" in acoes and "MFA_ATIVADO" in acoes and "LOGIN" in acoes


def test_cadastro_com_codigo_errado_nao_ativa(client, app):
    _senha(client, "u0@oris.com.br")
    client.get("/login/mfa/cadastrar")
    resp = client.post("/login/mfa/cadastrar", data={"codigo": "000000"})
    assert resp.status_code == 200
    assert "Código inválido" in resp.get_data(as_text=True)
    assert _usuario(app, "u0@oris.com.br").mfa_ativo is False
    assert not _logado(client)
    with app.app_context():
        assert Auditoria.query.filter_by(acao="MFA_FALHA").count() == 1


def test_login_seguinte_pede_codigo_e_aceita_o_certo(client, app):
    segredo, _ = _cadastrar(client, app, "u2@oris.com.br")
    _sair(client)
    resp = _senha(client, "u2@oris.com.br")
    assert resp.headers["Location"].endswith("/login/mfa")
    assert not _logado(client)
    proximo = pyotp.TOTP(segredo).at(time.time() + 30)
    resp = client.post("/login/mfa", data={"codigo": proximo})
    assert resp.status_code == 302 and resp.headers["Location"].endswith("/")
    assert _logado(client)


def test_codigo_errado_nao_entra(client, app):
    _cadastrar(client, app, "u2@oris.com.br")
    _sair(client)
    _senha(client, "u2@oris.com.br")
    resp = client.post("/login/mfa", data={"codigo": "123456"})
    assert resp.status_code == 200
    assert not _logado(client)


def test_mesmo_codigo_nao_pode_ser_reutilizado(client, app):
    segredo, _ = _cadastrar(client, app, "u3@oris.com.br")
    _sair(client)
    _senha(client, "u3@oris.com.br")
    codigo = pyotp.TOTP(segredo).at(time.time() + 30)
    assert client.post("/login/mfa", data={"codigo": codigo}).status_code == 302
    _sair(client)
    _senha(client, "u3@oris.com.br")
    resp = client.post("/login/mfa", data={"codigo": codigo})
    assert resp.status_code == 200 and not _logado(client)


def test_codigo_de_recuperacao_entra_uma_unica_vez(client, app):
    _, codigos = _cadastrar(client, app, "u0@oris.com.br")
    _sair(client)
    _senha(client, "u0@oris.com.br")
    assert client.post("/login/mfa", data={"codigo": codigos[0].lower()}).status_code == 302
    assert _logado(client)
    assert mfa_service.codigos_restantes(_usuario(app, "u0@oris.com.br")) == 7
    _sair(client)
    _senha(client, "u0@oris.com.br")
    resp = client.post("/login/mfa", data={"codigo": codigos[0]})
    assert resp.status_code == 200 and not _logado(client)


def test_etapa_pendente_expira(client, app, monkeypatch):
    _cadastrar(client, app, "u1@oris.com.br")
    _sair(client)
    _senha(client, "u1@oris.com.br")
    agora = time.time()
    monkeypatch.setattr("app.routes.auth.time.time", lambda: agora + 6 * 60)
    resp = client.get("/login/mfa")
    assert resp.headers["Location"].endswith("/login")


def test_nao_da_para_pular_direto_para_a_etapa_do_codigo(client):
    resp = client.get("/login/mfa")
    assert resp.headers["Location"].endswith("/login")
    resp = client.post("/login/mfa/cadastrar", data={"codigo": "123456"})
    assert resp.headers["Location"].endswith("/login")


def test_usuario_desativado_durante_a_etapa_nao_entra(client, app):
    _senha(client, "u1@oris.com.br")
    with app.app_context():
        u = db.session.query(Usuario).filter_by(email="u1@oris.com.br").one()
        u.ativo = False
        db.session.commit()
    resp = client.get("/login/mfa/cadastrar")
    assert resp.headers["Location"].endswith("/login")


def test_conta_de_diretorio_nunca_chega_ao_mfa_local(client, app):
    with app.app_context():
        u = db.session.query(Usuario).filter_by(email="u1@oris.com.br").one()
        u.origem = OrigemDiretorio.OIDC
        db.session.commit()
    resp = _senha(client, "u1@oris.com.br")
    assert resp.status_code == 200
    assert not _logado(client)


def test_muitos_codigos_errados_bloqueiam_a_etapa():
    app = _criar_app(ConfigMfaRateLimit)
    client = app.test_client()
    u_id = _usuario(app, "u0@oris.com.br").id
    try:
        _cadastrar(client, app, "u0@oris.com.br")
        _sair(client)
        _senha(client, "u0@oris.com.br")
        for _ in range(rate_limit.LIMITE_TENTATIVAS):
            client.post("/login/mfa", data={"codigo": "000000"})
        resp = client.post("/login/mfa", data={"codigo": "000000"})
        assert resp.headers["Location"].endswith("/login")
        with app.app_context():
            assert Auditoria.query.filter_by(acao="MFA_BLOQUEADO").count() == 1
    finally:
        rate_limit.limpar_tentativas("mfa", f"usuario:{u_id}")
        rate_limit.limpar_tentativas("127.0.0.1", "u0@oris.com.br")
        with app.app_context():
            db.session.remove()
            db.drop_all()


def test_admin_redefine_mfa_de_quem_perdeu_o_celular(client, app):
    _cadastrar(client, app, "u3@oris.com.br")
    _sair(client)
    _cadastrar(client, app, "u0@oris.com.br")
    alvo = _usuario(app, "u3@oris.com.br")
    resp = client.post(f"/usuarios/{alvo.id}/mfa/redefinir")
    assert resp.status_code == 302
    alvo = _usuario(app, "u3@oris.com.br")
    assert alvo.mfa_ativo is False and alvo.mfa_segredo is None
    with app.app_context():
        assert Auditoria.query.filter_by(acao="MFA_REDEFINIDO", registro_id=alvo.id).count() == 1
    _sair(client)
    assert _senha(client, "u3@oris.com.br").headers["Location"].endswith("/login/mfa/cadastrar")


def test_quem_nao_e_admin_nao_redefine_mfa(client, app):
    _cadastrar(client, app, "u0@oris.com.br")
    _sair(client)
    _cadastrar(client, app, "u3@oris.com.br")
    alvo = _usuario(app, "u0@oris.com.br")
    assert client.post(f"/usuarios/{alvo.id}/mfa/redefinir").status_code == 403
    assert _usuario(app, "u0@oris.com.br").mfa_ativo is True


def test_tela_do_usuario_mostra_situacao_do_mfa(client, app):
    _cadastrar(client, app, "u0@oris.com.br")
    alvo = _usuario(app, "admin2@oris.com.br")
    texto = client.get(f"/usuarios/{alvo.id}/editar").get_data(as_text=True)
    assert "Verificação em dois fatores" in texto and "não cadastrado" in texto


def test_tolerancia_de_relogio_de_um_intervalo(app):
    with app.app_context():
        u = db.session.query(Usuario).filter_by(email="u0@oris.com.br").one()
        segredo = mfa_service.preparar_cadastro(u)
        agora = 1_000_000_000
        assert mfa_service.verificar_totp(u, pyotp.TOTP(segredo).at(agora - 30), agora=agora)
        u.mfa_ultimo_passo = None
        assert not mfa_service.verificar_totp(u, pyotp.TOTP(segredo).at(agora - 90), agora=agora)


def test_mfa_desligado_pela_configuracao_mantem_login_so_com_senha():
    app = create_app(TestingConfig)
    with app.app_context():
        db.create_all()
        db.session.add(Usuario(nome="X", email="x@oris.com.br", senha_hash=gerar_hash_senha(SENHA),
                               perfil=PerfilUsuario.GESTOR, ativo=True))
        db.session.commit()
    c = app.test_client()
    assert c.post("/login", data={"email": "x@oris.com.br", "senha": SENHA}).headers["Location"].endswith("/")
    with c.session_transaction() as s:
        assert s.get("autenticado")
    with app.app_context():
        db.session.remove()
        db.drop_all()


def test_mfa_e_obrigatorio_por_padrao_fora_dos_testes(monkeypatch):
    import importlib

    import config as modulo_config

    monkeypatch.delenv("MFA_OBRIGATORIO", raising=False)
    recarregado = importlib.reload(modulo_config)
    try:
        assert recarregado.Config.MFA_OBRIGATORIO is True
        assert recarregado.ProductionConfig.MFA_OBRIGATORIO is True
    finally:
        importlib.reload(modulo_config)
