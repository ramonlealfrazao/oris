"""Indicadores ao vivo e cálculos da área de Governança."""

from sqlalchemy import case, func

from app.extensions import db
from app.models import (
    Alteracao,
    Equipamento,
    Manutencao,
    OrigemDiretorio,
    PerfilUsuario,
    Servico,
    SituacaoAtivoInativo,
    SituacaoUnidade,
    StatusAlteracao,
    Unidade,
    Usuario,
)
from app.services import governanca_dados as dados
from app.services.lgpd_service import resumo_conformidade

LIMITE_CRITICA = 50
LIMITE_ATENCAO = 80


def nivel_risco(p, i):
    produto = p * i
    if produto >= 15:
        return produto, "alto"
    if produto >= 6:
        return produto, "medio"
    return produto, "baixo"


def riscos_com_nivel():
    lista = []
    for r in dados.RISCOS:
        produto, classe = nivel_risco(r["p"], r["i"])
        lista.append({**r, "nivel": produto, "classe": classe})
    return sorted(lista, key=lambda r: (-r["nivel"], int(r["id"][1:])))


def mapa_de_calor():
    """Matriz 5x5 (impacto de 5 a 1, probabilidade de 1 a 5) com os ids dos riscos."""
    linhas = []
    for impacto in range(5, 0, -1):
        celulas = []
        for prob in range(1, 6):
            ids = [r["id"] for r in dados.RISCOS if r["p"] == prob and r["i"] == impacto]
            celulas.append({"ids": ids, "classe": nivel_risco(prob, impacto)[1]})
        linhas.append({"impacto": impacto, "celulas": celulas})
    return linhas


def _classificar_unidades():
    total = func.count(Equipamento.id)
    ativos = func.sum(case((Equipamento.situacao == SituacaoAtivoInativo.ATIVO, 1), else_=0))
    linhas = (
        db.session.query(Equipamento.unidade_id, total, ativos)
        .filter(Equipamento.unidade_id.isnot(None))
        .group_by(Equipamento.unidade_id)
        .all()
    )
    criticas = atencao = 0
    for _, n, ok in linhas:
        pct = 100 * int(ok or 0) / n
        if pct < LIMITE_CRITICA:
            criticas += 1
        elif pct < LIMITE_ATENCAO:
            atencao += 1
    return criticas, atencao


def _soma_custo(situacao):
    valor = (
        db.session.query(func.coalesce(func.sum(Manutencao.custo), 0))
        .filter(Manutencao.situacao == situacao)
        .scalar()
    )
    return float(valor or 0)


def indicadores():
    """Números por princípio da ISO 38500, calculados na hora."""
    por_perfil = {
        perfil: Usuario.query.filter_by(perfil=perfil, ativo=True).count() for perfil in PerfilUsuario
    }
    ativos_total = Usuario.query.filter_by(ativo=True).count()
    diretorio = Usuario.query.filter(Usuario.origem != OrigemDiretorio.LOCAL, Usuario.ativo.is_(True)).count()

    equip_total = Equipamento.query.count()
    equip_ativos = Equipamento.query.filter_by(situacao=SituacaoAtivoInativo.ATIVO).count()
    equip_manut = Equipamento.query.filter_by(situacao=SituacaoAtivoInativo.MANUTENCAO).count()
    pct_operantes = round(100 * equip_ativos / equip_total, 1) if equip_total else None
    criticas, atencao = _classificar_unidades()

    conf = resumo_conformidade()

    aprovadas = Alteracao.query.filter_by(status=StatusAlteracao.APROVADO).count()
    rejeitadas = Alteracao.query.filter_by(status=StatusAlteracao.REJEITADO).count()
    decididas = aprovadas + rejeitadas
    taxa_rejeicao = round(100 * rejeitadas / decididas, 1) if decididas else None

    def pct(valor):
        return "sem dados" if valor is None else f"{valor}%".replace(".", ",")

    def dinheiro(valor):
        return "R$ " + f"{valor:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")

    return {
        "responsabilidade": [
            ("Usuários ativos", ativos_total),
            ("Administradores", por_perfil[PerfilUsuario.ADMINISTRADOR]),
            ("Gestão da Informação", por_perfil[PerfilUsuario.GESTAO_INFORMACAO]),
            ("Resp. Saúde Bucal", por_perfil[PerfilUsuario.RESPONSAVEL_SAUDE_BUCAL]),
            ("Gestores", por_perfil[PerfilUsuario.GESTOR]),
            ("Contas do diretório", diretorio),
        ],
        "estrategia": [
            ("Unidades ativas", f"{Unidade.query.filter_by(situacao=SituacaoUnidade.ATIVA).count()} de {Unidade.query.count()}"),
            ("Serviços ativos", f"{Servico.query.filter_by(situacao=SituacaoAtivoInativo.ATIVO).count()} de {Servico.query.count()}"),
            ("Equipamentos cadastrados", equip_total),
        ],
        "aquisicao": [
            ("Equipamentos em manutenção", equip_manut),
            ("Manutenções abertas", Manutencao.query.filter_by(situacao="ABERTA").count()),
            ("Custo das abertas", dinheiro(_soma_custo("ABERTA"))),
            ("Custo das concluídas", dinheiro(_soma_custo("CONCLUIDA"))),
        ],
        "desempenho": [
            ("Equipamentos operantes", pct(pct_operantes)),
            ("Unidades em estado crítico", criticas),
            ("Unidades em atenção", atencao),
        ],
        "conformidade": [
            ("Registros na trilha", conf["auditoria_total"]),
            ("Falhas nos últimos 30 dias", conf["falhas_30_dias"]),
            ("Pedidos de titulares abertos", conf["solicitacoes_abertas"]),
            ("Pedidos vencidos", conf["solicitacoes_vencidas"]),
            ("Registros além da retenção", conf["auditoria_alem_da_retencao"]),
        ],
        "comportamento": [
            ("Alterações pendentes", Alteracao.query.filter_by(status=StatusAlteracao.PENDENTE).count()),
            ("Aprovadas", aprovadas),
            ("Rejeitadas", rejeitadas),
            ("Taxa de rejeição", pct(taxa_rejeicao)),
        ],
    }
