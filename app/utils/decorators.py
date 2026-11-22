from functools import wraps

from flask import abort, redirect, session, url_for

from app.extensions import db


def _sessao_autenticada() -> bool:
    return bool(session.get("autenticado") and session.get("usuario_id"))


def usuario_atual():
    from app.models import Usuario

    if not _sessao_autenticada():
        return None

    return db.session.get(Usuario, session["usuario_id"])


def login_required(view_func):
    @wraps(view_func)
    def wrapper(*args, **kwargs):
        if not _sessao_autenticada():
            return redirect(url_for("auth.login"))

        usuario = usuario_atual()
        if usuario is None or not usuario.ativo:
            session.clear()
            return redirect(url_for("auth.login"))

        return view_func(*args, **kwargs)

    return wrapper


def roles_required(*perfis_permitidos):
    perfis_permitidos_set = {str(p) for p in perfis_permitidos}

    def decorator(view_func):
        @wraps(view_func)
        def wrapper(*args, **kwargs):
            if not _sessao_autenticada():
                return redirect(url_for("auth.login"))

            usuario = usuario_atual()

            if usuario is None or not usuario.ativo:
                session.clear()
                return redirect(url_for("auth.login"))

            if usuario.perfil.value not in perfis_permitidos_set:
                abort(403)

            return view_func(*args, **kwargs)

        return wrapper

    return decorator
