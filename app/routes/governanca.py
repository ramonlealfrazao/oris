from flask import Blueprint, abort, render_template

from app.models import PerfilUsuario
from app.services import governanca_dados as dados
from app.services import governanca_service as servico
from app.utils.decorators import roles_required

PERFIS_GOVERNANCA = (
    PerfilUsuario.ADMINISTRADOR.value,
    PerfilUsuario.GESTAO_INFORMACAO.value,
    PerfilUsuario.GESTOR.value,
)

governanca_bp = Blueprint("governanca", __name__, url_prefix="/governanca")

SECOES = {
    "riscos": "Riscos e mitigação",
    "raci": "Matriz RACI",
    "cobit": "COBIT 2019",
    "auditoria": "Auditoria",
    "etica": "Ética",
    "nuvem": "Nuvem",
}


def _contexto(chave):
    if chave == "riscos":
        return {
            "riscos": servico.riscos_com_nivel(),
            "mapa": servico.mapa_de_calor(),
            "escala": dados.ESCALA_RISCO,
            "mitigacao": dados.MITIGACAO,
        }
    if chave == "raci":
        return {"colunas": dados.RACI_COLUNAS, "linhas": dados.RACI, "legenda": dados.RACI_LEGENDA}
    if chave == "cobit":
        return {"objetivos": dados.COBIT, "nota": dados.COBIT_NOTA}
    if chave == "auditoria":
        return {
            "plano": dados.PLANO_AUDITORIA,
            "checklist": dados.CHECKLIST_AUDITORIA,
            "atalhos": dados.ATALHOS_AUDITORIA,
            "elementos": dados.TRILHA_ELEMENTOS,
            "integridade": dados.TRILHA_INTEGRIDADE,
        }
    if chave == "etica":
        return {"dilemas": dados.DILEMAS}
    return {"intro": dados.NUVEM_INTRO, "camadas": dados.NUVEM, "nota": dados.NUVEM_NOTA}


@governanca_bp.route("")
@roles_required(*PERFIS_GOVERNANCA)
def index():
    return render_template(
        "governanca/index.html",
        principios=dados.PRINCIPIOS,
        indicadores=servico.indicadores(),
        secoes=SECOES,
    )


@governanca_bp.route("/<chave>")
@roles_required(*PERFIS_GOVERNANCA)
def secao(chave):
    if chave not in SECOES:
        abort(404)
    return render_template(
        "governanca/secao.html",
        chave=chave,
        titulo=SECOES[chave],
        secoes=SECOES,
        **_contexto(chave),
    )
