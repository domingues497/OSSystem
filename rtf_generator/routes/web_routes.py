from flask import Blueprint, current_app, render_template, request, send_file, redirect, url_for, Response
from werkzeug.utils import secure_filename
import os
import re
from config import Config
from repositories.local_auth_repository import LocalAuthRepository
from utils.chamados_filters import get_chamados_filter_definitions
from utils.dashboard_statuses import normalize_dashboard_status_codes
from utils.auth_utils import (
    admin_required,
    clear_user_session,
    get_access_scope,
    get_current_user,
    is_logged_in,
    login_required,
    sanitize_next_url,
    store_user_session,
)

web_bp = Blueprint('web', __name__)


def _get_auth_repo():
    repo = current_app.extensions.get("local_auth_repo")
    if repo:
        return repo
    return LocalAuthRepository(Config.LOCAL_DB)


def _render_with_auth(template_name, **kwargs):
    kwargs.setdefault("current_user", get_current_user())
    kwargs.setdefault("access_scope", get_access_scope())
    return render_template(template_name, **kwargs)


def _parse_subjects_from_form(auth_repo, form):
    selected_codes = []
    for raw in form.getlist("subject_codes"):
        try:
            code = int(str(raw).strip())
        except Exception:
            continue
        if code not in selected_codes:
            selected_codes.append(code)

    subject_map = {
        int(item["cod_assunto"]): item.get("descr_assunto") or ""
        for item in auth_repo.list_available_subjects()
    }
    return [
        {"cod_assunto": code, "descr_assunto": subject_map.get(code, "")}
        for code in selected_codes
    ]


def _parse_departments_from_form(auth_repo, form):
    selected_codes = []
    for raw in form.getlist("department_codes"):
        try:
            code = int(str(raw).strip())
        except Exception:
            continue
        if code not in selected_codes:
            selected_codes.append(code)

    department_map = {
        int(item["cod_depar"]): item.get("nome_departamento") or ""
        for item in auth_repo.list_available_departments()
    }
    return [
        {"cod_depar": code, "nome_departamento": department_map.get(code, "")}
        for code in selected_codes
    ]


def _parse_chart_flags_from_form(form):
    return {
        "show_external": (form.get("chart_show_external") or "").strip().lower() in {"1", "true", "on", "yes"},
        "show_internal": (form.get("chart_show_internal") or "").strip().lower() in {"1", "true", "on", "yes"},
    }


def _parse_chart_status_codes_from_form(form):
    return normalize_dashboard_status_codes(form.getlist("chart_status_codes"))


def _parse_kanban_status_codes_from_form(form):
    return normalize_dashboard_status_codes(form.getlist("kanban_status_codes"))

def extract_fields(filepath):
    with open(filepath, 'r', encoding='utf-8', errors='ignore') as f:
        content = f.read()
    fields = re.findall(r'\{\{(.*?)\}\}', content)
    return list(set(fields))

@web_bp.route('/')
@login_required
def index():
    return _render_with_auth('index.html')


@web_bp.route('/login', methods=['GET', 'POST'])
def login():
    if is_logged_in():
        return redirect(sanitize_next_url(request.args.get("next")))

    auth_repo = _get_auth_repo()
    has_users = auth_repo.count_users() > 0
    error = ""
    next_url = sanitize_next_url(request.args.get("next") or request.form.get("next"))

    if request.method == 'POST':
        action = (request.form.get("action") or "login").strip().lower()

        if action == "bootstrap" and not has_users:
            display_name = (request.form.get("display_name") or "").strip()
            username = (request.form.get("username") or "").strip()
            password = request.form.get("password") or ""
            confirm_password = request.form.get("confirm_password") or ""

            if not display_name or not username or not password:
                error = "Preencha nome, usuario e senha."
            elif password != confirm_password:
                error = "As senhas nao conferem."
            else:
                try:
                    auth_repo.create_user(
                        username=username,
                        password=password,
                        display_name=display_name,
                        profile="admin",
                        subjects=[],
                        departments=[],
                    )
                    user = auth_repo.authenticate(username, password)
                    if user:
                        store_user_session(user)
                        return redirect(next_url)
                    error = "Usuario criado, mas nao foi possivel iniciar a sessao."
                except Exception as exc:
                    error = f"Nao foi possivel criar o usuario inicial: {exc}"
            has_users = auth_repo.count_users() > 0
        else:
            username = (request.form.get("username") or "").strip()
            password = request.form.get("password") or ""
            user = auth_repo.authenticate(username, password)
            if not user:
                error = "Usuario ou senha invalidos."
            else:
                store_user_session(user)
                return redirect(next_url)

    return render_template(
        'login.html',
        error=error,
        has_users=has_users,
        next_url=next_url,
    )


@web_bp.route('/logout')
@login_required
def logout():
    clear_user_session()
    return redirect(url_for('web.login'))


@web_bp.route('/usuarios', methods=['GET', 'POST'])
@login_required
@admin_required
def manage_users():
    auth_repo = _get_auth_repo()
    error = ""
    success = ""

    if request.method == "POST":
        action = (request.form.get("action") or "").strip().lower()
        try:
            if action == "create_user":
                display_name = (request.form.get("display_name") or "").strip()
                username = (request.form.get("username") or "").strip()
                password = request.form.get("password") or ""
                confirm_password = request.form.get("confirm_password") or ""
                profile = (request.form.get("profile") or "subject").strip().lower()
                subjects = _parse_subjects_from_form(auth_repo, request.form)
                departments = _parse_departments_from_form(auth_repo, request.form)
                chart_flags = _parse_chart_flags_from_form(request.form)
                chart_status_codes = _parse_chart_status_codes_from_form(request.form)
                kanban_status_codes = _parse_kanban_status_codes_from_form(request.form)
                is_active = (request.form.get("is_active") or "").strip().lower() in {"1", "true", "on", "yes"}

                if password != confirm_password:
                    raise ValueError("As senhas nao conferem.")
                if profile != "admin" and not subjects:
                    raise ValueError("Selecione pelo menos um assunto para o usuario.")
                if chart_flags["show_external"] and not chart_status_codes:
                    raise ValueError("Selecione pelo menos um status para o grafico externo.")
                if not kanban_status_codes:
                    raise ValueError("Selecione pelo menos um status para o kanban.")

                auth_repo.create_user(
                    username=username,
                    password=password,
                    display_name=display_name,
                    profile=profile,
                    subjects=subjects,
                    departments=departments,
                    is_active=is_active,
                    chart_flags=chart_flags,
                    chart_status_codes=chart_status_codes,
                    kanban_status_codes=kanban_status_codes,
                )
                success = "Usuario cadastrado com sucesso."

            elif action == "update_user":
                user_id = int(request.form.get("user_id"))
                display_name = (request.form.get("display_name") or "").strip()
                profile = (request.form.get("profile") or "subject").strip().lower()
                password = request.form.get("password") or ""
                is_active = (request.form.get("is_active") or "").strip().lower() in {"1", "true", "on", "yes"}
                subjects = _parse_subjects_from_form(auth_repo, request.form)
                departments = _parse_departments_from_form(auth_repo, request.form)
                chart_flags = _parse_chart_flags_from_form(request.form)
                chart_status_codes = _parse_chart_status_codes_from_form(request.form)
                kanban_status_codes = _parse_kanban_status_codes_from_form(request.form)

                if profile != "admin" and not subjects:
                    raise ValueError("Selecione pelo menos um assunto para o usuario.")
                if chart_flags["show_external"] and not chart_status_codes:
                    raise ValueError("Selecione pelo menos um status para o grafico externo.")
                if not kanban_status_codes:
                    raise ValueError("Selecione pelo menos um status para o kanban.")

                auth_repo.update_user(
                    user_id=user_id,
                    display_name=display_name,
                    profile=profile,
                    is_active=is_active,
                    password=password or None,
                    subjects=subjects,
                    departments=departments,
                    chart_flags=chart_flags,
                    chart_status_codes=chart_status_codes,
                    kanban_status_codes=kanban_status_codes,
                )
                success = "Usuario atualizado com sucesso."
            else:
                error = "Acao invalida."
        except Exception as exc:
            error = str(exc)

    return _render_with_auth(
        "users.html",
        error=error,
        success=success,
        available_subjects=auth_repo.list_available_subjects(),
        available_departments=auth_repo.list_available_departments(),
        available_chart_statuses=auth_repo.list_available_chart_statuses(),
        available_kanban_statuses=auth_repo.list_available_kanban_statuses(),
        managed_users=auth_repo.list_users_with_subjects(),
    )

@web_bp.route('/upload', methods=['POST'])
@login_required
def upload_file():
    if 'rtf_file' not in request.files:
        return redirect(request.url)
    file = request.files['rtf_file']
    if file.filename == '':
        return redirect(request.url)
    if file:
        filename = secure_filename(file.filename)
        filepath = os.path.join(Config.UPLOAD_FOLDER, filename)
        file.save(filepath)
        return redirect(url_for('web.edit_file', filename=filename))

@web_bp.route('/edit/<filename>')
@login_required
def edit_file(filename):
    filepath = os.path.join(Config.UPLOAD_FOLDER, filename)
    fields = extract_fields(filepath)
    return _render_with_auth('edit.html', filename=filename, fields=fields)

@web_bp.route('/generate/<filename>', methods=['POST'])
@login_required
def generate_file(filename):
    original_filepath = os.path.join(Config.UPLOAD_FOLDER, filename)
    with open(original_filepath, 'r', encoding='utf-8', errors='ignore') as f:
        content = f.read()

    form_data = request.form
    for field, value in form_data.items():
        content = content.replace(f'{{{{{field}}}}}', value)

    new_filename = f'generated_{filename}'
    generated_filepath = os.path.join(Config.GENERATED_FOLDER, new_filename)
    with open(generated_filepath, 'w', encoding='utf-8') as f:
        f.write(content)

    return send_file(generated_filepath, as_attachment=True)

@web_bp.route('/produtividade')
@login_required
def produtividade_page():
    return _render_with_auth('produtividade.html')

@web_bp.route('/chamados')
@login_required
def chamados_page():
    return _render_with_auth(
        'chamados.html',
        available_chamados_filters=get_chamados_filter_definitions(),
    )

@web_bp.route('/favicon.ico')
def favicon():
    return Response(status=204)
