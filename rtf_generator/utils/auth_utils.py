from functools import wraps

from flask import jsonify, redirect, request, session, url_for
from utils.chamados_filters import get_default_chamados_filter_ids, normalize_chamados_filter_ids
from utils.dashboard_statuses import (
    get_default_dashboard_status_codes,
    get_default_kanban_status_codes,
    get_kanban_column_ids,
    normalize_dashboard_status_codes,
    normalize_kanban_column_order,
)


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
            "department_codes": [],
            "department_names": [],
            "chart_show_external": True,
            "chart_show_internal": True,
            "chart_status_codes": get_default_dashboard_status_codes(),
            "kanban_status_codes": get_default_kanban_status_codes(),
            "kanban_column_ids": get_kanban_column_ids(),
            "chamados_filter_ids": get_default_chamados_filter_ids(is_admin=False),
            "user_id": None,
            "username": "",
            "display_name": "",
            "profile": "",
            "can_manage_filters": False,
        }

    is_admin = (user.get("profile") or "").lower() == "admin"
    subject_codes = _clean_scope_codes(user.get("subject_codes") or [])
    subject_names = [str(name).strip() for name in (user.get("subject_names") or []) if str(name).strip()]
    department_codes = _clean_scope_codes(user.get("department_codes") or [])
    department_names = [str(name).strip() for name in (user.get("department_names") or []) if str(name).strip()]
    chart_status_codes = normalize_dashboard_status_codes(user.get("chart_status_codes")) or get_default_dashboard_status_codes()
    kanban_status_codes = normalize_dashboard_status_codes(user.get("kanban_status_codes")) or get_default_kanban_status_codes()
    kanban_column_ids = normalize_kanban_column_order(user.get("kanban_column_order"), kanban_status_codes)
    chamados_filter_ids = normalize_chamados_filter_ids(user.get("chamados_filter_ids"), is_admin=is_admin)
    return {
        "authenticated": True,
        "is_admin": is_admin,
        "subject_codes": subject_codes,
        "subject_names": subject_names,
        "department_codes": department_codes,
        "department_names": department_names,
        "chart_show_external": bool(user.get("chart_show_external", True)),
        "chart_show_internal": bool(user.get("chart_show_internal", True)),
        "chart_status_codes": chart_status_codes,
        "kanban_status_codes": kanban_status_codes,
        "kanban_column_ids": kanban_column_ids,
        "chamados_filter_ids": chamados_filter_ids,
        "user_id": user.get("id"),
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
        "department_codes": _clean_scope_codes([d.get("cod_depar") for d in (user.get("departments") or [])]),
        "department_names": [str(d.get("nome_departamento") or "").strip() for d in (user.get("departments") or []) if str(d.get("nome_departamento") or "").strip()],
        "chart_show_external": bool(user.get("chart_show_external", True)),
        "chart_show_internal": bool(user.get("chart_show_internal", True)),
        "chart_status_codes": normalize_dashboard_status_codes(user.get("chart_status_codes")) or get_default_dashboard_status_codes(),
        "kanban_status_codes": normalize_dashboard_status_codes(user.get("kanban_status_codes")) or get_default_kanban_status_codes(),
        "kanban_column_order": normalize_kanban_column_order(
            user.get("kanban_column_order"),
            normalize_dashboard_status_codes(user.get("kanban_status_codes")) or get_default_kanban_status_codes(),
        ),
        "chamados_filter_ids": normalize_chamados_filter_ids(
            user.get("chamados_filter_ids"),
            is_admin=(user.get("profile") or "").lower() == "admin",
        ),
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
