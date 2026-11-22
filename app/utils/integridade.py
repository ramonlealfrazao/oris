import base64
import hashlib

TAMANHO_BLOCO = 1024 * 1024


def sha256_hex(dados: bytes) -> str:
    return hashlib.sha256(dados).hexdigest()


def sha256_base64(dados: bytes) -> str:
    return base64.b64encode(hashlib.sha256(dados).digest()).decode("ascii")


def sha256_arquivo(caminho: str) -> str:
    resumo = hashlib.sha256()
    with open(caminho, "rb") as arquivo:
        for bloco in iter(lambda: arquivo.read(TAMANHO_BLOCO), b""):
            resumo.update(bloco)
    return resumo.hexdigest()
