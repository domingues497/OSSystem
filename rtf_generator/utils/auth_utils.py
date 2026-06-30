from functools import wraps

from flask import jsonify, redirect, request, session, url_for


SESSION_USER_KEY = "auth_user"


def _clean_scope_codes(values):
    codes = []
    for value in values or []:
        try:
            code = int(value)
        except Exception:
            continue
        if code not in codes:
            codes.append(code)
    return codes


def get_current_user():
    user = session.get(SESSION_USER_KEY)
    return user if isinstance(user, dict) else None


def is_logged_in():
    return get_current_user() is not None


def get_access_scope():
    user = get_current_user()
    if not user:
        return {
            "authenticated": False,
            "is_admin": False,
            "subject_codes": [],
            "subject_names": [],
            "username": "",
            "display_name": "",
            "profile": "",
            "can_manage_filters": False,
        }

    is_admin = (user.get("profile") or "").lower() == "admin"
    subject_codes = _clean_scope_codes(user.get("subject_codes") or [])
    subject_names = [str(name).strip() for name in (user.get("subject_names") or []) if str(name).strip()]
    return {
        "authenticated": True,
        "is_admin": is_admin,
        "subject_codes": subject_codes,
        "subject_names": subject_names,
        "username": user.get("username") or "",
        "display_name": user.get("display_name") or "",
        "profile": user.get("profile") or "",
        "can_manage_filters": is_admin,
    }


def store_user_session(user):
    subjects = user.get("subjects") or []
    session[SESSION_USER_KEY] = {
        "id": int(user["id"]),
        "username": user.get("username") or "",
        "display_name": user.get("display_name") or user.get("username") or "",
        "profile": user.get("profile") or "subject",
        "subject_codes": _clean_scope_codes([d.get("cod_assunto") for d in subjects]),
        "subject_names": [str(d.get("descr_assunto") or "").strip() for d in subjects if str(d.get("descr_assunto") or "").strip()],
    }
    session.permanent = True


def clear_user_session():
    session.pop(SESSION_USER_KEY, None)


def sanitize_next_url(next_url):
    next_url = (next_url or "").strip()
    if not next_url or not next_url.startswith("/"):
        return url_for("web.index")
    if next_url.startswith("//"):
        return url_for("web.index")
    return next_url


def unauthorized_response():
    if request.path.startswith("/api/"):
        return jsonify({"error": "Sessao expirada. Faca login novamente."}), 401
    return redirect(url_for("web.login", next=sanitize_next_url(request.full_path if request.query_string else request.path)))


def login_required(view_func):
    @wraps(view_func)
    def wrapper(*args, **kwargs):
        if not is_logged_in():
            return unauthorized_response()
        return view_func(*args, **kwargs)

    return wrapper


def admin_required(view_func):
    @wraps(view_func)
    def wrapper(*args, **kwargs):
        scope = get_access_scope()
        if not scope.get("authenticated"):
            return unauthorized_response()
        if not scope.get("is_admin"):
            if request.path.startswith("/api/"):
                return jsonify({"error": "Acesso restrito ao administrador."}), 403
            return redirect(url_for("web.index"))
        return view_func(*args, **kwargs)

    return wrapper
