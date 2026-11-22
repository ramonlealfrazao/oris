from flask import Blueprint, render_template

design_system_bp = Blueprint("design_system", __name__)


@design_system_bp.route("/design-system")
def index():
    return render_template("design_system.html")
