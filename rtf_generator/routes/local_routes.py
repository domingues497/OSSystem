from flask import Blueprint, jsonify, request
from repositories.erp_repository import ERPRepository
from repositories.local_note_repository import LocalNoteRepository
from services.local_note_service import LocalNoteService
from config import Config
from utils.auth_utils import get_access_scope

local_bp = Blueprint('local', __name__)
local_repo = LocalNoteRepository(Config.LOCAL_DB)
local_note_service = LocalNoteService(local_repo)
erp_repo = ERPRepository()


def _is_ticket_allowed(cod_solicitacao):
    return erp_repo.ticket_in_scope(cod_solicitacao, access_scope=get_access_scope())

@local_bp.route('/note', methods=['POST'])
def save_note():
    payload = request.get_json()
    cod_solicitacao = (payload or {}).get('cod_solicitacao')
    if not _is_ticket_allowed(cod_solicitacao):
        return jsonify({"error": "Acesso negado ao chamado"}), 403
    return jsonify(local_note_service.salvar(payload))

@local_bp.route('/note/<cod_solicitacao>')
def get_notes(cod_solicitacao):
    if not _is_ticket_allowed(cod_solicitacao):
        return jsonify({"error": "Acesso negado ao chamado"}), 403
    return jsonify(local_note_service.listar_por_chamado(cod_solicitacao))

@local_bp.route('/assignee', methods=['POST'])
def save_assignee():
    payload = request.get_json()
    cod_solicitacao = (payload or {}).get('cod_solicitacao')
    if not _is_ticket_allowed(cod_solicitacao):
        return jsonify({"error": "Acesso negado ao chamado"}), 403
    return jsonify(local_note_service.salvar_atendente(payload))

@local_bp.route('/assignee/<cod_solicitacao>')
def get_assignee(cod_solicitacao):
    if not _is_ticket_allowed(cod_solicitacao):
        return jsonify({"error": "Acesso negado ao chamado"}), 403
    return jsonify(local_note_service.obter_atendente(cod_solicitacao))

@local_bp.route('/assignees')
def get_assignees():
    return jsonify(local_note_service.listar_atendentes())


@local_bp.route('/ticket_user_contact', methods=['POST'])
def save_ticket_user_contact():
    payload = request.get_json(silent=True) or {}
    cod_solicitacao = payload.get('cod_solicitacao')
    cod_usuario = payload.get('cod_usuario')

    if not _is_ticket_allowed(cod_solicitacao):
        return jsonify({"error": "Acesso negado ao chamado"}), 403

    ticket_data = erp_repo.buscar_chamado_por_id(cod_solicitacao, access_scope=get_access_scope())
    if not ticket_data:
        return jsonify({"error": "Chamado nao encontrado"}), 404

    try:
        ticket_cod_usuario = int(ticket_data.get('cod_usuario') or 0)
        payload_cod_usuario = int(cod_usuario or 0)
    except Exception:
        return jsonify({"error": "Usuario do chamado invalido"}), 400

    if not ticket_cod_usuario or ticket_cod_usuario != payload_cod_usuario:
        return jsonify({"error": "Usuario informado nao corresponde ao solicitante do chamado"}), 400

    result = local_note_service.salvar_contato_usuario_chamado(payload)
    status_code = 200 if not result.get("error") else 400
    return jsonify(result), status_code
