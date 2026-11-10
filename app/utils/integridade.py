"""Verificação de integridade com SHA-256 (hash genérico, não é para senhas).

Senhas continuam com bcrypt (app/utils/security.py). Aqui o objetivo é outro:
permitir confirmar que um arquivo recebido ou enviado não foi corrompido nem
adulterado no caminho (planilhas importadas e relatórios exportados).
"""

import base64
import hashlib

TAMANHO_BLOCO = 1024 * 1024  # 1 MiB: arquivos grandes não vão inteiros para a memória


def sha256_hex(dados: bytes) -> str:
    """Hash SHA-256 em hexadecimal (64 caracteres), o formato de `sha256sum`."""
    return hashlib.sha256(dados).hexdigest()


def sha256_base64(dados: bytes) -> str:
    """Hash SHA-256 em base64, o formato que o Amazon S3 usa em ChecksumSHA256."""
    return base64.b64encode(hashlib.sha256(dados).digest()).decode("ascii")


def sha256_arquivo(caminho: str) -> str:
    """Hash SHA-256 (hex) de um arquivo em disco, lido em blocos."""
    resumo = hashlib.sha256()
    with open(caminho, "rb") as arquivo:
        for bloco in iter(lambda: arquivo.read(TAMANHO_BLOCO), b""):
            resumo.update(bloco)
    return resumo.hexdigest()
