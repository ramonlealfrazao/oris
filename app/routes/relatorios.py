from flask import Blueprint, Response, abort, current_app, flash, redirect, render_template, request, session, url_for

from app.extensions import db
from app.models import PerfilUsuario
from app.services.armazenamento_service import (
    ArmazenamentoError,
    enviar_relatorio,
    gerar_url_download,
    s3_configurado,
)
from app.services import gdrive_service
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
        drive_oidc_ativo=gdrive_service.oidc_drive_configurado(),
        drive_m2m_ativo=gdrive_service.m2m_drive_configurado(),
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


def _auditar_drive(entidade, metodo, arquivo, hash_conteudo, destino):
    registrar_auditoria(
        usuario=usuario_atual(),
        acao="EXPORTAR_DRIVE",
        tabela=entidade,
        descricao=(
            f"Relatório de {entidade} enviado ao Google Drive via {metodo} "
            f"(arquivo {arquivo}, destino {destino}), SHA-256 {hash_conteudo}."
        ),
    )
    db.session.commit()


@relatorios_bp.route("/<entidade>/exportar-drive-oidc", methods=["POST"])
@roles_required(*PERFIS_QUE_EXPORTAM)
def exportar_drive_oidc(entidade):
    _validar_entidade_ou_404(entidade)
    if not gdrive_service.oidc_drive_configurado():
        flash("A exportação ao Google Drive (OIDC) não está configurada neste ambiente.", "warning")
        return redirect(url_for("relatorios.index"))
    try:
        url, estado = gdrive_service.iniciar_autorizacao_oidc(
            url_for("relatorios.callback_drive", _external=True),
            email_sugerido=usuario_atual().email,
        )
    except gdrive_service.DriveError as erro:
        flash(str(erro), "danger")
        return redirect(url_for("relatorios.index"))
    session["drive_oidc"] = {**estado, "entidade": entidade}
    return redirect(url)


@relatorios_bp.route("/google/callback")
@roles_required(*PERFIS_QUE_EXPORTAM)
def callback_drive():
    estado = session.pop("drive_oidc", None)
    codigo = request.args.get("code")
    if not estado or not codigo or request.args.get("state") != estado.get("state"):
        flash("Autorização do Google Drive inválida ou cancelada.", "danger")
        return redirect(url_for("relatorios.index"))
    entidade = estado["entidade"]
    _validar_entidade_ou_404(entidade)
    try:
        token, email = gdrive_service.concluir_autorizacao_oidc(
            codigo, estado, url_for("relatorios.callback_drive", _external=True)
        )
        nome, conteudo = gerar_csv(entidade)
        enviado = gdrive_service.enviar_arquivo(token, conteudo, gdrive_service.nome_arquivo(entidade))
    except gdrive_service.DriveError as erro:
        flash(str(erro), "danger")
        return redirect(url_for("relatorios.index"))
    hash_conteudo = sha256_hex(conteudo)
    _auditar_drive(entidade, "OIDC", enviado.get("name", nome), hash_conteudo, f"conta Google {email}")
    flash(f"Relatório enviado ao Google Drive de {email} (OIDC): {enviado.get('name', nome)}.", "success")
    return redirect(url_for("relatorios.index"))


@relatorios_bp.route("/<entidade>/exportar-drive-m2m", methods=["POST"])
@roles_required(*PERFIS_QUE_EXPORTAM)
def exportar_drive_m2m(entidade):
    _validar_entidade_ou_404(entidade)
    if not gdrive_service.m2m_drive_configurado():
        flash("A exportação ao Google Drive (M2M) não está configurada neste ambiente.", "warning")
        return redirect(url_for("relatorios.index"))
    nome, conteudo = gerar_csv(entidade)
    try:
        token = gdrive_service.token_m2m()
        enviado = gdrive_service.enviar_arquivo(
            token, conteudo, gdrive_service.nome_arquivo(entidade),
            current_app.config["GOOGLE_DRIVE_PASTA_ID"],
        )
    except gdrive_service.DriveError as erro:
        flash(str(erro), "danger")
        return redirect(url_for("relatorios.index"))
    _auditar_drive(entidade, "OAuth2 M2M", enviado.get("name", nome), sha256_hex(conteudo), "pasta compartilhada")
    flash(f"Relatório enviado à pasta compartilhada do Google Drive (M2M): {enviado.get('name', nome)}.", "success")
    return redirect(url_for("relatorios.index"))
