import bcrypt


def gerar_hash_senha(senha: str) -> str:
    if not senha:
        raise ValueError("A senha não pode ser vazia.")

    senha_bytes = senha.encode("utf-8")
    hash_bytes = bcrypt.hashpw(senha_bytes, bcrypt.gensalt())
    return hash_bytes.decode("utf-8")


def verificar_senha(senha: str, senha_hash: str) -> bool:
    if not senha or not senha_hash:
        return False

    try:
        return bcrypt.checkpw(senha.encode("utf-8"), senha_hash.encode("utf-8"))
    except (ValueError, TypeError):
        return False
