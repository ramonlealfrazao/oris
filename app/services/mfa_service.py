import hashlib
import hmac
import json
import secrets
import time

import pyotp
import segno
from flask import current_app
from markupsafe import Markup

from app.services.criptografia_service import cifrar_texto, decifrar_texto

EMISSOR = "ORIS"
PERIODO = 30
TOLERANCIA_PASSOS = 1
QTD_CODIGOS_RECUPERACAO = 8
ALFABETO_RECUPERACAO = "ABCDEFGHJKMNPQRSTUVWXYZ23456789"


def mfa_obrigatorio():
    return bool(current_app.config.get("MFA_OBRIGATORIO", True))


def preparar_cadastro(usuario):
    if usuario.mfa_ativo:
        raise ValueError("O MFA deste usuário já está ativo.")
    if not usuario.mfa_segredo:
        usuario.mfa_segredo = cifrar_texto(pyotp.random_base32())
        usuario.mfa_ultimo_passo = None
    return _segredo(usuario)


def uri_provisionamento(usuario, segredo):
    return pyotp.TOTP(segredo, interval=PERIODO).provisioning_uri(name=usuario.email, issuer_name=EMISSOR)


def qr_code_svg(uri):
    return Markup(segno.make(uri, error="m").svg_inline(scale=5, border=2, dark="#0B2A4A"))


def formatar_segredo(segredo):
    return " ".join(segredo[i:i + 4] for i in range(0, len(segredo), 4))


def ativar(usuario):
    usuario.mfa_ativo = True
    return gerar_codigos_recuperacao(usuario)


def redefinir(usuario):
    usuario.mfa_ativo = False
    usuario.mfa_segredo = None
    usuario.mfa_ultimo_passo = None
    usuario.mfa_codigos_recuperacao = None


def _segredo(usuario):
    return decifrar_texto(usuario.mfa_segredo)


def _so_digitos(codigo):
    return "".join(c for c in (codigo or "") if c.isdigit())


def parece_codigo_totp(codigo):
    limpo = (codigo or "").replace(" ", "").strip()
    return len(limpo) == 6 and limpo.isdigit()


def verificar_totp(usuario, codigo, agora=None):
    if not usuario.mfa_segredo or not parece_codigo_totp(codigo):
        return False
    codigo = _so_digitos(codigo)
    totp = pyotp.TOTP(_segredo(usuario), interval=PERIODO)
    passo_atual = int((agora if agora is not None else time.time()) // PERIODO)
    ultimo = usuario.mfa_ultimo_passo
    for deslocamento in range(-TOLERANCIA_PASSOS, TOLERANCIA_PASSOS + 1):
        passo = passo_atual + deslocamento
        if ultimo is not None and passo <= ultimo:
            continue
        if hmac.compare_digest(totp.at(passo * PERIODO), codigo):
            usuario.mfa_ultimo_passo = passo
            return True
    return False


def _normalizar_recuperacao(codigo):
    return "".join(c for c in (codigo or "").upper() if c.isalnum())


def _hash_recuperacao(codigo):
    return hashlib.sha256(_normalizar_recuperacao(codigo).encode("ascii", "ignore")).hexdigest()


def gerar_codigos_recuperacao(usuario):
    codigos = []
    for _ in range(QTD_CODIGOS_RECUPERACAO):
        bruto = "".join(secrets.choice(ALFABETO_RECUPERACAO) for _ in range(8))
        codigos.append(f"{bruto[:4]}-{bruto[4:]}")
    usuario.mfa_codigos_recuperacao = json.dumps([_hash_recuperacao(c) for c in codigos])
    return codigos


def codigos_restantes(usuario):
    return len(json.loads(usuario.mfa_codigos_recuperacao or "[]"))


def usar_codigo_recuperacao(usuario, codigo):
    if len(_normalizar_recuperacao(codigo)) != 8:
        return False
    alvo = _hash_recuperacao(codigo)
    restantes = json.loads(usuario.mfa_codigos_recuperacao or "[]")
    encontrado = None
    for h in restantes:
        if hmac.compare_digest(h, alvo):
            encontrado = h
    if encontrado is None:
        return False
    restantes.remove(encontrado)
    usuario.mfa_codigos_recuperacao = json.dumps(restantes)
    return True
