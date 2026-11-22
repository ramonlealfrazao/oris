from flask import Blueprint, Response, abort, flash, redirect, render_template, url_for

from app.extensions import db
from app.forms import AcaoAlteracaoForm, RespostaSolicitacaoForm, SolicitacaoTitularForm
from app.models import PerfilUsuario, SolicitacaoTitular, StatusSolicitacaoTitular, TipoSolicitacaoTitular
from app.services import lgpd_service
from app.services.auditoria_service import registrar_auditoria
from app.utils.decorators import login_required, roles_required, usuario_atual

lgpd_bp = Blueprint("lgpd", __name__, url_prefix="/lgpd")

ADMINISTRADOR = PerfilUsuario.ADMINISTRADOR.value

ROTULOS_TIPO = {
    TipoSolicitacaoTitular.ACESSO: "Acesso aos dados",
    TipoSolicitacaoTitular.CORRECAO: "Correção",
    TipoSolicitacaoTitular.ELIMINACAO: "Anonimização ou eliminação",
    TipoSolicitacaoTitular.PORTABILIDADE: "Portabilidade",
    TipoSolicitacaoTitular.COMPARTILHAMENTO: "Compartilhamento",
    TipoSolicitacaoTitular.OPOSICAO: "Oposição",
}


@lgpd_bp.app_template_filter("rotulo_tipo_solicitacao")
def rotulo_tipo_solicitacao(tipo):
    return ROTULOS_TIPO.get(tipo, str(tipo))


@lgpd_bp.app_template_filter("solicitacao_vencida")
def solicitacao_vencida_filter(solicitacao):
    return lgpd_service.solicitacao_vencida(solicitacao)


def _buscar_solicitacao_ou_404(solicitacao_id):
    solicitacao = db.session.get(SolicitacaoTitular, solicitacao_id)
    if solicitacao is None:
        abort(404)
    return solicitacao


@lgpd_bp.route("/meus-dados")
@login_required
def meus_dados():
    usuario = usuario_atual()
    dados = lgpd_service.dados_do_titular(usuario)
    return render_template(
        "lgpd/meus_dados.html",
        dados=dados,
        form=SolicitacaoTitularForm(),
        form_acao=AcaoAlteracaoForm(),
        transparencia=lgpd_service.dados_de_transparencia(),
    )


@lgpd_bp.route("/solicitacoes/nova", methods=["POST"])
@login_required
def nova_solicitacao():
    usuario = usuario_atual()
    form = SolicitacaoTitularForm()
    if form.validate_on_submit():
        solicitacao = lgpd_service.registrar_solicitacao(usuario, form.tipo.data, form.descricao.data)
        flash(
            f"Pedido #{solicitacao.id} registrado. A resposta será dada até "
            f"{solicitacao.prazo_resposta.strftime('%d/%m/%Y')}.",
            "success",
        )
    else:
        for erros in form.errors.values():
            for erro in erros:
                flash(erro, "danger")
    return redirect(url_for("lgpd.meus_dados"))


@lgpd_bp.route("/meus-dados/exportar", methods=["POST"])
@login_required
def exportar():
    usuario = usuario_atual()
    corpo = lgpd_service.exportar_json(usuario)
    registrar_auditoria(
        usuario=usuario,
        acao="LGPD_EXPORTACAO",
        tabela="usuarios",
        registro_id=usuario.id,
        descricao="Exportação dos próprios dados pelo titular.",
    )
    db.session.commit()
    resposta = Response(corpo, mimetype="application/json")
    resposta.headers["Content-Disposition"] = f'attachment; filename="meus-dados-oris-{usuario.id}.json"'
    resposta.headers["Cache-Control"] = "no-store"
    return resposta


@lgpd_bp.route("/solicitacoes")
@roles_required(ADMINISTRADOR)
def solicitacoes():
    lista = SolicitacaoTitular.query.order_by(
        SolicitacaoTitular.status.asc(), SolicitacaoTitular.prazo_resposta.asc()
    ).all()
    return render_template("lgpd/solicitacoes_lista.html", solicitacoes=lista)


@lgpd_bp.route("/solicitacoes/<int:solicitacao_id>", methods=["GET", "POST"])
@roles_required(ADMINISTRADOR)
def solicitacao(solicitacao_id):
    item = _buscar_solicitacao_ou_404(solicitacao_id)
    form = RespostaSolicitacaoForm()
    if item.status == StatusSolicitacaoTitular.ABERTA and form.validate_on_submit():
        lgpd_service.responder_solicitacao(item, usuario_atual(), form.decisao.data, form.resposta.data)
        flash("Resposta registrada.", "success")
        return redirect(url_for("lgpd.solicitacao", solicitacao_id=item.id))
    return render_template(
        "lgpd/solicitacao_detalhe.html",
        item=item,
        form=form,
        form_acao=AcaoAlteracaoForm(),
        pode_anonimizar=(
            item.tipo == TipoSolicitacaoTitular.ELIMINACAO and item.titular.ativo
        ),
    )


@lgpd_bp.route("/solicitacoes/<int:solicitacao_id>/anonimizar", methods=["POST"])
@roles_required(ADMINISTRADOR)
def anonimizar(solicitacao_id):
    item = _buscar_solicitacao_ou_404(solicitacao_id)
    if item.tipo != TipoSolicitacaoTitular.ELIMINACAO:
        abort(400)
    try:
        lgpd_service.anonimizar_titular(item.titular, usuario_atual())
    except ValueError as erro:
        flash(str(erro), "danger")
    else:
        flash("Conta anonimizada. Registre a resposta ao titular.", "success")
    return redirect(url_for("lgpd.solicitacao", solicitacao_id=item.id))
