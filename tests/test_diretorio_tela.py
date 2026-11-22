import pytest

from app import create_app
from app.extensions import db
from app.models import Auditoria, OrigemDiretorio, PerfilUsuario, Usuario
from app.services import ldap_service
from app.services.diretorio_service import DiretorioConfigError, UsuarioExterno
from app.utils.security import gerar_hash_senha
from config import TestingConfig

SENHA = "SenhaForte123!"
MAPA = '{"oris-admin":"ADMINISTRADOR","oris-gestor":"GESTOR"}'


class Config(TestingConfig):
    LDAP_URI = "ldap://ldap.teste:389"
    LDAP_USE_STARTTLS = True
    LDAP_CA_CERT_FILE = "/certs/ca.crt"
    LDAP_BIND_DN = "cn=leitor,dc=oris,dc=local"
    LDAP_USER_BASE = "ou=usuarios,dc=oris,dc=local"
    LDAP_GROUP_BASE = "ou=grupos,dc=oris,dc=local"
    DIRETORIO_MAPA_GRUPO_PERFIL = MAPA


PESSOAS = [
    UsuarioExterno(identificador="ana.admin", nome="Ana", email="ana@rede.gov", grupos=["oris-admin"]),
    UsuarioExterno(identificador="davi.gestor", nome="Davi", email="davi@rede.gov", grupos=["oris-gestor"]),
    UsuarioExterno(identificador="eva.semgrupo", nome="Eva", email="eva@rede.gov", grupos=[]),
]


@pytest.fixture
def app(monkeypatch):
    app = create_app(Config)
    with app.app_context():
        db.create_all()
        for email, perfil in (("admin@oris.com.br", PerfilUsuario.ADMINISTRADOR), ("gestor@oris.com.br", PerfilUsuario.GESTOR)):
            db.session.add(Usuario(nome=email, email=email, senha_hash=gerar_hash_senha(SENHA), perfil=perfil, ativo=True))
        db.session.commit()
    monkeypatch.setattr(ldap_service, "buscar_usuarios_ldap", lambda config=None, conexao=None: list(PESSOAS))
    yield app
    with app.app_context():
        db.session.remove()
        db.drop_all()


@pytest.fixture
def client(app):
    return app.test_client()


def entrar(client, email):
    client.post("/login", data={"email": email, "senha": SENHA})


def test_so_administrador_abre_a_tela(client):
    entrar(client, "gestor@oris.com.br")
    assert client.get("/usuarios/diretorio").status_code == 403


def test_tela_mostra_conexao_tls_e_mapa(client):
    entrar(client, "admin@oris.com.br")
    texto = client.get("/usuarios/diretorio").get_data(as_text=True)
    assert "ldap://ldap.teste:389" in texto and "certificado validado" in texto
    assert "oris-admin" in texto and "ADMINISTRADOR" in texto


def test_simular_mostra_quem_entra_e_nao_grava(client, app):
    entrar(client, "admin@oris.com.br")
    texto = client.post("/usuarios/diretorio", data={"modo": "simular"}).get_data(as_text=True)
    assert "Simulação: nada foi gravado" in texto
    assert "ana.admin" in texto and "sem grupo mapeado" in texto
    with app.app_context():
        assert Usuario.query.filter_by(origem=OrigemDiretorio.LDAP).count() == 0
        assert Auditoria.query.filter_by(acao="SINCRONIZAR_LDAP").count() == 0


def test_sincronizar_grava_tabelas_locais_e_audita(client, app):
    entrar(client, "admin@oris.com.br")
    texto = client.post("/usuarios/diretorio", data={"modo": "gravar"}).get_data(as_text=True)
    assert "Resultado da sincronização" in texto
    with app.app_context():
        ana = Usuario.query.filter_by(email="ana@rede.gov").one()
        assert ana.origem == OrigemDiretorio.LDAP and ana.perfil == PerfilUsuario.ADMINISTRADOR
        assert [g.nome for g in ana.grupos] == ["oris-admin"]
        assert Usuario.query.filter_by(email="eva@rede.gov").first() is None
        assert Auditoria.query.filter_by(acao="SINCRONIZAR_LDAP").count() == 1
    assert "davi@rede.gov" in client.get("/usuarios/diretorio").get_data(as_text=True)


def test_erro_de_configuracao_aparece_na_tela(client, monkeypatch):
    def falha(config=None, conexao=None):
        raise DiretorioConfigError("Conexão LDAP sem TLS recusada")

    monkeypatch.setattr(ldap_service, "buscar_usuarios_ldap", falha)
    entrar(client, "admin@oris.com.br")
    resp = client.post("/usuarios/diretorio", data={"modo": "simular"})
    assert resp.status_code == 200 and "sem TLS recusada" in resp.get_data(as_text=True)


def test_falha_de_rede_mostra_mensagem_generica(client, monkeypatch):
    def falha(config=None, conexao=None):
        raise OSError("connection refused 10.0.0.5")

    monkeypatch.setattr(ldap_service, "buscar_usuarios_ldap", falha)
    entrar(client, "admin@oris.com.br")
    texto = client.post("/usuarios/diretorio", data={"modo": "gravar"}).get_data(as_text=True)
    assert "Não foi possível consultar o LDAP" in texto and "10.0.0.5" not in texto


def test_botao_na_lista_de_usuarios(client):
    entrar(client, "admin@oris.com.br")
    assert "/usuarios/diretorio" in client.get("/usuarios").get_data(as_text=True)
