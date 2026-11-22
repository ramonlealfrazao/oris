"""Direitos do titular de dados (LGPD, art. 18) e dados de transparência."""

import json
import secrets
from datetime import timedelta

from flask import current_app

from app.extensions import db
from app.models import (
    Auditoria,
    PerfilUsuario,
    SolicitacaoTitular,
    StatusSolicitacaoTitular,
    TipoSolicitacaoTitular,
    Usuario,
)
from app.services.auditoria_service import registrar_auditoria
from app.utils.datetime_utils import utcnow
from app.utils.security import gerar_hash_senha

LIMITE_REGISTROS_NO_RELATORIO = 200

OPERACOES_TRATAMENTO = [
    {
        "dado": "Nome, e-mail, perfil e situação do usuário",
        "titular": "Usuários do sistema",
        "finalidade": "Identificar a pessoa e controlar o que ela pode acessar",
        "onde": "Tabela usuarios",
        "retencao": "Enquanto a conta existir; contas desativadas não são apagadas pela aplicação",
        "compartilhamento": "Não é compartilhado",
    },
    {
        "dado": "Hash bcrypt da senha",
        "titular": "Usuários com conta local",
        "finalidade": "Autenticar o acesso",
        "onde": "Tabela usuarios (nunca a senha em texto)",
        "retencao": "Enquanto a conta existir",
        "compartilhamento": "Não é compartilhado",
    },
    {
        "dado": "Origem da conta e grupos do diretório (LDAP ou OIDC)",
        "titular": "Usuários provisionados pelo diretório",
        "finalidade": "Definir o perfil de acesso a partir do grupo",
        "onde": "Tabelas usuarios e grupos",
        "retencao": "Enquanto a conta existir",
        "compartilhamento": "Recebido do diretório da organização",
    },
    {
        "dado": "Ações realizadas, IP de origem e resultado",
        "titular": "Usuários do sistema",
        "finalidade": "Auditoria, segurança e responsabilização",
        "onde": "Tabela auditorias (não pode ser alterada nem apagada pela aplicação)",
        "retencao": "Mínimo de {anos} ano(s)",
        "compartilhamento": "Não é compartilhado",
    },
    {
        "dado": "E-mail digitado em tentativas de login que falham",
        "titular": "Quem tenta acessar o sistema",
        "finalidade": "Detectar tentativas de acesso indevido",
        "onde": "Tabela auditorias",
        "retencao": "Mesma da trilha de auditoria",
        "compartilhamento": "Não é compartilhado",
    },
    {
        "dado": "Pedidos feitos pelo titular e respostas",
        "titular": "Usuários do sistema",
        "finalidade": "Atender os direitos do art. 18 da LGPD e comprovar o atendimento",
        "onde": "Tabela solicitacoes_titular",
        "retencao": "Mesma da trilha de auditoria",
        "compartilhamento": "Não é compartilhado",
    },
]

OPERADORES = [
    {
        "nome": "Amazon Web Services",
        "papel": "Hospedagem do servidor, do banco de dados (disco criptografado) e do armazenamento de relatórios (S3).",
    },
    {
        "nome": "Provedor de identidade da organização (LDAP e OIDC)",
        "papel": "Informa quem é o usuário e a que grupo pertence, quando o acesso é institucional.",
    },
]

DIREITOS_TITULAR = [
    ("ACESSO", "Confirmar que há tratamento e acessar os dados", "Em Meus dados, a tela mostra o cadastro, os grupos e as ações registradas em seu nome."),
    ("CORRECAO", "Corrigir dados incompletos, inexatos ou desatualizados", "Pedido tratado pelo Administrador, que corrige o cadastro."),
    ("ELIMINACAO", "Anonimizar ou eliminar dados desnecessários", "O Administrador anonimiza a conta. A trilha de auditoria é mantida pelo prazo legal."),
    ("PORTABILIDADE", "Receber os dados em formato estruturado", "Botão Exportar meus dados baixa um arquivo JSON na hora."),
    ("COMPARTILHAMENTO", "Saber com quem os dados são compartilhados", "Lista de operadores na página de privacidade."),
    ("OPOSICAO", "Opor-se a um tratamento", "Pedido analisado e respondido pelo Administrador."),
]


def retencao_anos():
    return current_app.config.get("LGPD_RETENCAO_AUDITORIA_ANOS", 1)


def operacoes_tratamento():
    anos = retencao_anos()
    return [{**op, "retencao": op["retencao"].format(anos=anos)} for op in OPERACOES_TRATAMENTO]


def dados_de_transparencia():
    cfg = current_app.config
    return {
        "controlador": cfg.get("LGPD_CONTROLADOR"),
        "encarregado_nome": cfg.get("LGPD_ENCARREGADO_NOME"),
        "encarregado_email": cfg.get("LGPD_ENCARREGADO_EMAIL"),
        "base_legal": cfg.get("LGPD_BASE_LEGAL"),
        "retencao_anos": retencao_anos(),
        "prazo_resposta_dias": cfg.get("LGPD_PRAZO_RESPOSTA_DIAS", 15),
        "operacoes": operacoes_tratamento(),
        "operadores": OPERADORES,
        "direitos": DIREITOS_TITULAR,
    }


def _iso(valor):
    return valor.isoformat() if valor else None


def dados_do_titular(usuario):
    registros = (
        Auditoria.query.filter_by(usuario_id=usuario.id)
        .order_by(Auditoria.data_hora.desc())
        .limit(LIMITE_REGISTROS_NO_RELATORIO)
        .all()
    )
    total_registros = Auditoria.query.filter_by(usuario_id=usuario.id).count()
    solicitacoes = (
        SolicitacaoTitular.query.filter_by(usuario_id=usuario.id)
        .order_by(SolicitacaoTitular.criada_em.desc())
        .all()
    )
    return {
        "cadastro": {
            "nome": usuario.nome,
            "email": usuario.email,
            "perfil": usuario.perfil.value,
            "ativo": usuario.ativo,
            "origem": usuario.origem.value,
            "grupos": sorted(g.nome for g in usuario.grupos),
            # Só a situação: o segredo TOTP e os códigos de recuperação nunca são exportados.
            "mfa_ativo": bool(usuario.mfa_ativo),
            "criado_em": _iso(usuario.created_at),
            "atualizado_em": _iso(usuario.updated_at),
        },
        "auditoria": {
            "total_de_registros": total_registros,
            "registros_listados": len(registros),
            "registros": [
                {
                    "data_hora": _iso(r.data_hora),
                    "acao": r.acao,
                    "tabela": r.tabela,
                    "resultado": r.resultado,
                    "origem_ip": r.origem_ip,
                    "descricao": r.descricao,
                }
                for r in registros
            ],
        },
        "solicitacoes": [
            {
                "id": s.id,
                "tipo": s.tipo.value,
                "status": s.status.value,
                "criada_em": _iso(s.criada_em),
                "prazo_resposta": _iso(s.prazo_resposta),
                "respondida_em": _iso(s.respondida_em),
                "resposta": s.resposta,
            }
            for s in solicitacoes
        ],
    }


def exportar_json(usuario):
    corpo = {"exportado_em": _iso(utcnow()), "titular": dados_do_titular(usuario)}
    return json.dumps(corpo, ensure_ascii=False, indent=2)


def registrar_solicitacao(usuario, tipo, descricao):
    dias = current_app.config.get("LGPD_PRAZO_RESPOSTA_DIAS", 15)
    agora = utcnow()
    solicitacao = SolicitacaoTitular(
        usuario_id=usuario.id,
        tipo=TipoSolicitacaoTitular(tipo),
        descricao=descricao.strip(),
        prazo_resposta=agora + timedelta(days=dias),
    )
    db.session.add(solicitacao)
    db.session.flush()
    registrar_auditoria(
        usuario=usuario,
        acao="LGPD_SOLICITACAO",
        tabela="solicitacoes_titular",
        registro_id=solicitacao.id,
        descricao=f"Pedido de titular registrado: {solicitacao.tipo.value}.",
    )
    db.session.commit()
    return solicitacao


def responder_solicitacao(solicitacao, administrador, decisao, resposta):
    solicitacao.status = StatusSolicitacaoTitular(decisao)
    solicitacao.resposta = resposta.strip()
    solicitacao.respondida_em = utcnow()
    solicitacao.respondida_por = administrador.id
    registrar_auditoria(
        usuario=administrador,
        acao="LGPD_RESPOSTA",
        tabela="solicitacoes_titular",
        registro_id=solicitacao.id,
        descricao=f"Pedido #{solicitacao.id} ({solicitacao.tipo.value}) respondido: {solicitacao.status.value}.",
    )
    db.session.commit()


def e_ultimo_administrador_ativo(usuario):
    if usuario.perfil != PerfilUsuario.ADMINISTRADOR or not usuario.ativo:
        return False
    outros = Usuario.query.filter(
        Usuario.perfil == PerfilUsuario.ADMINISTRADOR, Usuario.ativo.is_(True), Usuario.id != usuario.id
    ).count()
    return outros == 0


def anonimizar_titular(usuario, administrador):
    """Remove os dados pessoais da conta; a trilha de auditoria permanece ligada ao id."""
    if e_ultimo_administrador_ativo(usuario):
        raise ValueError("Esta conta é a do único Administrador ativo e não pode ser anonimizada.")
    nome_anterior, email_anterior = usuario.nome, usuario.email
    usuario.nome = f"Usuário anonimizado {usuario.id}"
    usuario.email = f"anonimizado-{usuario.id}@anonimizado.invalid"
    usuario.senha_hash = gerar_hash_senha(secrets.token_urlsafe(32))
    usuario.identificador_externo = None
    usuario.grupos = []
    usuario.ativo = False
    # O segredo do MFA e os códigos de recuperação também são dados da pessoa.
    usuario.mfa_ativo = False
    usuario.mfa_segredo = None
    usuario.mfa_ultimo_passo = None
    usuario.mfa_codigos_recuperacao = None
    registrar_auditoria(
        usuario=administrador,
        acao="LGPD_ANONIMIZACAO",
        tabela="usuarios",
        registro_id=usuario.id,
        descricao=f"Conta #{usuario.id} anonimizada a pedido do titular.",
    )
    db.session.commit()
    return nome_anterior, email_anterior


def solicitacao_vencida(solicitacao):
    return solicitacao.status == StatusSolicitacaoTitular.ABERTA and solicitacao.prazo_resposta < utcnow()


def resumo_conformidade():
    """Números usados na área de governança."""
    agora = utcnow()
    limite = agora - timedelta(days=365 * retencao_anos())
    abertas = SolicitacaoTitular.query.filter_by(status=StatusSolicitacaoTitular.ABERTA)
    return {
        "solicitacoes_abertas": abertas.count(),
        "solicitacoes_vencidas": abertas.filter(SolicitacaoTitular.prazo_resposta < agora).count(),
        "solicitacoes_total": SolicitacaoTitular.query.count(),
        "auditoria_total": Auditoria.query.count(),
        "auditoria_alem_da_retencao": Auditoria.query.filter(Auditoria.data_hora < limite).count(),
        "falhas_30_dias": Auditoria.query.filter(
            Auditoria.resultado == "FALHA", Auditoria.data_hora >= agora - timedelta(days=30)
        ).count(),
    }
