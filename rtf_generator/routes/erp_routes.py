from flask import Blueprint, jsonify, request
from repositories.erp_repository import ERPRepository
from repositories.local_note_repository import LocalNoteRepository
from services.chamado_service import ChamadoService
from services.dashboard_service import DashboardService
from services.produtividade_service import ProdutividadeService
from config import Config

erp_bp = Blueprint('erp', __name__)
erp_repo = ERPRepository()
local_repo = LocalNoteRepository(Config.LOCAL_DB)

chamado_service = ChamadoService(erp_repo, local_repo)
dashboard_service = DashboardService(erp_repo, local_repo)
produtividade_service = ProdutividadeService(erp_repo)

@erp_bp.route('/assuntos')
def get_assuntos():
    tipo = request.args.get('tipo')
    return jsonify(erp_repo.buscar_assuntos(tipo))

@erp_bp.route('/ativos')
def get_ativos():
    tipo = request.args.get('tipo')
    assunto = request.args.get('assunto')
    return jsonify(erp_repo.buscar_ativos(tipo, assunto))

@erp_bp.route('/aprovadores')
def get_aprovadores():
    return jsonify(erp_repo.buscar_aprovadores())

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
        'aprovador': request.args.get('aprovador')
    }
    return jsonify(chamado_service.listar_chamados(filtros))

@erp_bp.route('/chamado/<cod_solicitacao>')
def get_chamado_detalhe(cod_solicitacao):
    data = chamado_service.detalhar_chamado(cod_solicitacao)
    if not data:
        return jsonify({"error": "Chamado não encontrado"}), 404
    return jsonify(data)

@erp_bp.route('/estatisticas')
def get_estatisticas():
    start = request.args.get('start_date')
    end = request.args.get('end_date')
    kpi_date = request.args.get('kpi_date')
    return jsonify(dashboard_service.obter_estatisticas(start, end, kpi_date))

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
        'encerrados_all': request.args.get('encerrados_all')
    }
    return jsonify(dashboard_service.obter_kanban(filtros))

@erp_bp.route('/chamados_pendentes')
def get_chamados_pendentes():
    return jsonify(chamado_service.buscar_pendentes())

@erp_bp.route('/produtividade')
def get_produtividade_data():
    start = request.args.get('start_date')
    end = request.args.get('end_date')
    return jsonify(produtividade_service.obter_produtividade(start, end))
