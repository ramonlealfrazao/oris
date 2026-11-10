"""Serviço central de auditoria (Fase 8)."""

import json

from flask import has_request_context, request

from app.extensions import db
from app.models import Auditoria


def registrar_auditoria(
    usuario,
    acao,
    tabela=None,
    registro_id=None,
    descricao=None,
    valor_anterior=None,
    valor_novo=None,
    resultado="SUCESSO",
    origem_ip=None,
    identificador_tentado=None,
):
    """Cria (sem commitar) um registro de Auditoria.

    `usuario` pode ser None (tentativa de login de quem nao existe). A origem (IP)
    vem da requisicao em andamento, se nao for informada.
    """
    if origem_ip is None and has_request_context():
        origem_ip = request.remote_addr
    auditoria = Auditoria(
        usuario_id=usuario.id if usuario is not None else None,
        resultado=resultado,
        origem_ip=(origem_ip or None) and str(origem_ip)[:45],
        identificador_tentado=(identificador_tentado[:255] if identificador_tentado else None),
        acao=acao,
        tabela=tabela,
        registro_id=registro_id,
        descricao=descricao,
        valor_anterior=json.dumps(valor_anterior, ensure_ascii=False) if valor_anterior else None,
        valor_novo=json.dumps(valor_novo, ensure_ascii=False) if valor_novo else None,
    )
    db.session.add(auditoria)
    return auditoria
