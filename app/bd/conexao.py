from contextlib import contextmanager

import pymysql
from flask import current_app
from pymysql.cursors import DictCursor


class ErroBanco(Exception):
    pass


def abrir_conexao():
    cfg = current_app.config
    return pymysql.connect(
        host=cfg.get("DB_HOST", "localhost"),
        port=int(cfg.get("DB_PORT", 3306)),
        user=cfg.get("DB_USER"),
        password=cfg.get("DB_PASSWORD", ""),
        database=cfg.get("DB_NAME"),
        charset="utf8mb4",
        cursorclass=DictCursor,
        autocommit=False,
    )


@contextmanager
def transacao():
    conn = abrir_conexao()
    try:
        with conn.cursor() as cur:
            yield cur
        conn.commit()
    except pymysql.err.IntegrityError as erro:
        conn.rollback()
        raise ErroBanco(_traduzir_erro_integridade(erro)) from erro
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def consultar(sql, parametros=None):
    conn = abrir_conexao()
    try:
        with conn.cursor() as cur:
            cur.execute(sql, parametros)
            linhas = cur.fetchall()
            colunas = [descricao[0] for descricao in (cur.description or [])]
        return colunas, list(linhas)
    finally:
        conn.close()


def consultar_um(sql, parametros=None):
    _, linhas = consultar(sql, parametros)
    return linhas[0] if linhas else None


def _traduzir_erro_integridade(erro):
    codigo = erro.args[0] if erro.args else None
    if codigo == 1451:
        return (
            "Não é possível excluir: existem registros vinculados a este "
            "item (restrição de chave estrangeira)."
        )
    if codigo == 1452:
        return "O registro relacionado informado não existe."
    if codigo == 1062:
        return "Já existe um registro com esse valor único."
    return "O banco recusou a operação por violar uma restrição de integridade."
