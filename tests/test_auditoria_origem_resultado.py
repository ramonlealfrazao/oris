"""Audit trail completo (documento do Humberto): QUEM, O QUE, QUANDO, DE ONDE e RESULTADO.

Cobre origem (IP), resultado (SUCESSO/FALHA) e o registro de tentativas de login
que falham (que nao tem usuario vinculado).
"""

import pytest

from app import create_app
from app.extensions import db
from app.models import Auditoria, PerfilUsuario, Usuario
from app.utils.security import gerar_hash_senha
from config import TestingConfig

SENHA = "SenhaForte123!"
EMAIL = "admin@oris.com.br"


class Cfg(TestingConfig):
    RATE_LIMIT_LOGIN_ENABLED = False


class CfgComLimite(TestingConfig):
    RATE_LIMIT_LOGIN_ENABLED = True


def _app(cfg):
    app = create_app(cfg)
    with app.app_context():
        db.create_all()
        db.session.add(Usuario(nome="Admin", email=EMAIL, senha_hash=gerar_hash_senha(SENHA),
                               perfil=PerfilUsuario.ADMINISTRADOR, ativo=True))
        db.session.add(Usuario(nome="Inativo", email="inativo@oris.com.br", senha_hash=gerar_hash_senha(SENHA),
                               perfil=PerfilUsuario.GESTOR, ativo=False))
        db.session.commit()
    return app


@pytest.fixture
def app():
    return _app(Cfg)


def _postar(client, email, senha, ip="203.0.113.7"):
    client.get("/login")
    return client.post("/login", data={"email": email, "senha": senha},
                       environ_overrides={"REMOTE_ADDR": ip}, follow_redirects=False)


def _login_pelo_cliente(client, email, senha, ip="203.0.113.7"):
    # o formulario tem CSRF desligado no TestingConfig
    return _postar(client, email, senha, ip)


def test_login_com_sucesso_registra_ip_e_resultado(app):
    c = app.test_client()
    _login_pelo_cliente(c, EMAIL, SENHA, ip="198.51.100.20")
    with app.app_context():
        reg = Auditoria.query.filter_by(acao="LOGIN").one()
        assert reg.origem_ip == "198.51.100.20"
        assert reg.resultado == "SUCESSO"
        assert reg.usuario_id is not None


def test_login_com_senha_errada_e_registrado_como_falha(app):
    c = app.test_client()
    _login_pelo_cliente(c, EMAIL, "senha-errada", ip="198.51.100.21")
    with app.app_context():
        reg = Auditoria.query.filter_by(acao="LOGIN_FALHA").one()
        assert reg.resultado == "FALHA"
        assert reg.origem_ip == "198.51.100.21"
        assert reg.identificador_tentado == EMAIL
        assert reg.usuario_id is not None  # usuario existe, senha errada
        assert "senha" not in (reg.descricao or "").lower() or "SenhaForte" not in (reg.descricao or "")


def test_login_com_usuario_inexistente_e_registrado_sem_usuario(app):
    c = app.test_client()
    _login_pelo_cliente(c, "nao.existe@oris.com.br", "qualquer", ip="198.51.100.22")
    with app.app_context():
        reg = Auditoria.query.filter_by(acao="LOGIN_FALHA").one()
        assert reg.usuario_id is None
        assert reg.identificador_tentado == "nao.existe@oris.com.br"
        assert reg.resultado == "FALHA"


def test_login_de_usuario_inativo_e_falha_e_nao_revela_motivo_ao_usuario(app):
    c = app.test_client()
    resp = _login_pelo_cliente(c, "inativo@oris.com.br", SENHA)
    assert resp.status_code == 200  # volta ao formulario (mensagem generica)
    with app.app_context():
        reg = Auditoria.query.filter_by(acao="LOGIN_FALHA").one()
        assert "inativ" in reg.descricao.lower()  # o motivo fica so na trilha


def test_senha_digitada_nunca_e_gravada_na_auditoria(app):
    c = app.test_client()
    _login_pelo_cliente(c, EMAIL, "SegredoDigitado#999")
    with app.app_context():
        for reg in Auditoria.query.all():
            for campo in (reg.descricao, reg.valor_anterior, reg.valor_novo, reg.identificador_tentado):
                assert "SegredoDigitado#999" not in (campo or "")


def test_identificador_tentado_e_limitado(app):
    c = app.test_client()
    _login_pelo_cliente(c, "x" * 400 + "@oris.com.br", "qualquer")
    with app.app_context():
        reg = Auditoria.query.filter_by(acao="LOGIN_FALHA").first()
        if reg is not None:  # o formulario pode rejeitar e-mail enorme antes
            assert len(reg.identificador_tentado) <= 255


def test_bloqueio_por_excesso_de_tentativas_e_registrado():
    app = _app(CfgComLimite)
    c = app.test_client()
    for _ in range(12):
        _postar(c, EMAIL, "errada", ip="198.51.100.30")
    with app.app_context():
        acoes = {a.acao for a in Auditoria.query.all()}
        assert "LOGIN_FALHA" in acoes
        assert "LOGIN_BLOQUEADO" in acoes


def test_registros_antigos_continuam_validos_resultado_padrao(app):
    with app.app_context():
        u = Usuario.query.filter_by(email=EMAIL).one()
        db.session.add(Auditoria(usuario_id=u.id, acao="X"))
        db.session.commit()
        assert Auditoria.query.filter_by(acao="X").one().resultado == "SUCESSO"


def test_tela_de_auditoria_mostra_ip_resultado_e_filtra_por_falha(app):
    c = app.test_client()
    _login_pelo_cliente(c, "ninguem@oris.com.br", "x", ip="198.51.100.40")
    _login_pelo_cliente(c, EMAIL, SENHA, ip="198.51.100.41")
    html = c.get("/auditoria").get_data(as_text=True)
    assert "198.51.100.40" in html and "198.51.100.41" in html
    assert "ninguem@oris.com.br" in html
    so_falhas = c.get("/auditoria?resultado=FALHA").get_data(as_text=True)
    assert "198.51.100.40" in so_falhas and "198.51.100.41" not in so_falhas
    detalhe = c.get("/auditoria/1").get_data(as_text=True)
    assert "Origem" in detalhe
