"""OIDC: verificação criptográfica do id_token (assinatura, exp e iat).

Antes, o ORIS lia as claims do id_token sem verificar a assinatura nem a
expiração. A especificação OIDC permite dispensar a assinatura quando o token
vem direto do endpoint de token por TLS, mas essa premissa cai com
OIDC_ALLOW_INSECURE e o `exp` nunca foi conferido. Estes testes fixam o
comportamento novo: o id_token só é aceito se tiver assinatura válida de uma
chave publicada no JWKS do provedor, algoritmo assimétrico permitido e datas
coerentes.
"""

import base64
import json
import time

import pytest

from app.services import oidc_service
from app.services.diretorio_service import DiretorioConfigError
from app.services.oidc_service import OidcError
from tests.oidc_helpers import KID, assinar, gerar_chave_privada, jwks_de

ISSUER = "https://idp.exemplo.test/realms/oris"
CONFIG = {
    "OIDC_ISSUER": ISSUER,
    "OIDC_CLIENT_ID": "oris-web",
    "OIDC_CLIENT_SECRET": "segredo",
    "OIDC_CLAIM_GROUPS": "groups",
}
ESTADO = {"state": "s", "nonce": "nonce-1", "code_verifier": "v"}


@pytest.fixture(scope="module")
def chave():
    return gerar_chave_privada()


@pytest.fixture(scope="module")
def chave_do_atacante():
    return gerar_chave_privada()


def _claims(**extra):
    agora = int(time.time())
    base = {
        "iss": ISSUER, "aud": "oris-web", "sub": "u-1", "nonce": "nonce-1",
        "iat": agora, "exp": agora + 300,
        "email": "dora@rede.gov", "email_verified": True, "name": "Dora", "groups": ["oris-gestao"],
    }
    base.update(extra)
    return base


@pytest.fixture
def provedor(monkeypatch, chave):
    """Provedor simulado; `ctx` permite trocar o id_token e o JWKS por teste."""
    ctx = {"id_token": None, "jwks": jwks_de(chave), "metadados_extra": {}}

    def fake_get(url, cabecalhos=None):
        if url.endswith("/.well-known/openid-configuration"):
            return {
                "authorization_endpoint": f"{ISSUER}/auth",
                "token_endpoint": f"{ISSUER}/token",
                "jwks_uri": f"{ISSUER}/jwks",
                **ctx["metadados_extra"],
            }
        if url.endswith("/jwks"):
            return ctx["jwks"]
        return {}

    def fake_post(url, dados):
        return {"id_token": ctx["id_token"]}

    monkeypatch.setattr(oidc_service, "_http_get_json", fake_get)
    monkeypatch.setattr(oidc_service, "_http_post_form", fake_post)
    return ctx


def _concluir():
    return oidc_service.concluir_autorizacao("codigo", dict(ESTADO), "https://app/cb", config=dict(CONFIG))


def test_id_token_com_assinatura_valida_e_aceito(provedor, chave):
    provedor["id_token"] = assinar(_claims(), chave)
    usuario = _concluir()
    assert usuario.identificador == "u-1"
    assert usuario.email == "dora@rede.gov"
    assert usuario.grupos == ["oris-gestao"]


def test_assinatura_de_outra_chave_e_recusada(provedor, chave_do_atacante):
    provedor["id_token"] = assinar(_claims(), chave_do_atacante)  # mesmo kid, chave errada
    with pytest.raises(OidcError):
        _concluir()


def test_claims_adulteradas_apos_assinar_sao_recusadas(provedor, chave):
    cabecalho, carga, assinatura = assinar(_claims(), chave).split(".")
    falsa = _claims(sub="admin-falso")
    carga_falsa = base64.urlsafe_b64encode(json.dumps(falsa).encode()).rstrip(b"=").decode()
    provedor["id_token"] = f"{cabecalho}.{carga_falsa}.{assinatura}"
    with pytest.raises(OidcError):
        _concluir()


def test_algoritmo_none_e_recusado(provedor):
    def b64(d):
        return base64.urlsafe_b64encode(json.dumps(d).encode()).rstrip(b"=").decode()

    provedor["id_token"] = f"{b64({'alg': 'none', 'kid': KID})}.{b64(_claims())}."
    with pytest.raises(OidcError):
        _concluir()


def test_confusao_de_algoritmo_hs256_com_chave_publica_e_recusada(provedor, chave):
    import jwt
    from cryptography.hazmat.primitives import serialization

    pem_publica = chave.public_key().public_bytes(
        serialization.Encoding.PEM, serialization.PublicFormat.SubjectPublicKeyInfo
    )
    # PyJWT recusa assinar HS256 com PEM; montamos o token à mão, como um atacante faria.
    import hashlib
    import hmac

    def b64(d: bytes):
        return base64.urlsafe_b64encode(d).rstrip(b"=").decode()

    cab = b64(json.dumps({"alg": "HS256", "kid": KID}).encode())
    car = b64(json.dumps(_claims()).encode())
    sig = b64(hmac.new(pem_publica, f"{cab}.{car}".encode(), hashlib.sha256).digest())
    provedor["id_token"] = f"{cab}.{car}.{sig}"
    with pytest.raises(OidcError):
        _concluir()
    assert jwt  # garante que o import acima não foi removido por lint


def test_token_expirado_e_recusado(provedor, chave):
    agora = int(time.time())
    provedor["id_token"] = assinar(_claims(iat=agora - 7200, exp=agora - 3600), chave)
    with pytest.raises(OidcError):
        _concluir()


def test_token_sem_exp_e_recusado(provedor, chave):
    claims = _claims()
    del claims["exp"]
    provedor["id_token"] = assinar(claims, chave)
    with pytest.raises(OidcError):
        _concluir()


def test_iat_no_futuro_e_recusado(provedor, chave):
    agora = int(time.time())
    provedor["id_token"] = assinar(_claims(iat=agora + 3600, exp=agora + 7200), chave)
    with pytest.raises(OidcError):
        _concluir()


def test_pequena_diferenca_de_relogio_e_tolerada(provedor, chave):
    agora = int(time.time())
    provedor["id_token"] = assinar(_claims(iat=agora + 20, exp=agora + 320), chave)
    assert _concluir().identificador == "u-1"


def test_kid_desconhecido_e_recusado(provedor, chave):
    provedor["id_token"] = assinar(_claims(), chave, kid="outro-kid")
    with pytest.raises(OidcError):
        _concluir()


def test_provedor_sem_jwks_uri_e_recusado(provedor, chave, monkeypatch):
    original = oidc_service._http_get_json

    def sem_jwks(url, cabecalhos=None):
        dados = original(url, cabecalhos)
        dados.pop("jwks_uri", None)
        return dados

    monkeypatch.setattr(oidc_service, "_http_get_json", sem_jwks)
    provedor["id_token"] = assinar(_claims(), chave)
    with pytest.raises(OidcError):
        _concluir()


def test_jwks_uri_sem_https_e_recusado(provedor, chave):
    provedor["metadados_extra"] = {"jwks_uri": "http://idp.exemplo.test/jwks"}
    provedor["id_token"] = assinar(_claims(), chave)
    with pytest.raises(DiretorioConfigError):
        _concluir()
