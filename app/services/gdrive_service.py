import hashlib
import json
import secrets
import time
import urllib.error
import urllib.parse
import urllib.request
import uuid

import jwt
from flask import current_app

from app.services import oidc_service
from app.utils.datetime_utils import utcnow

GOOGLE_ISSUER = "https://accounts.google.com"
GOOGLE_DISCOVERY = f"{GOOGLE_ISSUER}/.well-known/openid-configuration"
GOOGLE_TOKEN_URL = "https://oauth2.googleapis.com/token"
GOOGLE_UPLOAD_URL = "https://www.googleapis.com/upload/drive/v3/files"
ESCOPO_DRIVE = "https://www.googleapis.com/auth/drive.file"
ESCOPO_DRIVE_CONTA_SERVICO = "https://www.googleapis.com/auth/drive"
TIMEOUT_SEGUNDOS = 20
FRONTEIRA = "oris-" + uuid.uuid4().hex


class DriveError(Exception):
    pass


def _cfg(config=None):
    return config if config is not None else current_app.config


def oidc_drive_configurado(config=None):
    config = _cfg(config)
    return bool(config.get("GOOGLE_CLIENT_ID") and config.get("GOOGLE_CLIENT_SECRET"))


def m2m_drive_configurado(config=None):
    config = _cfg(config)
    return bool(config.get("GOOGLE_SA_ARQUIVO") and config.get("GOOGLE_DRIVE_PASTA_ID"))


def _post_form(url, dados):
    try:
        return oidc_service._http_post_form(url, dados)
    except (urllib.error.URLError, ValueError, OSError) as erro:
        raise DriveError("Falha ao falar com o Google.") from erro


def _config_para_validar_token(config):
    return {"OIDC_CLIENT_ID": config["GOOGLE_CLIENT_ID"], "OIDC_ALLOW_INSECURE": False}


def iniciar_autorizacao_oidc(redirect_uri, config=None):
    config = _cfg(config)
    estado = {
        "state": secrets.token_urlsafe(24),
        "nonce": secrets.token_urlsafe(24),
        "code_verifier": secrets.token_urlsafe(48),
    }
    desafio = oidc_service._b64url(hashlib.sha256(estado["code_verifier"].encode("ascii")).digest())
    try:
        metadados = oidc_service._http_get_json(GOOGLE_DISCOVERY)
    except (urllib.error.URLError, ValueError, OSError) as erro:
        raise DriveError("Falha ao falar com o Google.") from erro
    parametros = {
        "response_type": "code",
        "client_id": config["GOOGLE_CLIENT_ID"],
        "redirect_uri": redirect_uri,
        "scope": f"openid email {ESCOPO_DRIVE}",
        "state": estado["state"],
        "nonce": estado["nonce"],
        "code_challenge": desafio,
        "code_challenge_method": "S256",
        "prompt": "consent",
    }
    url = f"{metadados['authorization_endpoint']}?{urllib.parse.urlencode(parametros)}"
    return url, estado


def concluir_autorizacao_oidc(codigo, estado, redirect_uri, config=None):
    config = _cfg(config)
    tokens = _post_form(
        GOOGLE_TOKEN_URL,
        {
            "grant_type": "authorization_code",
            "code": codigo,
            "redirect_uri": redirect_uri,
            "client_id": config["GOOGLE_CLIENT_ID"],
            "client_secret": config["GOOGLE_CLIENT_SECRET"],
            "code_verifier": estado["code_verifier"],
        },
    )
    id_token = tokens.get("id_token")
    acesso = tokens.get("access_token")
    if not id_token or not acesso:
        raise DriveError("Resposta do Google sem token.")
    try:
        metadados = oidc_service._http_get_json(GOOGLE_DISCOVERY)
        claims = oidc_service._verificar_id_token(id_token, metadados, _config_para_validar_token(config))
    except oidc_service.OidcError as erro:
        raise DriveError("Token do Google inválido.") from erro
    except (urllib.error.URLError, ValueError, OSError) as erro:
        raise DriveError("Falha ao falar com o Google.") from erro
    if claims.get("iss") not in (GOOGLE_ISSUER, "accounts.google.com"):
        raise DriveError("Emissor do token inesperado.")
    if not secrets.compare_digest(str(claims.get("nonce", "")), estado["nonce"]):
        raise DriveError("nonce do token não confere.")
    return acesso, claims.get("email", "")


def _carregar_conta_servico(config):
    try:
        with open(config["GOOGLE_SA_ARQUIVO"], encoding="utf-8") as arquivo:
            conta = json.load(arquivo)
        return conta["client_email"], conta["private_key"], conta.get("token_uri") or GOOGLE_TOKEN_URL
    except (OSError, ValueError, KeyError) as erro:
        raise DriveError("Credencial da conta de serviço indisponível.") from erro


def token_m2m(config=None):
    config = _cfg(config)
    email, chave, token_uri = _carregar_conta_servico(config)
    agora = int(time.time())
    assertiva = jwt.encode(
        {"iss": email, "scope": ESCOPO_DRIVE_CONTA_SERVICO, "aud": token_uri, "iat": agora, "exp": agora + 300},
        chave,
        algorithm="RS256",
    )
    resposta = _post_form(
        token_uri,
        {"grant_type": "urn:ietf:params:oauth:grant-type:jwt-bearer", "assertion": assertiva},
    )
    token = resposta.get("access_token")
    if not token:
        raise DriveError("O Google não emitiu token para a conta de serviço.")
    return token


def enviar_arquivo(token, conteudo, nome, pasta_id=None):
    metadados = {"name": nome}
    if pasta_id:
        metadados["parents"] = [pasta_id]
    corpo = (
        f"--{FRONTEIRA}\r\nContent-Type: application/json; charset=UTF-8\r\n\r\n"
        f"{json.dumps(metadados)}\r\n"
        f"--{FRONTEIRA}\r\nContent-Type: text/csv\r\n\r\n"
    ).encode("utf-8") + conteudo + f"\r\n--{FRONTEIRA}--".encode("ascii")
    consulta = urllib.parse.urlencode(
        {"uploadType": "multipart", "supportsAllDrives": "true", "fields": "id,name,webViewLink"}
    )
    requisicao = urllib.request.Request(
        f"{GOOGLE_UPLOAD_URL}?{consulta}",
        data=corpo,
        headers={
            "Authorization": f"Bearer {token}",
            "Content-Type": f"multipart/related; boundary={FRONTEIRA}",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(requisicao, timeout=TIMEOUT_SEGUNDOS) as resposta:  # noqa: S310
            return json.loads(resposta.read().decode("utf-8"))
    except (urllib.error.URLError, ValueError, OSError) as erro:
        current_app.logger.exception("Falha ao enviar arquivo ao Google Drive")
        raise DriveError("Não foi possível enviar o arquivo ao Google Drive.") from erro


def nome_arquivo(entidade):
    return f"oris-{entidade}-{utcnow().strftime('%Y%m%d-%H%M%S')}.csv"
