from flask import Blueprint, Response, abort, current_app, flash, redirect, render_template, session, url_for

from app.extensions import db
from app.models import PerfilUsuario
from app.services.armazenamento_service import (
    ArmazenamentoError,
    enviar_relatorio,
    gerar_url_download,
    s3_configurado,
)
from app.services.auditoria_service import registrar_auditoria
from app.services.relatorio_service import (
    ENTIDADES_RELATORIO,
    gerar_csv,
    gerar_csv_historico,
    historico_exportacoes,
)
from app.utils.integridade import sha256_hex
from app.utils.decorators import login_required, roles_required, usuario_atual

relatorios_bp = Blueprint("relatorios", __name__, url_prefix="/relatorios")

PERFIS_QUE_EXPORTAM = (
    PerfilUsuario.ADMINISTRADOR.value,
    PerfilUsuario.GESTAO_INFORMACAO.value,
)

TITULOS = {"unidades": "Unidades de Saúde", "servicos": "Serviços", "equipamentos": "Equipamentos"}


def _validar_entidade_ou_404(entidade):
    if entidade not in ENTIDADES_RELATORIO:
        abort(404)


def _montar_cartao_exportacao(dados):
    if not dados:
        return None
    try:
        link = gerar_url_download(dados["chave"])
    except ArmazenamentoError:
        link = None
    return {
        "titulo": TITULOS.get(dados["entidade"], dados["entidade"]),
        "arquivo": dados["chave"].rsplit("/", 1)[-1],
        "bucket": current_app.config.get("S3_BUCKET"),
        "chave": dados["chave"],
        "sha256": dados["sha256"],
        "minutos": max(1, int(current_app.config.get("S3_URL_EXPIRA_SEGUNDOS", 900)) // 60),
        "link": link,
    }


@relatorios_bp.route("")
@login_required
def index():
    usuario = usuario_atual()
    exportacao = _montar_cartao_exportacao(session.pop("ultima_exportacao", None))
    return render_template(
        "relatorios/index.html",
        exportacao=exportacao,
        historico=historico_exportacoes(limite=20) if usuario.perfil.value in PERFIS_QUE_EXPORTAM else [],
        entidades=ENTIDADES_RELATORIO,
        titulos=TITULOS,
        pode_exportar=usuario.perfil.value in PERFIS_QUE_EXPORTAM,
        s3_ativo=s3_configurado(),
    )


@relatorios_bp.route("/<entidade>/baixar")
@login_required
def baixar(entidade):
    _validar_entidade_ou_404(entidade)
    nome_arquivo, conteudo = gerar_csv(entidade)
    hash_conteudo = sha256_hex(conteudo)

    registrar_auditoria(
        usuario=usuario_atual(),
        acao="BAIXAR_RELATORIO",
        tabela=entidade,
        descricao=f"Download do relatório de {entidade} ({nome_arquivo}), SHA-256 {hash_conteudo}.",
    )
    db.session.commit()

    return Response(
        conteudo,
        mimetype="text/csv",
        headers={
            "Content-Disposition": f"attachment; filename={nome_arquivo}",
            "X-Content-SHA256": hash_conteudo,
        },
    )


@relatorios_bp.route("/historico.csv")
@roles_required(*PERFIS_QUE_EXPORTAM)
def baixar_historico():
    nome_arquivo, conteudo = gerar_csv_historico()
    registrar_auditoria(
        usuario=usuario_atual(),
        acao="BAIXAR_RELATORIO",
        tabela="exportacoes",
        descricao=f"Download do histórico de exportações ({nome_arquivo}), SHA-256 {sha256_hex(conteudo)}.",
    )
    db.session.commit()
    return Response(
        conteudo,
        mimetype="text/csv",
        headers={"Content-Disposition": f"attachment; filename={nome_arquivo}"},
    )


@relatorios_bp.route("/<entidade>/exportar-s3", methods=["POST"])
@roles_required(*PERFIS_QUE_EXPORTAM)
def exportar_s3(entidade):
    _validar_entidade_ou_404(entidade)

    if not s3_configurado():
        flash("A exportação para a nuvem não está configurada neste ambiente.", "warning")
        return redirect(url_for("relatorios.index"))

    _, conteudo = gerar_csv(entidade)
    hash_conteudo = sha256_hex(conteudo)
    try:
        chave = enviar_relatorio(conteudo, entidade)
        gerar_url_download(chave)
    except ArmazenamentoError as erro:
        flash(str(erro), "danger")
        return redirect(url_for("relatorios.index"))

    registrar_auditoria(
        usuario=usuario_atual(),
        acao="EXPORTAR_RELATORIO",
        tabela=entidade,
        descricao=(
            f"Relatório de {entidade} exportado para o armazenamento em nuvem "
            f"(objeto {chave}), SHA-256 {hash_conteudo}."
        ),
    )
    db.session.commit()

    session["ultima_exportacao"] = {"entidade": entidade, "chave": chave, "sha256": hash_conteudo}
    return redirect(url_for("relatorios.index"))
