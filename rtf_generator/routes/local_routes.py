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
