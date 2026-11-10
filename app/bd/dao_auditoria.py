"""DAO da trilha de auditoria - SQL explícito."""

import json

from flask import has_request_context, request

SQL_INSERIR_AUDITORIA = """
    INSERT INTO auditorias
        (usuario_id, acao, tabela, registro_id, descricao,
         valor_anterior, valor_novo, origem_ip, resultado, data_hora)
    VALUES
        (%s, %s, %s, %s, %s, %s, %s, %s, 'SUCESSO', UTC_TIMESTAMP())
"""

SQL_DEFINIR_USUARIO = "SET @oris_usuario_id = %s, @oris_origem_ip = %s"


def _ip_atual():
    """IP da requisicao em andamento (None fora de uma requisicao, ex.: scripts)."""
    if has_request_context() and request.remote_addr:
        return str(request.remote_addr)[:45]
    return None


def _json(valor):
    if not valor:
        return None
    return json.dumps(valor, ensure_ascii=False, default=str)


def definir_usuario(cur, usuario_id):
    """Informa aos triggers do MySQL quem está operando e de onde (variáveis de
    sessão @oris_usuario_id e @oris_origem_ip, lidas por trg_equipamentos_au e
    trg_unidades_au)."""
    cur.execute(SQL_DEFINIR_USUARIO, (usuario_id, _ip_atual()))


def registrar(cur, usuario_id, acao, tabela, registro_id, descricao,
              valor_anterior=None, valor_novo=None):
    cur.execute(
        SQL_INSERIR_AUDITORIA,
        (usuario_id, acao, tabela, registro_id, descricao,
         _json(valor_anterior), _json(valor_novo), _ip_atual()),
    )
