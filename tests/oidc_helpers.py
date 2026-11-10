"""Apoio aos testes de OIDC: chaves RSA de teste, JWKS e assinatura de id_token.

Nada aqui fala com provedor real. As chaves são geradas na hora, só para os
testes, e o JWKS é servido por um `_http_get_json` falso.
"""

import json

import jwt
from cryptography.hazmat.primitives.asymmetric import rsa

KID = "chave-teste-1"


def gerar_chave_privada():
    return rsa.generate_private_key(public_exponent=65537, key_size=2048)


def jwks_de(chave_privada, kid=KID):
    """JWKS (conjunto de chaves públicas) correspondente à chave privada."""
    jwk = json.loads(jwt.algorithms.RSAAlgorithm.to_jwk(chave_privada.public_key()))
    jwk.update({"kid": kid, "use": "sig", "alg": "RS256"})
    return {"keys": [jwk]}


def assinar(claims, chave_privada, kid=KID, alg="RS256"):
    cabecalho = {"kid": kid} if kid else {}
    return jwt.encode(claims, chave_privada, algorithm=alg, headers=cabecalho)
