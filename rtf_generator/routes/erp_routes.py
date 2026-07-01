from flask import Blueprint, current_app, jsonify, request
from time import perf_counter
from repositories.local_auth_repository import LocalAuthRepository
from repositories.erp_repository import ERPRepository
from repositories.local_note_repository import LocalNoteRepository
from services.chamado_service import ChamadoService
from services.dashboard_service import DashboardService
from services.produtividade_service import ProdutividadeService
from config import Config
from utils.auth_utils import get_access_scope, get_current_user, store_user_session

erp_bp = Blueprint('erp', __name__)
erp_repo = ERPRepository()
local_repo = LocalNoteRepository(Config.LOCAL_DB)

chamado_service = ChamadoService(erp_repo, local_repo)
dashboard_service = DashboardService(erp_repo, local_repo)
produtividade_service = ProdutividadeService(erp_repo)


def _get_auth_repo():
    repo = current_app.extensions.get("local_auth_repo")
    if repo:
        return repo
    return LocalAuthRepository(Config.LOCAL_DB)

@erp_bp.route('/assuntos')
def get_assuntos():
    tipo = request.args.get('tipo')
    return jsonify(erp_repo.buscar_assuntos(tipo, access_scope=get_access_scope()))

@erp_bp.route('/ativos')
def get_ativos():
    tipo = request.args.get('tipo')
    assunto = request.args.get('assunto')
    return jsonify(erp_repo.buscar_ativos(tipo, assunto, access_scope=get_access_scope()))

@erp_bp.route('/aprovadores')
def get_aprovadores():
    return jsonify(erp_repo.buscar_aprovadores(access_scope=get_access_scope()))

@erp_bp.route('/status')
def get_status():
    return jsonify(erp_repo.buscar_status())

@erp_bp.route('/chamados')
def get_chamados():
    filtros = {
        'status': request.args.getlist('status'),
        'cod_solicitacao': request.args.get('cod_solicitacao'),
        'solicitante': request.args.get('solicitante'),
        'start_date': request.args.get('start_date'),
        'end_date': request.args.get('end_date'),
        'kpi': request.args.get('kpi'),
        'tipo': request.args.get('tipo'),
        'assunto': request.args.get('assunto'),
        'ativo': request.args.get('ativo'),
        'aprovador': request.args.get('aprovador'),
        'access_scope': get_access_scope(),
    }
    return jsonify(chamado_service.listar_chamados(filtros))

@erp_bp.route('/chamado/<cod_solicitacao>')
def get_chamado_detalhe(cod_solicitacao):
    data = chamado_service.detalhar_chamado(cod_solicitacao, access_scope=get_access_scope())
    if not data:
        return jsonify({"error": "Chamado não encontrado"}), 404
    return jsonify(data)

@erp_bp.route('/estatisticas')
def get_estatisticas():
    start = request.args.get('start_date')
    end = request.args.get('end_date')
    kpi_date = request.args.get('kpi_date')
    debug_timing = (request.args.get('debug_timing') or "").strip().lower() in {"1", "true", "yes", "on"}
    t0 = perf_counter()
    data = dashboard_service.obter_estatisticas(start, end, kpi_date, debug_timing=debug_timing, access_scope=get_access_scope())
    resp = jsonify(data)
    resp.headers["X-Server-Time-ms"] = f"{(perf_counter() - t0) * 1000:.2f}"
    return resp

@erp_bp.route('/kanban')
def get_kanban():
    filtros = {
        'id': request.args.get('id'),
        'solicitante': request.args.get('solicitante'),
        'start_date': request.args.get('start_date'),
        'end_date': request.args.get('end_date'),
        'status': request.args.getlist('status'),
        'kpi': request.args.get('kpi'),
        'tipo': request.args.get('tipo'),
        'assunto': request.args.get('assunto'),
        'assunto_q': request.args.get('assunto_q'),
        'q': request.args.get('q'),
        'executor': request.args.get('executor'),
        'etapa': request.args.get('etapa'),
        'ativo': request.args.get('ativo'),
        'aprovador': request.args.get('aprovador'),
        'atendente': request.args.get('atendente'),
        'access_scope': get_access_scope(),
    }
    data = dashboard_service.obter_kanban(filtros)
    return jsonify(data)


@erp_bp.route('/kanban_column_order', methods=['POST'])
def save_kanban_column_order():
    user = get_current_user()
    if not user:
        return jsonify({"error": "Sessao expirada. Faca login novamente."}), 401

    payload = request.get_json(silent=True) or {}
    column_ids = payload.get("column_ids") or []
    auth_repo = _get_auth_repo()
    auth_repo.replace_user_kanban_column_order(
        user["id"],
        column_ids,
        user.get("kanban_status_codes"),
    )
    refreshed_user = auth_repo.get_user_with_subjects(user["id"])
    if refreshed_user:
        store_user_session(refreshed_user)
    return jsonify({"ok": True})

@erp_bp.route('/chamados_pendentes')
def get_chamados_pendentes():
    t0 = perf_counter()
    raw_limit = (request.args.get('limit') or '').strip()
    try:
        limit = int(raw_limit) if raw_limit else None
    except Exception:
        limit = None
    data = chamado_service.buscar_pendentes(access_scope=get_access_scope(), limit=limit)
    resp = jsonify(data)
    resp.headers["X-Server-Time-ms"] = f"{(perf_counter() - t0) * 1000:.2f}"
    return resp

@erp_bp.route('/trello_sem_rotulo')
def get_trello_sem_rotulo():
    raw = (request.args.get('limit') or '').strip()
    try:
        limit = int(raw) if raw else 30
    except Exception:
        limit = 30
    data = dashboard_service.obter_trello_sem_rotulo(limit, access_scope=get_access_scope())
    return jsonify(data)

@erp_bp.route('/produtividade')
def get_produtividade_data():
    start = request.args.get('start_date')
    end = request.args.get('end_date')
    return jsonify(produtividade_service.obter_produtividade(start, end, access_scope=get_access_scope()))
