"""Autenticação multifator (MFA) do login local com TOTP (RFC 6238).

Compatível com Google Authenticator, Microsoft Authenticator, Authy etc.

Decisões de segurança:
- o segredo TOTP fica cifrado no banco com a DATA_ENCRYPTION_KEY (Fernet);
- cada código só vale uma vez: guardamos o último intervalo de 30 s aceito (anti-replay);
- aceitamos o intervalo atual e um de cada lado (tolerância de relógio de ±30 s);
- códigos de recuperação são aleatórios, mostrados uma única vez e guardados só como
  SHA-256 (são de alta entropia, então um hash rápido é adequado); cada um vale uma vez;
- comparação em tempo constante.

Contas LDAP/OIDC não passam por aqui: o segundo fator delas é feito no provedor (Keycloak).
"""

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
# Sem 0/O/1/I/L para não confundir quem digita o código.
ALFABETO_RECUPERACAO = "ABCDEFGHJKMNPQRSTUVWXYZ23456789"


def mfa_obrigatorio():
    return bool(current_app.config.get("MFA_OBRIGATORIO", True))


# --------------------------------------------------------------------------
# Cadastro
# --------------------------------------------------------------------------
def preparar_cadastro(usuario):
    """Garante um segredo pendente para o usuário (sem ativar o MFA) e o devolve.

    Recarregar a página não troca o segredo, para o QR já lido continuar valendo.
    """
    if usuario.mfa_ativo:
        raise ValueError("O MFA deste usuário já está ativo.")
    if not usuario.mfa_segredo:
        usuario.mfa_segredo = cifrar_texto(pyotp.random_base32())
        usuario.mfa_ultimo_passo = None
    return _segredo(usuario)


def uri_provisionamento(usuario, segredo):
    return pyotp.TOTP(segredo, interval=PERIODO).provisioning_uri(name=usuario.email, issuer_name=EMISSOR)


def qr_code_svg(uri):
    """QR code do cadastro como SVG inline.

    O SVG é gerado pelo segno só com caminhos geométricos (o texto da URI não aparece
    como texto no SVG), por isso é seguro marcá-lo como Markup.
    """
    return Markup(segno.make(uri, error="m").svg_inline(scale=5, border=2, dark="#0B2A4A"))


def formatar_segredo(segredo):
    """Segredo em grupos de 4 para quem preferir digitar no aplicativo."""
    return " ".join(segredo[i:i + 4] for i in range(0, len(segredo), 4))


def ativar(usuario):
    """Ativa o MFA e devolve os códigos de recuperação em texto (mostrar UMA vez)."""
    usuario.mfa_ativo = True
    return gerar_codigos_recuperacao(usuario)


def redefinir(usuario):
    """Apaga o MFA do usuário (perdeu o celular): no próximo login ele cadastra de novo."""
    usuario.mfa_ativo = False
    usuario.mfa_segredo = None
    usuario.mfa_ultimo_passo = None
    usuario.mfa_codigos_recuperacao = None


# --------------------------------------------------------------------------
# Verificação
# --------------------------------------------------------------------------
def _segredo(usuario):
    return decifrar_texto(usuario.mfa_segredo)


def _so_digitos(codigo):
    return "".join(c for c in (codigo or "") if c.isdigit())


def parece_codigo_totp(codigo):
    limpo = (codigo or "").replace(" ", "").strip()
    return len(limpo) == 6 and limpo.isdigit()


def verificar_totp(usuario, codigo, agora=None):
    """True se o código de 6 dígitos for válido e ainda não tiver sido usado."""
    if not usuario.mfa_segredo or not parece_codigo_totp(codigo):
        return False
    codigo = _so_digitos(codigo)
    totp = pyotp.TOTP(_segredo(usuario), interval=PERIODO)
    passo_atual = int((agora if agora is not None else time.time()) // PERIODO)
    ultimo = usuario.mfa_ultimo_passo
    for deslocamento in range(-TOLERANCIA_PASSOS, TOLERANCIA_PASSOS + 1):
        passo = passo_atual + deslocamento
        if ultimo is not None and passo <= ultimo:
            continue  # código já usado (ou mais antigo que o último aceito)
        if hmac.compare_digest(totp.at(passo * PERIODO), codigo):
            usuario.mfa_ultimo_passo = passo
            return True
    return False


# --------------------------------------------------------------------------
# Códigos de recuperação
# --------------------------------------------------------------------------
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
    """True (e consome o código) se for um código de recuperação válido e não usado."""
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
