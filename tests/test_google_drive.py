import json
import urllib.parse

import jwt
import pytest
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa

from app.models import Auditoria, PerfilUsuario
from app.services import gdrive_service, oidc_service

from tests.test_fase14_diretorio_relatorios import _dados_rede, _login, app, client  # noqa: F401


@pytest.fixture()
def conta_servico(tmp_path):
    chave = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    pem = chave.private_bytes(
        serialization.Encoding.PEM,
        serialization.PrivateFormat.PKCS8,
        serialization.NoEncryption(),
    ).decode()
    caminho = tmp_path / "sa.json"
    caminho.write_text(json.dumps({
        "client_email": "oris@projeto.iam.gserviceaccount.com",
        "private_key": pem,
        "token_uri": "https://oauth2.googleapis.com/token",
    }))
    return str(caminho), chave.public_key()


@pytest.fixture()
def envios(monkeypatch):
    chamadas = []

    def falso(token, conteudo, nome, pasta_id=None):
        chamadas.append({"token": token, "conteudo": conteudo, "nome": nome, "pasta": pasta_id})
        return {"id": "abc", "name": nome}

    monkeypatch.setattr(gdrive_service, "enviar_arquivo", falso)
    return chamadas


def test_token_m2m_usa_jwt_bearer_assinado_pela_conta_de_servico(app, conta_servico, monkeypatch):
    caminho, publica = conta_servico
    capturado = {}

    def falso(url, dados):
        capturado.update(url=url, dados=dados)
        return {"access_token": "tok-m2m"}

    monkeypatch.setattr(oidc_service, "_http_post_form", falso)
    with app.app_context():
        app.config["GOOGLE_SA_ARQUIVO"] = caminho
        assert gdrive_service.token_m2m() == "tok-m2m"

    assert capturado["dados"]["grant_type"] == "urn:ietf:params:oauth:grant-type:jwt-bearer"
    claims = jwt.decode(
        capturado["dados"]["assertion"], publica, algorithms=["RS256"],
        audience="https://oauth2.googleapis.com/token",
    )
    assert claims["iss"] == "oris@projeto.iam.gserviceaccount.com"
    assert claims["scope"] == gdrive_service.ESCOPO_DRIVE_CONTA_SERVICO


def test_exportacao_m2m_envia_para_a_pasta_e_audita(app, client, conta_servico, envios, monkeypatch):
    caminho, _ = conta_servico
    app.config.update(GOOGLE_SA_ARQUIVO=caminho, GOOGLE_DRIVE_PASTA_ID="pasta123")
    monkeypatch.setattr(gdrive_service, "token_m2m", lambda config=None: "tok-m2m")
    _dados_rede(app)
    _login(client, PerfilUsuario.GESTAO_INFORMACAO)

    client.post("/relatorios/unidades/exportar-drive-m2m")

    assert len(envios) == 1
    assert envios[0]["token"] == "tok-m2m" and envios[0]["pasta"] == "pasta123"
    with app.app_context():
        registro = Auditoria.query.filter_by(acao="EXPORTAR_DRIVE", tabela="unidades").one()
        assert "OAuth2 M2M" in registro.descricao and "SHA-256" in registro.descricao


def test_falha_do_google_nao_audita_nem_vaza_detalhe(app, client, conta_servico, monkeypatch):
    caminho, _ = conta_servico
    app.config.update(GOOGLE_SA_ARQUIVO=caminho, GOOGLE_DRIVE_PASTA_ID="pasta123")

    def quebra(config=None):
        raise gdrive_service.DriveError("O Google não emitiu token para a conta de serviço.")

    monkeypatch.setattr(gdrive_service, "token_m2m", quebra)
    _dados_rede(app)
    _login(client, PerfilUsuario.ADMINISTRADOR)
    client.post("/relatorios/unidades/exportar-drive-m2m")
    with app.app_context():
        assert Auditoria.query.filter_by(acao="EXPORTAR_DRIVE").count() == 0


@pytest.mark.parametrize("perfil", [PerfilUsuario.GESTOR, PerfilUsuario.RESPONSAVEL_SAUDE_BUCAL])
@pytest.mark.parametrize("rota", ["exportar-drive-m2m", "exportar-drive-oidc"])
def test_perfis_sem_permissao_nao_exportam_ao_drive(app, client, envios, perfil, rota):
    app.config.update(GOOGLE_SA_ARQUIVO="x", GOOGLE_DRIVE_PASTA_ID="p", GOOGLE_CLIENT_ID="c", GOOGLE_CLIENT_SECRET="s")
    _login(client, perfil)
    assert client.post(f"/relatorios/unidades/{rota}").status_code == 403
    assert envios == []


def test_exportar_ao_drive_exige_login(client, envios):
    resp = client.post("/relatorios/unidades/exportar-drive-m2m")
    assert resp.status_code in (302, 401, 403) and envios == []


def test_sem_configuracao_nao_ha_botoes_do_drive(app, client):
    _login(client, PerfilUsuario.ADMINISTRADOR)
    html = client.get("/relatorios").get_data(as_text=True)
    assert "Drive (OIDC)" not in html and "Drive (M2M)" not in html


def test_com_configuracao_os_botoes_aparecem(app, client):
    app.config.update(GOOGLE_SA_ARQUIVO="x", GOOGLE_DRIVE_PASTA_ID="p", GOOGLE_CLIENT_ID="c", GOOGLE_CLIENT_SECRET="s")
    _dados_rede(app)
    _login(client, PerfilUsuario.ADMINISTRADOR)
    html = client.get("/relatorios").get_data(as_text=True)
    assert "Drive (OIDC)" in html and "Drive (M2M)" in html


def _configurar_oidc(app, monkeypatch):
    app.config.update(GOOGLE_CLIENT_ID="cliente-google", GOOGLE_CLIENT_SECRET="segredo-google")
    monkeypatch.setattr(
        oidc_service, "_http_get_json",
        lambda url, cabecalhos=None: {"authorization_endpoint": "https://accounts.google.com/o/oauth2/v2/auth"},
    )


def test_oidc_redireciona_ao_google_com_pkce_state_e_escopo_do_drive(app, client, monkeypatch):
    _configurar_oidc(app, monkeypatch)
    _login(client, PerfilUsuario.GESTAO_INFORMACAO)
    resp = client.post("/relatorios/unidades/exportar-drive-oidc")
    assert resp.status_code == 302
    destino = urllib.parse.urlparse(resp.headers["Location"])
    consulta = urllib.parse.parse_qs(destino.query)
    assert destino.netloc == "accounts.google.com"
    assert consulta["code_challenge_method"] == ["S256"]
    assert consulta["client_id"] == ["cliente-google"]
    assert gdrive_service.ESCOPO_DRIVE in consulta["scope"][0] and "openid" in consulta["scope"][0]
    assert consulta["state"]


def test_callback_com_state_errado_e_recusado(app, client, envios, monkeypatch):
    _configurar_oidc(app, monkeypatch)
    _login(client, PerfilUsuario.GESTAO_INFORMACAO)
    client.post("/relatorios/unidades/exportar-drive-oidc")
    client.get("/relatorios/google/callback?code=x&state=forjado")
    assert envios == []


def test_callback_valido_envia_com_token_da_pessoa_e_audita(app, client, envios, monkeypatch):
    _configurar_oidc(app, monkeypatch)
    monkeypatch.setattr(
        gdrive_service, "concluir_autorizacao_oidc",
        lambda codigo, estado, redirect_uri, config=None: ("tok-pessoa", "ana@exemplo.com"),
    )
    _dados_rede(app)
    _login(client, PerfilUsuario.GESTAO_INFORMACAO)
    resp = client.post("/relatorios/unidades/exportar-drive-oidc")
    estado = urllib.parse.parse_qs(urllib.parse.urlparse(resp.headers["Location"]).query)["state"][0]

    client.get(f"/relatorios/google/callback?code=abc&state={estado}")

    assert len(envios) == 1 and envios[0]["token"] == "tok-pessoa" and envios[0]["pasta"] is None
    with app.app_context():
        registro = Auditoria.query.filter_by(acao="EXPORTAR_DRIVE", tabela="unidades").one()
        assert "OIDC" in registro.descricao and "ana@exemplo.com" in registro.descricao



def _consulta_da_autorizacao(client):
    resp = client.post("/relatorios/unidades/exportar-drive-oidc")
    return urllib.parse.parse_qs(urllib.parse.urlparse(resp.headers["Location"]).query)


def test_oidc_pede_telas_em_portugues_e_sugere_o_dominio(app, client, monkeypatch):
    _configurar_oidc(app, monkeypatch)
    app.config["GOOGLE_DOMINIO"] = "rede.gov"
    _login(client, PerfilUsuario.GESTAO_INFORMACAO)
    consulta = _consulta_da_autorizacao(client)
    assert consulta["hl"] == ["pt-BR"] and consulta["hd"] == ["rede.gov"]


@pytest.mark.parametrize("email, esperado", [
    ("ana@rede.gov", ["ana@rede.gov"]),
    ("ana@outrarede.gov", None),
])
def test_oidc_so_sugere_email_do_proprio_dominio(app, monkeypatch, email, esperado):
    _configurar_oidc(app, monkeypatch)
    app.config["GOOGLE_DOMINIO"] = "rede.gov"
    with app.app_context():
        url, _ = gdrive_service.iniciar_autorizacao_oidc("https://oris.test/cb", email_sugerido=email)
    assert urllib.parse.parse_qs(urllib.parse.urlparse(url).query).get("login_hint") == esperado


def test_oidc_sem_dominio_nao_envia_hd_nem_email(app, client, monkeypatch):
    _configurar_oidc(app, monkeypatch)
    app.config["GOOGLE_DOMINIO"] = ""
    _login(client, PerfilUsuario.GESTAO_INFORMACAO)
    consulta = _consulta_da_autorizacao(client)
    assert "hd" not in consulta and "login_hint" not in consulta


def test_historico_mostra_envios_ao_drive_com_o_metodo(app, client, conta_servico, envios, monkeypatch):
    caminho, _ = conta_servico
    app.config.update(GOOGLE_SA_ARQUIVO=caminho, GOOGLE_DRIVE_PASTA_ID="pasta123")
    monkeypatch.setattr(gdrive_service, "token_m2m", lambda config=None: "tok-m2m")
    _configurar_oidc(app, monkeypatch)
    monkeypatch.setattr(
        gdrive_service, "concluir_autorizacao_oidc",
        lambda codigo, estado, redirect_uri, config=None: ("tok-pessoa", "ana@exemplo.com"),
    )
    _dados_rede(app)
    _login(client, PerfilUsuario.GESTAO_INFORMACAO)
    client.post("/relatorios/unidades/exportar-drive-m2m")
    estado = _consulta_da_autorizacao(client)["state"][0]
    client.get(f"/relatorios/google/callback?code=abc&state={estado}")

    html = client.get("/relatorios").get_data(as_text=True)
    assert "<td>Google Drive (M2M)</td>" in html and "<td>Google Drive (OIDC)</td>" in html
    assert envios[0]["nome"] in html

    linhas = client.get("/relatorios/historico.csv").get_data(as_text=True).lstrip("\ufeff").splitlines()
    assert linhas[0].endswith(",sha256,destino") and len(linhas) == 3
    assert {linha.rsplit(",", 1)[1] for linha in linhas[1:]} == {"Google Drive (M2M)", "Google Drive (OIDC)"}
