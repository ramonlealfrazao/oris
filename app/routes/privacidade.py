"""Página de Privacidade e Transparência."""

from flask import Blueprint, render_template

from app.services.lgpd_service import dados_de_transparencia

privacidade_bp = Blueprint("privacidade", __name__)


@privacidade_bp.route("/privacidade")
def index():
    return render_template("privacidade.html", t=dados_de_transparencia())
