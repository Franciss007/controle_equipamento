from functools import wraps
from flask import session, flash, redirect, url_for, request, abort

def login_required(f):
    @wraps(f)
    def wrapper(*args, **kwargs):
        if "usuario" not in session:
            flash("Faça login para continuar.", "erro")
            return redirect(url_for("login", next=request.path))
        return f(*args, **kwargs)
    return wrapper

def roles_required(*roles):
    def decorator(f):
        @wraps(f)
        def wrapper(*args, **kwargs):
            if "usuario" not in session:
                flash("Faça login para continuar.", "erro")
                return redirect(url_for("login", next=request.path))
            if session.get("role") not in roles:
                return abort(403)
            return f(*args, **kwargs)
        return wrapper
    return decorator
