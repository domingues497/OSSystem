from flask import Blueprint, jsonify, request
from repositories.local_note_repository import LocalNoteRepository
from services.local_note_service import LocalNoteService
from config import Config

local_bp = Blueprint('local', __name__)
local_repo = LocalNoteRepository(Config.LOCAL_DB)
local_note_service = LocalNoteService(local_repo)

@local_bp.route('/note', methods=['POST'])
def save_note():
    payload = request.get_json()
    return jsonify(local_note_service.salvar(payload))

@local_bp.route('/note/<cod_solicitacao>')
def get_notes(cod_solicitacao):
    return jsonify(local_note_service.listar_por_chamado(cod_solicitacao))

@local_bp.route('/assignee', methods=['POST'])
def save_assignee():
    payload = request.get_json()
    return jsonify(local_note_service.salvar_atendente(payload))

@local_bp.route('/assignee/<cod_solicitacao>')
def get_assignee(cod_solicitacao):
    return jsonify(local_note_service.obter_atendente(cod_solicitacao))

@local_bp.route('/assignees')
def get_assignees():
    return jsonify(local_note_service.listar_atendentes())
