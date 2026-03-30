
from flask import Flask, render_template, request, send_file, redirect, url_for, jsonify
import os
import re
import sqlite3
import psycopg2
from werkzeug.utils import secure_filename
from dotenv import load_dotenv

load_dotenv()

app = Flask(__name__)
app.config['UPLOAD_FOLDER'] = os.getenv('UPLOAD_FOLDER', 'uploads')
app.config['GENERATED_FOLDER'] = os.getenv('GENERATED_FOLDER', 'generated')
app.config['LOCAL_DB'] = os.getenv('LOCAL_DB', os.path.join(os.path.dirname(__file__), 'local_notes.db'))

# Banco Local (SQLite)
def get_local_connection():
    conn = sqlite3.connect(app.config['LOCAL_DB'])
    conn.row_factory = sqlite3.Row
    return conn

def init_local_db():
    conn = get_local_connection()
    cur = conn.cursor()
    cur.execute("""
        CREATE TABLE IF NOT EXISTS notes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            cod_solicitacao INTEGER NOT NULL,
            note TEXT NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    conn.commit()
    conn.close()

try:
    os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
    os.makedirs(app.config['GENERATED_FOLDER'], exist_ok=True)
    init_local_db()
except Exception:
    pass

# Configuração de conexão com o ERP (PostgreSQL)
def get_erp_connection():
    return psycopg2.connect(
        dbname=os.getenv("ERP_DB_NAME"),
        user=os.getenv("ERP_DB_USER"),
        password=os.getenv("ERP_DB_PASS"),
        host=os.getenv("ERP_DB_HOST"),
        port=os.getenv("ERP_DB_PORT")
    )

def format_erp_date(date_val):
    if not date_val: return ""
    s = str(int(date_val))
    if len(s) == 8:
        return f"{s[6:8]}/{s[4:6]}/{s[0:4]}"
    return s

def format_erp_time(time_val):
    if time_val is None: return ""
    try:
        s_time = str(time_val)
        if '.' in s_time:
            parts = s_time.split('.')
            hh = parts[0].zfill(2)
            mmss = parts[1].ljust(4, '0')[:4]
            s = hh + mmss
        else:
            s = s_time.zfill(6)
        return f"{s[0:2]}:{s[2:4]}:{s[4:6]}"
    except:
        return str(time_val)

def erp_to_datetime(date_val, time_val):
    try:
        from datetime import datetime
        if not date_val: return None
        d_str = str(int(date_val)).zfill(8)
        
        # Tratar o tempo de forma robusta para suportar Decimal, Float e Int
        if time_val is None:
            t_str = "000000"
        else:
            s_time = str(time_val)
            if '.' in s_time:
                parts = s_time.split('.')
                hh = parts[0].zfill(2)
                mmss = parts[1].ljust(4, '0')[:4]
                t_str = hh + mmss
            else:
                t_str = s_time.zfill(6)
        
        return datetime.strptime(f"{d_str}{t_str[:6]}", "%Y%m%d%H%M%S")
    except:
        return None

def format_duration(td):
    if not td: return ""
    days = td.days
    hours, remainder = divmod(td.seconds, 3600)
    minutes, _ = divmod(remainder, 60)
    
    parts = []
    if days > 0: parts.append(f"{days}d")
    if hours > 0: parts.append(f"{hours}h")
    if minutes > 0 or (days == 0 and hours == 0): parts.append(f"{minutes}m")
    return " ".join(parts)

def format_duration_short(seconds):
    if not seconds or seconds < 0: return "0m"
    days, remainder = divmod(int(seconds), 86400)
    hours, remainder = divmod(remainder, 3600)
    minutes, _ = divmod(remainder, 60)
    
    if days > 0: return f"{days}d {hours}h"
    if hours > 0: return f"{hours}h {minutes}m"
    return f"{minutes}m"

def classify_ticket(titulo, descricao=""):
    """
    Classificação usando Processamento de Linguagem Natural (Heurística).
    Classifica entre 'Incidente' (algo quebrou), 'Requisição de Serviço' (pedido de algo novo) e 'BI' (relatórios e consultas).
    """
    text = (str(titulo) + " " + str(descricao)).upper()
    
    # Prioridade para BI - Usando regex para garantir que seja palavra inteira ou termo específico
    # Adicionado termos mais específicos e verificação de limites de palavras
    bi_patterns = [
        r'\bBI\b', r'\bB\.I\b', r'\bQLIK\b', r'\bQLIKVIEW\b', r'\bQLIKSENSE\b', 
        r'\bDASHBOARD\b', r'\bPOWER BI\b', r'\bPOWERBI\b', r'\bDATASET\b'
    ]
    if any(re.search(p, text) for p in bi_patterns):
        return "BI"
    
    # Padrões para Incidentes (Quebra de serviço, erro, falha)
    incident_keywords = [
        'ERRO', 'FALHA', 'NÃO FUNCIONA', 'NAO FUNCIONA', 'BUG', 'PAROU', 'PROBLEMA', 
        'LENTIDÃO', 'LENTIDAO', 'TRAVANDO', 'FORA DO AR', 'QUEDAS', 'INTERROMPIDO',
        'MENSAGEM DE ERRO', 'INCORRETO', 'DIVERGÊNCIA', 'DIVERGENCIA', 'ESTORNO', 'RETRABALHO'
    ]
    
    # Padrões para Requisições (Pedidos, acessos, novas configurações)
    request_keywords = [
        'SOLICITO', 'LIBERAÇÃO', 'LIBERACAO', 'ACESSO', 'INSTALAÇÃO', 'INSTALACAO', 
        'CONFIGURAÇÃO', 'CONFIGURACAO', 'NOVO USUÁRIO', 'NOVO USUARIO', 'TROCA DE SENHA', 
        'RELATÓRIO', 'RELATORIO', 'EXTRAÇÃO', 'EXTRACAO', 'CADASTRO', 'CRIAR', 'CRIACAO',
        'ALTERAR', 'MUDANÇA', 'MUDANCA', 'DÚVIDA', 'DUVIDA', 'PEDIDO', 'SOLICITAÇÃO'
    ]
    
    # Contagem de ocorrências usando busca por palavra inteira para evitar falsos positivos
    inc_score = sum(1 for word in incident_keywords if re.search(rf'\b{word}\b', text))
    req_score = sum(1 for word in request_keywords if re.search(rf'\b{word}\b', text))
    
    if inc_score > req_score:
        return "Incidente"
    elif req_score > inc_score:
        return "Requisição"
    else:
        # Se houver empate, mas tiver palavras de incidente, priorizar incidente para atenção
        if inc_score > 0:
            return "Incidente"
        return "Requisição" # Geralmente Requisições são mais comuns em ERPs

@app.route('/api/erp/assuntos')
def get_erp_assuntos():
    tipo_filter = request.args.get('tipo')
    try:
        conn = get_erp_connection()
        if not conn:
            return jsonify([])
        cur = conn.cursor()
        
        # Se houver filtro de tipo, precisamos buscar os assuntos que pertencem a esse tipo
        # Como o tipo é classificado em Python, vamos buscar os chamados abertos e classificá-los
        if tipo_filter:
            cur.execute("""
                SELECT DISTINCT DM1744.COD_ASSUNTO, DC1739.DESCR_ASSUNTO, DM1744.TITULO_SOLICITACAO
                FROM BANCO01.DM1744
                JOIN BANCO01.DC1739 ON (DC1739.COD_ASSUNTO = DM1744.COD_ASSUNTO)
                JOIN BANCO01.DC1966 ON (DC1966.COD_ASSUNTO = DM1744.COD_ASSUNTO)
                WHERE DC1966.COD_DEPAR = 16 
                  AND DM1744.COD_STATUS_DOC NOT IN ('BA', 'RJ')
                  AND (DC1739.DATA_DESAT = 0 OR DC1739.DATA_DESAT IS NULL)
            """)
            rows = cur.fetchall()
            assuntos_set = set()
            assuntos_list = []
            for cod, descr, titulo in rows:
                if classify_ticket(titulo) == tipo_filter:
                    if cod not in assuntos_set:
                        assuntos_set.add(cod)
                        assuntos_list.append({"code": cod, "name": descr})
            assuntos = sorted(assuntos_list, key=lambda x: x['name'])
        else:
            cur.execute("""
                SELECT DISTINCT DC1739.COD_ASSUNTO, DC1739.DESCR_ASSUNTO 
                FROM BANCO01.DC1739 
                JOIN BANCO01.DC1966 ON (DC1966.COD_ASSUNTO = DC1739.COD_ASSUNTO)
                WHERE DC1966.COD_DEPAR = 16 
                  AND (DC1739.DATA_DESAT = 0 OR DC1739.DATA_DESAT IS NULL)
                ORDER BY DC1739.DESCR_ASSUNTO
            """)
            assuntos = [{"code": row[0], "name": row[1]} for row in cur.fetchall()]
            
        cur.close()
        conn.close()
        return jsonify(assuntos)
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/api/erp/ativos')
def get_erp_ativos():
    tipo_filter = request.args.get('tipo')
    assunto_filter = request.args.get('assunto')
    try:
        conn = get_erp_connection()
        if not conn:
            return jsonify([])
        cur = conn.cursor()
        
        # Query base para ativos com chamados abertos no depto 16
        query = """
            SELECT DC1629.COD_ATIVO, DC1629.DESCR_ATIVO, DC1629.IDENT_ATIVO, DM1744.TITULO_SOLICITACAO, DM1744.COD_ASSUNTO
            FROM BANCO01.DC1629 
            JOIN BANCO01.DM1744 ON (DM1744.COD_ATIVO = DC1629.COD_ATIVO)
            JOIN BANCO01.DC1966 ON (DC1966.COD_ASSUNTO = DM1744.COD_ASSUNTO)
            WHERE DM1744.COD_STATUS_DOC NOT IN ('BA', 'RJ')
              AND DC1966.COD_DEPAR = 16
              AND (DC1629.DATA_DESAT = 0 OR DC1629.DATA_DESAT IS NULL)
        """
        params = []
        if assunto_filter:
            query += " AND DM1744.COD_ASSUNTO = %s"
            params.append(assunto_filter)
            
        cur.execute(query, params)
        rows = cur.fetchall()
        
        # Agrupamento e Filtragem por Tipo (Python)
        grouped = {}
        for row in rows:
            cod, descr, ident, titulo, cod_assunto = row
            
            # Se tiver filtro de tipo, classificar e ignorar se não bater
            if tipo_filter and classify_ticket(titulo) != tipo_filter:
                continue
                
            name = f"{descr} ({ident})" if ident else descr
            if name not in grouped:
                grouped[name] = []
            if str(cod) not in grouped[name]:
                grouped[name].append(str(cod))
        
        ativos = [{"code": ",".join(ids), "name": name} for name, ids in grouped.items()]
        ativos.sort(key=lambda x: x['name'])
        
        cur.close()
        conn.close()
        return jsonify(ativos)
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/api/erp/aprovadores')
def get_erp_aprovadores():
    try:
        conn = get_erp_connection()
        if not conn:
            return jsonify([])
        cur = conn.cursor()
        
        # 1. Identificar o nome da coluna de texto na DM1745 (comentários)
        cur.execute("SELECT * FROM BANCO01.DM1745 LIMIT 1")
        all_cols = [col[0].lower() for col in cur.description]
        text_col = next((c for c in all_cols if 'descr' in c or 'texto' in c or 'obs' in c), "DESCR_ACOMP")
        
        # 2. Buscar os operadores oficiais da T.I (Departamento 16) 
        # Conforme o log e a imagem fornecida, a tabela DC1964 contém os operadores por departamento.
        # Buscamos os nomes na DS0300 cruzando com DC1964 (operadores do depto 16).
        query_operadores = """
            SELECT DISTINCT DS0300.NOME_USUARIO 
            FROM public.DS0300 
            JOIN BANCO01.DC1964 ON (DC1964.COD_USUARIO = DS0300.COD_USUARIO)
            WHERE DC1964.COD_DEPAR = 16
            ORDER BY DS0300.NOME_USUARIO
        """
        cur.execute(query_operadores)
        tecnicos_ti = {row[0].strip() for row in cur.fetchall()}
        
        # 3. Também buscamos quem aprova chamados da TI no histórico (DM1745)
        # mas só incluímos se o nome extraído ou o usuário que registrou pertencer à lista de TI
        # ou se tiver "TI" ou "T.I" no nome (conforme a imagem).
        query_aprovadores_hist = f"""
            SELECT DISTINCT DS0300.NOME_USUARIO, DM1745.{text_col}
            FROM BANCO01.DM1745 
            JOIN public.DS0300 ON (DS0300.COD_USUARIO = DM1745.COD_USUARIO)
            JOIN BANCO01.DM1744 ON (DM1744.COD_SOLICITACAO = DM1745.COD_SOLICITACAO)
            JOIN BANCO01.DC1966 ON (DC1966.COD_ASSUNTO = DM1744.COD_ASSUNTO)
            WHERE DC1966.COD_DEPAR = 16
              AND (UPPER({text_col}) LIKE '%%AUTORIZAÇÃO%%' AND UPPER({text_col}) LIKE '%%APROVADA%%')
        """
        cur.execute(query_aprovadores_hist)
        rows = cur.fetchall()
        
        aprovadores_finais = set(tecnicos_ti)
        for u_name, txt in rows:
            txt_upper = str(txt).upper()
            
            # Adicionar o usuário que gravou o comentário se ele for da TI (contém "TI")
            if u_name and ("TI" in u_name.upper() or "T.I" in u_name.upper()):
                aprovadores_finais.add(u_name.strip())
            
            # Extrair menção em "APROVADA POR [NOME]"
            if "APROVADA POR" in txt_upper:
                try:
                    parts = txt_upper.split("APROVADA POR")
                    if len(parts) > 1:
                        # Extrair o nome e limpar sufixos para comparar com a lista de técnicos
                        nome_cru = parts[1].split(".")[0].split("\r")[0].split("\n")[0].strip()
                        nome_sem_sufixo = nome_cru.split(" - ")[0].split(" -")[0].strip()
                        
                        # Se o nome extraído (com ou sem sufixo) bater com alguém da TI, 
                        # ou se ele próprio contiver "TI", adicionamos.
                        encontrou = False
                        for tec in tecnicos_ti:
                            if nome_sem_sufixo in tec.upper():
                                encontrou = True
                                break
                        
                        if encontrou or "TI" in nome_cru or "T.I" in nome_cru:
                            # Preferimos adicionar o nome como está na lista oficial se possível
                            adicionado = False
                            for tec in tecnicos_ti:
                                if nome_sem_sufixo in tec.upper():
                                    aprovadores_finais.add(tec)
                                    adicionado = True
                                    break
                            if not adicionado and len(nome_cru) > 3:
                                aprovadores_finais.add(nome_cru)
                except: pass
        
        aprovadores = sorted(list(aprovadores_finais))
        cur.close()
        conn.close()
        return jsonify(aprovadores)
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/api/erp/status')
def get_erp_statuses():
    try:
        status_map = {
            'AA': 'Aguardando autorização',
            'IM': 'Aberta',
            'AB': 'Aberta',
            'EA': 'Em andamento',
            'AN': 'Em andamento',
            'AV': 'Aguardando avaliação',
            'PR': 'Programada',
            'RT': 'Retrabalho',
            'BA': 'Encerrada',
            'RJ': 'Rejeitada'
        }
        conn = get_erp_connection()
        if not conn:
            # DADOS SIMULADOS
            return jsonify([
                {"code": "IM", "name": "Aberta"},
                {"code": "AA", "name": "Aguardando autorização"},
                {"code": "EA", "name": "Em andamento"},
                {"code": "AV", "name": "Aguardando avaliação"},
                {"code": "BA", "name": "Encerrada"},
                {"code": "RJ", "name": "Rejeitada"}
            ])

        cur = conn.cursor()
        cur.execute("SELECT DISTINCT COD_STATUS_DOC FROM BANCO01.DM1744 WHERE COD_STATUS_DOC IS NOT NULL ORDER BY COD_STATUS_DOC")
        statuses = []
        for row in cur.fetchall():
            code = row[0]
            statuses.append({
                "code": code,
                "name": status_map.get(code, code)
            })
        cur.close()
        conn.close()
        return jsonify(statuses)
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/api/erp/chamados')
def get_erp_chamados():
    status_filter = request.args.getlist('status')
    cod_solicitacao_filter = request.args.get('cod_solicitacao')
    solicitante_filter = request.args.get('solicitante')
    start_date = request.args.get('start_date')
    end_date = request.args.get('end_date')
    kpi_type = request.args.get('kpi') 
    tipo_filter = request.args.get('tipo') 
    assunto_filter = request.args.get('assunto') 
    ativo_filter = request.args.get('ativo') 
    aprovador_filter = request.args.get('aprovador') # Novo parâmetro para filtrar por Aprovador
    
    try:
        conn = get_erp_connection()
        cur = conn.cursor()
        
        # 1. Identificar o nome da coluna de texto na DM1745
        cur.execute("SELECT * FROM BANCO01.DM1745 LIMIT 1")
        all_cols = [col[0].lower() for col in cur.description]
        text_col = next((c for c in all_cols if 'descr' in c or 'texto' in c or 'obs' in c), "DESCR_ACOMP")
        
        status_map = {
            'AA': 'Aguardando autorização',
            'IM': 'Aberta',
            'AB': 'Aberta',
            'EA': 'Em andamento',
            'AN': 'Em andamento',
            'AV': 'Aguardando avaliação',
            'PR': 'Programada',
            'RT': 'Retrabalho',
            'BA': 'Encerrada',
            'RJ': 'Rejeitada'
        }

        # Query base
        exists_subquery = f"""
            EXISTS (
                SELECT 1 FROM BANCO01.DM1745 
                WHERE COD_SOLICITACAO = DM1744.COD_SOLICITACAO 
                  AND (UPPER({text_col}) LIKE '%%AUTORIZAÇÃO%%' AND UPPER({text_col}) LIKE '%%APROVADA%%')
            )
        """

        query = f"""
            SELECT 
                DM1744.PRIORIDADE, 
                DM1744.COD_STATUS_DOC, 
                DM1744.DATA_CAD, 
                DS0300.NOME_USUARIO as SOLICITANTE,
                DM1744.COD_SOLICITACAO, 
                DM1744.TITULO_SOLICITACAO,
                DC1629.DESCR_ATIVO,
                DC1739.DESCR_ASSUNTO as ASSUNTO,
                {exists_subquery} as foi_aprovado
            FROM BANCO01.DM1744 
            LEFT JOIN public.DS0300 ON (DS0300.COD_USUARIO = DM1744.COD_USUARIO)
            LEFT JOIN BANCO01.DC1629 ON (DC1629.COD_ATIVO = DM1744.COD_ATIVO)
            LEFT JOIN BANCO01.DC1739 ON (DC1739.COD_ASSUNTO = DM1744.COD_ASSUNTO)
            WHERE DM1744.COD_ASSUNTO IN (
                SELECT COD_ASSUNTO 
                FROM BANCO01.DC1966 
                WHERE COD_DEPAR = 16
            )
        """
        
        params = []

        # Filtro de Aprovador
        if aprovador_filter:
            # Limpar o nome do aprovador para busca mais flexível (remover sufixos TI)
            clean_approver = aprovador_filter.upper().split(" - ")[0].split(" -")[0].strip()
            query += f""" AND (
                EXISTS (
                    SELECT 1 FROM BANCO01.DM1745 
                    JOIN public.DS0300 ON (DS0300.COD_USUARIO = DM1745.COD_USUARIO)
                    WHERE DM1745.COD_SOLICITACAO = DM1744.COD_SOLICITACAO 
                      AND (UPPER({text_col}) LIKE '%%AUTORIZAÇÃO%%' AND UPPER({text_col}) LIKE '%%APROVADA%%')
                      AND (UPPER(DS0300.NOME_USUARIO) LIKE %s OR UPPER({text_col}) LIKE %s)
                ) OR EXISTS (
                    SELECT 1 FROM public.DS0300 DSRESP
                    WHERE DS0300.COD_USUARIO = DM1744.COD_USUARIO_RESPONS
                      AND UPPER(DS0300.NOME_USUARIO) LIKE %s
                )
            )"""
            params.append(f"%{clean_approver}%")
            params.append(f"%APROVADA POR {clean_approver}%")
            params.append(f"%{clean_approver}%")

        # Lógica especial para KPIs
        if kpi_type == 'abertos':
            if start_date:
                query += " AND DM1744.DATA_CAD >= %s"
                params.append(int(start_date.replace('-', '')))
            if end_date:
                query += " AND DM1744.DATA_CAD <= %s"
                params.append(int(end_date.replace('-', '')))
        
        elif kpi_type == 'aprovados':
            # Chamados que tiveram o comentário de aprovação no período
            query += f""" AND EXISTS (
                SELECT 1 FROM BANCO01.DM1745 
                WHERE COD_SOLICITACAO = DM1744.COD_SOLICITACAO 
                  AND (UPPER({text_col}) LIKE '%%AUTORIZAÇÃO%%' AND UPPER({text_col}) LIKE '%%APROVADA%%')
            """
            if start_date:
                query += " AND DATA_GRAV >= %s"
                params.append(int(start_date.replace('-', '')))
            if end_date:
                query += " AND DATA_GRAV <= %s"
                params.append(int(end_date.replace('-', '')))
            query += ")"

        elif kpi_type == 'finalizados':
            query += " AND DM1744.COD_STATUS_DOC IN ('AV', 'BA')"
            if start_date:
                query += " AND DM1744.DATA_BAIXA >= %s"
                params.append(int(start_date.replace('-', '')))
            if end_date:
                query += " AND DM1744.DATA_BAIXA <= %s"
                params.append(int(end_date.replace('-', '')))

        elif kpi_type == 'encerrados':
            query += " AND DM1744.COD_STATUS_DOC = 'BA'"
            if start_date:
                query += " AND DM1744.DATA_BAIXA >= %s"
                params.append(int(start_date.replace('-', '')))
            if end_date:
                query += " AND DM1744.DATA_BAIXA <= %s"
                params.append(int(end_date.replace('-', '')))

        else:
            # Filtros normais se não for KPI
            if status_filter:
                flat_status = []
                for s in status_filter:
                    flat_status.extend(s.split(','))
                query += " AND DM1744.COD_STATUS_DOC IN %s"
                params.append(tuple(flat_status))
            
            if start_date:
                query += " AND DM1744.DATA_CAD >= %s"
                params.append(int(start_date.replace('-', '')))
                
            if end_date:
                query += " AND DM1744.DATA_CAD <= %s"
                params.append(int(end_date.replace('-', '')))
        
        # Filtros comuns a ambos
        if cod_solicitacao_filter:
            query += " AND DM1744.COD_SOLICITACAO = %s"
            params.append(cod_solicitacao_filter)
            
        if solicitante_filter:
            query += " AND UPPER(DS0300.NOME_USUARIO) LIKE %s"
            params.append(f"%{solicitante_filter.upper()}%")
        
        if assunto_filter:
            query += " AND DM1744.COD_ASSUNTO = %s"
            params.append(assunto_filter)
        
        if ativo_filter:
            # Lidar com ativos agrupados (múltiplos IDs separados por vírgula)
            if ',' in str(ativo_filter):
                ids = ativo_filter.split(',')
                placeholders = ','.join(['%s'] * len(ids))
                query += f" AND DM1744.COD_ATIVO IN ({placeholders})"
                params.extend(ids)
            else:
                query += " AND DM1744.COD_ATIVO = %s"
                params.append(ativo_filter)
        
        query += " ORDER BY DM1744.DATA_CAD DESC, DM1744.COD_SOLICITACAO DESC LIMIT 100"
        
        cur.execute(query, params)
        rows = cur.fetchall()
        columns = [col[0].lower() for col in cur.description]
        
        # Buscar notas locais para estes chamados
        ticket_ids = [int(row[columns.index('cod_solicitacao')]) for row in rows]
        tickets_with_notes = set()
        if ticket_ids:
            try:
                l_conn = get_local_connection()
                l_cur = l_conn.cursor()
                l_cur.execute(f"SELECT DISTINCT cod_solicitacao FROM notes WHERE cod_solicitacao IN ({','.join(['?'] * len(ticket_ids))})", ticket_ids)
                tickets_with_notes = {int(row[0]) for row in l_cur.fetchall()}
                l_conn.close()
            except: pass

        results = []
        for row in rows:
            d = dict(zip(columns, row))
            d['data_cad_fmt'] = format_erp_date(d['data_cad'])
            d['status_name'] = status_map.get(d['cod_status_doc'], d['cod_status_doc'])
            d['has_local_note'] = int(d['cod_solicitacao']) in tickets_with_notes
            d['tipo'] = classify_ticket(d['titulo_solicitacao']) # Classificar para permitir filtro
            
            # Aplicar filtro de tipo se existir
            if tipo_filter and d['tipo'] != tipo_filter:
                continue
                
            results.append(d)

        cur.close()
        conn.close()
        return jsonify(results)
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/api/local/note', methods=['POST'])
def save_local_note():
    try:
        data = request.json
        cod_solicitacao = data.get('cod_solicitacao')
        note = data.get('note')
        
        if not cod_solicitacao or not note:
            return jsonify({"error": "Dados incompletos"}), 400
            
        conn = get_local_connection()
        cur = conn.cursor()
        cur.execute("INSERT INTO notes (cod_solicitacao, note) VALUES (?, ?)", (cod_solicitacao, note))
        conn.commit()
        conn.close()
        return jsonify({"success": True})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/api/erp/chamado/<cod_solicitacao>')
def get_erp_chamado(cod_solicitacao):
    try:
        # Buscar Notas Locais (SQLite)
        local_notes = []
        try:
            l_conn = get_local_connection()
            l_cur = l_conn.cursor()
            l_cur.execute("SELECT note, created_at FROM notes WHERE cod_solicitacao = ? ORDER BY created_at DESC", (cod_solicitacao,))
            local_notes = [dict(row) for row in l_cur.fetchall()]
            l_conn.close()
        except: pass

        conn = get_erp_connection()
        cur = conn.cursor()
        
        # Consulta principal (DM1744)
        cur.execute("""
            SELECT 
                DM1744.PRIORIDADE, 
                DM1744.COD_STATUS_DOC, 
                DM1744.DATA_CAD, 
                DM1744.HORA_CAD,
                DM1744.DATA_INIC_ATEND,
                DM1744.HORA_INIC_ATEND,
                DM1744.DATA_BAIXA,
                DM1744.HORA_BAIXA,
                DM1744.COD_USUARIO,
                DS0300.NOME_USUARIO as SOLICITANTE,
                DM1744.COD_SOLICITACAO, 
                DM1744.TITULO_SOLICITACAO,
                DM1744.DESCR_SOLICITACAO,
                DC1629.DESCR_ATIVO,
                DC1629.IDENT_ATIVO as TAG
            FROM BANCO01.DM1744 
            LEFT JOIN public.DS0300 ON (DS0300.COD_USUARIO = DM1744.COD_USUARIO)
            LEFT JOIN BANCO01.DC1629 ON (DC1629.COD_ATIVO = DM1744.COD_ATIVO)
            WHERE DM1744.COD_SOLICITACAO = %s
        """, (cod_solicitacao,))
        
        row = cur.fetchone()
        if not row:
            return jsonify({"error": "Chamado não encontrado no ERP"}), 404

        columns = [col[0].lower() for col in cur.description]
        erp_data = dict(zip(columns, row))
        erp_data['data_cad_fmt'] = format_erp_date(erp_data['data_cad'])
        try:
            nome = (erp_data.get('solicitante') or '').strip()
            cod = erp_data.get('cod_usuario')
            if cod is not None and str(cod).strip() != '':
                erp_data['criador'] = f"{cod} - {nome}" if nome else f"{cod}"
            else:
                erp_data['criador'] = nome
        except Exception:
            erp_data['criador'] = erp_data.get('solicitante')
        erp_data['anotacoes_locais'] = local_notes # Adiciona as notas locais à resposta

        # Busca se o chamado já foi aprovado em algum momento (DM1745)
        # Vamos buscar todos os comentários e verificar no Python para evitar erros de nomes de colunas
        cur.execute("SELECT * FROM BANCO01.DM1745 WHERE COD_SOLICITACAO = %s ORDER BY DATA_GRAV DESC, HORA_GRAV DESC", (cod_solicitacao,))
        all_comments_rows = cur.fetchall()
        comment_cols = [col[0].lower() for col in cur.description]
        
        dt_abertura = erp_to_datetime(erp_data['data_cad'], erp_data.get('hora_cad'))

        # Analisar o Fluxo do Chamado (6 etapas)
        fluxo = {
            "abertura": {"status": "completed", "data": erp_data['data_cad_fmt'], "dt": dt_abertura},
            "primeiro_atendimento": {"status": "pending", "data": "", "dt": None},
            "autorizacao_gerencia": {"status": "pending", "data": "", "dt": None},
            "aprovado_andamento": {"status": "pending", "data": "", "dt": None},
            "finalizacao": {"status": "pending", "data": "", "dt": None},
            "encerramento": {"status": "pending", "data": "", "dt": None}
        }

        # 1. Primeiro Atendimento (usando coluna oficial se disponível)
        if erp_data.get('data_inic_atend') and int(erp_data['data_inic_atend']) > 0:
            dt_inic = erp_to_datetime(erp_data['data_inic_atend'], erp_data.get('hora_inic_atend'))
            fluxo["primeiro_atendimento"] = {"status": "completed", "data": format_erp_date(erp_data['data_inic_atend']), "dt": dt_inic}

        foi_aprovado = False
        comentarios_erp = []
        
        if all_comments_rows:
            text_col_idx = next((i for i, c in enumerate(comment_cols) if 'descr' in c or 'texto' in c or 'obs' in c), None)
            user_col_idx = next((i for i, c in enumerate(comment_cols) if 'usuario' in c or 'cod_usu' in c), None)
            date_col_idx = next((i for i, c in enumerate(comment_cols) if 'data' in c and 'grav' in c), None)
            time_col_idx = next((i for i, c in enumerate(comment_cols) if 'hora' in c and 'grav' in c), None)

            comms_asc = sorted(all_comments_rows, key=lambda r: (r[date_col_idx], r[time_col_idx]))
            
            for row in comms_asc:
                txt_content = str(row[text_col_idx]) if text_col_idx is not None else ""
                txt_upper = txt_content.upper()
                dt_fmt = format_erp_date(row[date_col_idx])
                dt_obj = erp_to_datetime(row[date_col_idx], row[time_col_idx])
                
                is_system_auth = "SOLICITAÇÃO DE AUTORIZAÇÃO" in txt_upper
                is_system_status_change = "SOLICITAÇÃO ATUALIZADA PARA O STATUS" in txt_upper
                is_system_msg = is_system_auth or is_system_status_change

                # Etapa 2: Primeiro Atendimento via comentário (fallback para comentário técnico manual)
                if fluxo["primeiro_atendimento"]["status"] == "pending" and not is_system_msg:
                    fluxo["primeiro_atendimento"] = {"status": "completed", "data": dt_fmt, "dt": dt_obj}
                
                # Etapa 3: Autorização da Gerência
                if ("SOLICITAÇÃO DE AUTORIZAÇÃO" in txt_upper and "FOI APROVADA" in txt_upper) or ("AUTORIZAÇÃO" in txt_upper and "APROVADA" in txt_upper):
                    if fluxo["autorizacao_gerencia"]["status"] == "pending":
                        fluxo["autorizacao_gerencia"] = {"status": "completed", "data": dt_fmt, "dt": dt_obj}
                
                # Etapa 4: Aprovado e em Andamento (Aprovação manual do técnico/gestor ou mudança de status)
                if ("SOLICITAÇÃO APROVADA POR" in txt_upper) or ("SOLICITAÇÃO ATUALIZADA PARA O STATUS: ANDAMENTO" in txt_upper) or ("SOLICITAÇÃO ATUALIZADA PARA O STATUS: EA" in txt_upper):
                    if fluxo["aprovado_andamento"]["status"] == "pending":
                        foi_aprovado = True
                        fluxo["aprovado_andamento"] = {"status": "completed", "data": dt_fmt, "dt": dt_obj}
                
                # Etapa 5: Finalização via comentário (fallback)
                if ("FINALIZAD" in txt_upper or "CONCLUÍD" in txt_upper or "SOLUCIONAD" in txt_upper or "RESOLVID" in txt_upper):
                    if fluxo["finalizacao"]["status"] == "pending":
                        fluxo["finalizacao"] = {"status": "completed", "data": dt_fmt, "dt": dt_obj}

                cod_usuario = row[user_col_idx]
                if cod_usuario and int(cod_usuario) > 0:
                    cur.execute("SELECT NOME_USUARIO FROM public.DS0300 WHERE COD_USUARIO = %s", (cod_usuario,))
                    u_row = cur.fetchone()
                    u_name = u_row[0] if u_row else "Desconhecido"
                    
                    comentarios_erp.insert(0, {
                        "data": dt_fmt,
                        "hora": format_erp_time(row[time_col_idx]) if time_col_idx is not None else "",
                        "usuario": u_name,
                        "texto": txt_content,
                        "destacar": ("AUTORIZAÇÃO" in txt_upper and "APROVADA" in txt_upper) or ("SOLICITAÇÃO" in txt_upper and "APROVADA" in txt_upper)
                    })

        # 5. Finalização T.I (Status AV - Aguardando Avaliação)
        if erp_data['cod_status_doc'] in ['AV', 'BA']:
            if fluxo["finalizacao"]["status"] == "pending":
                data_fin = comentarios_erp[0]['data'] if comentarios_erp else erp_data['data_cad_fmt']
                dt_fin = erp_to_datetime(erp_data.get('data_baixa'), erp_data.get('hora_baixa')) or dt_abertura
                fluxo["finalizacao"] = {"status": "completed", "data": data_fin, "dt": dt_fin}

        # 6. Encerramento (Status BA - Baixada)
        if erp_data['cod_status_doc'] == 'BA':
            data_baixa = format_erp_date(erp_data.get('data_baixa')) or erp_data['data_cad_fmt']
            dt_baixa = erp_to_datetime(erp_data.get('data_baixa'), erp_data.get('hora_baixa')) or dt_abertura
            fluxo["encerramento"] = {"status": "completed", "data": data_baixa, "dt": dt_baixa}

        # Calcular durações entre etapas (considerando etapas puladas)
        keys = ["abertura", "primeiro_atendimento", "autorizacao_gerencia", "aprovado_andamento", "finalizacao", "encerramento"]
        for i in range(len(keys)):
            k1 = keys[i]
            if fluxo[k1]["status"] == "completed":
                # Procurar a próxima etapa completada para calcular a duração
                for j in range(i + 1, len(keys)):
                    k2 = keys[j]
                    if fluxo[k2]["status"] == "completed":
                        dt1, dt2 = fluxo[k1]["dt"], fluxo[k2]["dt"]
                        if dt1 and dt2 and dt2 >= dt1:
                            fluxo[k1]["duracao_proxima"] = format_duration(dt2 - dt1)
                            # Se pulou etapas no meio, a duração deve ser visualmente atribuída à última etapa completada
                            # mas no HTML ela renderiza a partir da bolinha atual. 
                            # Para manter a linha contínua, vamos marcar as etapas intermediárias como 'skipped'
                            for mid in range(i + 1, j):
                                fluxo[keys[mid]]["status"] = "skipped"
                        break
            elif fluxo[k1]["status"] == "pending":
                fluxo[k1]["duracao_proxima"] = ""

        # Remover objetos datetime antes de enviar JSON
        for k in fluxo:
            if "dt" in fluxo[k]: del fluxo[k]["dt"]

        erp_data['foi_aprovado'] = foi_aprovado
        erp_data['comentarios_erp'] = comentarios_erp
        erp_data['fluxo_etapas'] = fluxo

        cur.close()
        conn.close()
        return jsonify(erp_data)
    except Exception as e:
        return jsonify({"error": str(e)}), 500

def extract_fields(filepath):
    with open(filepath, 'r', encoding='utf-8', errors='ignore') as f:
        content = f.read()
    fields = re.findall(r'\{\{(.*?)\}\}', content)
    return list(set(fields))

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/upload', methods=['POST'])
def upload_file():
    if 'rtf_file' not in request.files:
        return redirect(request.url)
    file = request.files['rtf_file']
    if file.filename == '':
        return redirect(request.url)
    if file:
        filename = secure_filename(file.filename)
        filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
        file.save(filepath)
        return redirect(url_for('edit_file', filename=filename))

@app.route('/edit/<filename>')
def edit_file(filename):
    filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
    fields = extract_fields(filepath)
    return render_template('edit.html', filename=filename, fields=fields)

@app.route('/generate/<filename>', methods=['POST'])
def generate_file(filename):
    original_filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
    with open(original_filepath, 'r', encoding='utf-8', errors='ignore') as f:
        content = f.read()

    form_data = request.form
    for field, value in form_data.items():
        content = content.replace(f'{{{{{field}}}}}', value)

    new_filename = f'generated_{filename}'
    generated_filepath = os.path.join(app.config['GENERATED_FOLDER'], new_filename)
    with open(generated_filepath, 'w', encoding='utf-8') as f:
        f.write(content)

    return send_file(generated_filepath, as_attachment=True)

@app.route('/api/erp/estatisticas')
def get_erp_stats():
    try:
        from datetime import datetime, timedelta
        now = datetime.now()
        
        # Obter datas do filtro via query params (formato YYYY-MM-DD)
        start_date_str = request.args.get('start_date')
        end_date_str = request.args.get('end_date')
        
        if start_date_str and end_date_str:
            start_dt = datetime.strptime(start_date_str, '%Y-%m-%d')
            end_dt = datetime.strptime(end_date_str, '%Y-%m-%d')
        else:
            # Padrão: últimos 7 dias
            end_dt = now
            start_dt = now - timedelta(days=6)
            
        today_erp = int(now.strftime('%Y%m%d'))
        
        # Gerar lista de dias no período
        period_days = []
        curr = start_dt
        while curr <= end_dt:
            period_days.append(int(curr.strftime('%Y%m%d')))
            curr += timedelta(days=1)
        
        conn = get_erp_connection()
        if not conn:
            # DADOS SIMULADOS PARA O DASHBOARD (Fallback em caso de falha de conexão)
            historico = []
            import random
            for d_erp in period_days:
                d_str = str(d_erp)
                historico.append({
                    "data": f"{d_str[6:8]}/{d_str[4:6]}",
                    "abertos": random.randint(10, 30),
                    "atendidos": random.randint(8, 25),
                    "aprovados": random.randint(5, 20),
                    "finalizados": random.randint(8, 28),
                    "encerrados": random.randint(5, 25)
                })
            
            return jsonify({
                "kpis": {
                    "abertos_hoje": 33,
                    "aprovados_hoje": 77,
                    "finalizados_hoje": 344,
                    "encerrados_hoje": 210
                },
                "historico": historico,
                "detalhes": [
                    {"codigo": "Aberta", "descricao": "Aberta", "quantidade": 33, "percentual": 7.25, "ignorar_percentual": False},
                    {"codigo": "Aguardando", "descricao": "Aguardando", "quantidade": 77, "percentual": 16.92, "ignorar_percentual": False},
                    {"codigo": "Andamento", "descricao": "Andamento", "quantidade": 344, "percentual": 75.60, "ignorar_percentual": False},
                    {"codigo": "Avaliação", "descricao": "Avaliação", "quantidade": 1, "percentual": 0.22, "ignorar_percentual": False}
                ],
                "distribuicao_tipos": {"Incidente": 120, "Requisição": 335}
            })

        cur = conn.cursor()
        
        # Identificar coluna de texto na DM1745 (comentários)
        cur.execute("SELECT * FROM BANCO01.DM1745 LIMIT 1")
        all_cols_1745 = [col[0].lower() for col in cur.description]
        text_col = next((c for c in all_cols_1745 if 'descr' in c or 'texto' in c or 'obs' in c), "DESCR_ACOMP")

        # Mapeamento de Status
        status_map = {
            'AA': 'Aguardando autorização',
            'IM': 'Aberta',
            'EA': 'Em andamento',
            'AV': 'Aguardando avaliação',
            'PR': 'Programada',
            'RT': 'Retrabalho',
            'BA': 'Encerrada',
            'RJ': 'Rejeitada'
        }

        # 1. Totais por categoria operacional (filtro Dept 16)
        # Sincronizado com os status reais do ERP conforme solicitado pelo usuário
        cur.execute(f"""
            SELECT 
                CASE 
                    WHEN DM1744.COD_STATUS_DOC IN ('EA', 'AN') THEN 'Andamento'
                    WHEN DM1744.COD_STATUS_DOC = 'AV' THEN 'Avaliação'
                    WHEN DM1744.COD_STATUS_DOC = 'AA' THEN 'Aguardando'
                    WHEN DM1744.COD_STATUS_DOC IN ('IM', 'AB') THEN 'Aberta'
                    ELSE DM1744.COD_STATUS_DOC
                END as categoria,
                COUNT(*),
                STRING_AGG(DM1744.TITULO_SOLICITACAO, '|||') as titulos
            FROM BANCO01.DM1744 
            WHERE DM1744.COD_ASSUNTO IN (SELECT COD_ASSUNTO FROM BANCO01.DC1966 WHERE COD_DEPAR = 16)
            GROUP BY categoria
        """)
        rows = cur.fetchall()
        
        # Calcular distribuição de tipos (Incidente vs Requisição) usando a "I.A"
        # Somente para as 4 categorias solicitadas: Aberta, Aguardando, Andamento, Avaliação
        categorias_alvo = ['Aberta', 'Aguardando', 'Andamento', 'Avaliação']
        distribuicao_tipos = {"Incidente": 0, "Requisição": 0, "BI": 0}
        for row in rows:
            if row[0] in categorias_alvo:
                titulos = row[2].split('|||') if row[2] else []
                for t in titulos:
                    tipo = classify_ticket(t)
                    distribuicao_tipos[tipo] += 1

        # 2. Histórico do período (Abertos, Atendidos, Aprovados, Finalizados, Encerrados)
        historico = []
        for d_erp in period_days:
            # Abertos
            cur.execute(f"""
                SELECT COUNT(*) FROM BANCO01.DM1744 
                WHERE DATA_CAD = %s 
                  AND COD_ASSUNTO IN (SELECT COD_ASSUNTO FROM BANCO01.DC1966 WHERE COD_DEPAR = 16)
            """, (d_erp,))
            abertos = cur.fetchone()[0]

            # Atendidos
            cur.execute(f"""
                SELECT COUNT(*) FROM BANCO01.DM1744 
                WHERE DATA_INIC_ATEND = %s 
                  AND COD_ASSUNTO IN (SELECT COD_ASSUNTO FROM BANCO01.DC1966 WHERE COD_DEPAR = 16)
            """, (d_erp,))
            atendidos = cur.fetchone()[0]

            # Aprovados
            cur.execute(f"""
                SELECT COUNT(DISTINCT DM1745.COD_SOLICITACAO) 
                FROM BANCO01.DM1745
                INNER JOIN BANCO01.DM1744 ON (DM1744.COD_SOLICITACAO = DM1745.COD_SOLICITACAO)
                WHERE DM1745.DATA_GRAV = %s 
                  AND DM1744.COD_ASSUNTO IN (SELECT COD_ASSUNTO FROM BANCO01.DC1966 WHERE COD_DEPAR = 16)
                  AND (UPPER({text_col}) LIKE '%%AUTORIZAÇÃO%%' AND UPPER({text_col}) LIKE '%%APROVADA%%')
            """, (d_erp,))
            aprovados = cur.fetchone()[0]

            # Finalizados
            cur.execute(f"""
                SELECT COUNT(*) FROM BANCO01.DM1744 
                WHERE DATA_BAIXA = %s AND COD_STATUS_DOC IN ('AV', 'BA')
                  AND COD_ASSUNTO IN (SELECT COD_ASSUNTO FROM BANCO01.DC1966 WHERE COD_DEPAR = 16)
            """, (d_erp,))
            finalizados = cur.fetchone()[0]

            # Encerrados
            cur.execute(f"""
                SELECT COUNT(*) FROM BANCO01.DM1744 
                WHERE DATA_BAIXA = %s AND COD_STATUS_DOC = 'BA'
                  AND COD_ASSUNTO IN (SELECT COD_ASSUNTO FROM BANCO01.DC1966 WHERE COD_DEPAR = 16)
            """, (d_erp,))
            encerrados = cur.fetchone()[0]

            d_str = str(d_erp)
            historico.append({
                "data": f"{d_str[6:8]}/{d_str[4:6]}",
                "abertos": abertos,
                "atendidos": atendidos,
                "aprovados": aprovados,
                "finalizados": finalizados,
                "encerrados": encerrados
            })

        # 3. KPIs de HOJE
        # Abertos hoje
        cur.execute(f"""
            SELECT COUNT(*) FROM BANCO01.DM1744 
            WHERE DATA_CAD = %s 
              AND COD_ASSUNTO IN (SELECT COD_ASSUNTO FROM BANCO01.DC1966 WHERE COD_DEPAR = 16)
        """, (today_erp,))
        total_abertos_hoje = cur.fetchone()[0]

        # Aprovados hoje
        cur.execute(f"""
            SELECT COUNT(DISTINCT DM1744.COD_SOLICITACAO) 
            FROM BANCO01.DM1744
            INNER JOIN BANCO01.DM1745 ON (DM1745.COD_SOLICITACAO = DM1744.COD_SOLICITACAO)
            WHERE DM1745.DATA_GRAV = %s 
              AND DM1744.COD_ASSUNTO IN (SELECT COD_ASSUNTO FROM BANCO01.DC1966 WHERE COD_DEPAR = 16)
              AND (UPPER({text_col}) LIKE '%%AUTORIZAÇÃO%%' AND UPPER({text_col}) LIKE '%%APROVADA%%')
        """, (today_erp,))
        total_aprovados_hoje = cur.fetchone()[0]

        # Finalizados hoje (T.I enviou para AV)
        cur.execute(f"""
            SELECT COUNT(*) FROM BANCO01.DM1744 
            WHERE DATA_BAIXA = %s AND COD_STATUS_DOC IN ('AV', 'BA')
              AND COD_ASSUNTO IN (SELECT COD_ASSUNTO FROM BANCO01.DC1966 WHERE COD_DEPAR = 16)
        """, (today_erp,))
        total_finalizados_hoje = cur.fetchone()[0]

        # Encerrados hoje (Status BA definitivo)
        cur.execute(f"""
            SELECT COUNT(*) FROM BANCO01.DM1744 
            WHERE DATA_BAIXA = %s AND COD_STATUS_DOC = 'BA'
              AND COD_ASSUNTO IN (SELECT COD_ASSUNTO FROM BANCO01.DC1966 WHERE COD_DEPAR = 16)
        """, (today_erp,))
        total_encerrados_hoje = cur.fetchone()[0]

        # Processar totais e percentuais (Distribuição Geral)
        categorias_ativas = ['Aberta', 'Aguardando', 'Andamento', 'Avaliação']
        rows_para_percentual = [row for row in rows if row[0] in categorias_ativas]
        total_para_percentual = sum(row[1] for row in rows_para_percentual)
        
        stats = []
        for row in rows:
            cat = row[0]
            count = row[1]
            percent = (count / total_para_percentual * 100) if total_para_percentual > 0 and cat in categorias_ativas else 0
            stats.append({
                "codigo": cat,
                "descricao": cat,
                "quantidade": count,
                "percentual": round(percent, 2),
                "ignorar_percentual": cat not in categorias_ativas
            })

        # 4. Cálculo de Tempo Médio por Etapa (Baseado em chamados recentes para performance)
        cur.execute(f"""
            SELECT COD_SOLICITACAO, DATA_CAD, HORA_CAD, DATA_INIC_ATEND, HORA_INIC_ATEND, DATA_BAIXA, HORA_BAIXA, COD_STATUS_DOC
            FROM BANCO01.DM1744 
            WHERE DM1744.COD_ASSUNTO IN (SELECT COD_ASSUNTO FROM BANCO01.DC1966 WHERE COD_DEPAR = 16)
            ORDER BY DATA_CAD DESC, HORA_CAD DESC
            LIMIT 200
        """)
        recent_tickets = cur.fetchall()
        
        # Estrutura para acumular tempos de transição
        transitions = {
            "abertura_atendimento": [],
            "atendimento_autorizacao": [],
            "autorizacao_aprovacao": [],
            "aprovacao_finalizacao": [],
            "finalizacao_encerramento": []
        }
        
        for t in recent_tickets:
            tid, d_cad, h_cad, d_atend, h_atend, d_baixa, h_baixa, status = t
            dt_abertura = erp_to_datetime(d_cad, h_cad)
            
            # 1. Abertura -> Primeiro Atendimento
            dt_atendimento = None
            if d_atend and int(d_atend) > 0:
                dt_atendimento = erp_to_datetime(d_atend, h_atend)
                if dt_atendimento and dt_abertura:
                    transitions["abertura_atendimento"].append((dt_atendimento - dt_abertura).total_seconds())
            
            # Buscar comentários para etapas intermediárias
            cur.execute(f"SELECT DATA_GRAV, HORA_GRAV, UPPER({text_col}) FROM BANCO01.DM1745 WHERE COD_SOLICITACAO = %s ORDER BY DATA_GRAV ASC, HORA_GRAV ASC", (tid,))
            comms = cur.fetchall()
            
            dt_autorizacao = None
            dt_aprovacao = None
            
            for c_date, c_time, c_text in comms:
                dt_c = erp_to_datetime(c_date, c_time)
                
                # 2. Atendimento -> Autorização Gerência
                if ("SOLICITAÇÃO DE AUTORIZAÇÃO" in c_text and "FOI ENVIADA" in c_text) and dt_atendimento and not dt_autorizacao:
                    dt_autorizacao = dt_c
                    transitions["atendimento_autorizacao"].append((dt_c - dt_atendimento).total_seconds())
                
                # 3. Autorização -> Aprovação
                if ("SOLICITAÇÃO DE AUTORIZAÇÃO" in c_text and "FOI APROVADA" in c_text) and dt_autorizacao and not dt_aprovacao:
                    dt_aprovacao = dt_c
                    transitions["autorizacao_aprovacao"].append((dt_c - dt_autorizacao).total_seconds())
                
                # Fallback: Se aprovou direto sem autorização (pular etapa)
                if ("SOLICITAÇÃO APROVADA POR" in c_text or "SOLICITAÇÃO ATUALIZADA PARA O STATUS: ANDAMENTO" in c_text) and dt_atendimento and not dt_aprovacao:
                    dt_aprovacao = dt_c
                    # Opcional: Se quiser contar como autorização instantânea, mas vamos focar nas transições reais
            
            # 4. Aprovação -> Finalização (Status AV ou BA)
            dt_finalizacao = None
            if status in ['AV', 'BA'] and d_baixa and int(d_baixa) > 0 and dt_aprovacao:
                dt_finalizacao = erp_to_datetime(d_baixa, h_baixa)
                if dt_finalizacao:
                    transitions["aprovacao_finalizacao"].append((dt_finalizacao - dt_aprovacao).total_seconds())
            
            # 5. Finalização -> Encerramento (Status BA definitivo)
            if status == 'BA' and d_baixa and int(d_baixa) > 0 and dt_finalizacao:
                # No ERP, a baixa final pode ser o mesmo timestamp ou posterior
                # Para fins de gráfico, vamos considerar a transição se houver delay registrado
                dt_encerramento = erp_to_datetime(d_baixa, h_baixa)
                if dt_encerramento and dt_finalizacao:
                    diff = (dt_encerramento - dt_finalizacao).total_seconds()
                    if diff > 0:
                        transitions["finalizacao_encerramento"].append(diff)

        def get_avg(key):
            lst = transitions[key]
            return format_duration_short(sum(lst)/len(lst)) if lst else "0m"

        tempos_medios = {
            "Abertura → Atendimento": get_avg("abertura_atendimento"),
            "Atendimento → Autorização": get_avg("atendimento_autorizacao"),
            "Autorização → Aprovação": get_avg("autorizacao_aprovacao"),
            "Aprovação → Finalização": get_avg("aprovacao_finalizacao"),
            "Finalização → Encerramento": get_avg("finalizacao_encerramento")
        }

        cur.close()
        conn.close()
        return jsonify({
            "kpis": {
                "abertos_hoje": total_abertos_hoje,
                "aprovados_hoje": total_aprovados_hoje,
                "finalizados_hoje": total_finalizados_hoje,
                "encerrados_hoje": total_encerrados_hoje
            },
            "historico": historico,
            "detalhes": stats,
            "distribuicao_tipos": distribuicao_tipos,
            "tempos_medios": tempos_medios
        })
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/api/erp/kanban')
def get_kanban_data():
    try:
        # Filtros opcionais
        f_id = request.args.get('id')
        f_solicitante = request.args.get('solicitante')
        f_start = request.args.get('start_date')
        f_end = request.args.get('end_date')
        f_statuses = request.args.getlist('status')
        f_tipo = request.args.get('tipo')
        f_assunto = request.args.get('assunto')
        f_ativo = request.args.get('ativo')
        f_aprovador = request.args.get('aprovador') # Novo filtro de Aprovador

        conn = get_erp_connection()
        cur = conn.cursor()
        
        # Identificar coluna de texto na DM1745
        cur.execute("SELECT * FROM BANCO01.DM1745 LIMIT 1")
        all_cols_1745 = [col[0].lower() for col in cur.description]
        text_col = next((c for c in all_cols_1745 if 'descr' in c or 'texto' in c or 'obs' in c), "DESCR_ACOMP")

        query_base = """
            SELECT 
                DM1744.COD_SOLICITACAO, 
                DM1744.TITULO_SOLICITACAO,
                DM1744.COD_STATUS_DOC
            FROM BANCO01.DM1744 
            LEFT JOIN BANCO01.DC1739 ON (DC1739.COD_ASSUNTO = DM1744.COD_ASSUNTO)
            WHERE DM1744.COD_ASSUNTO IN (SELECT COD_ASSUNTO FROM BANCO01.DC1966 WHERE COD_DEPAR = 16)
        """
        params_base = []

        if f_id:
            query_base += " AND DM1744.COD_SOLICITACAO = %s "
            params_base.append(f_id)
        if f_solicitante:
            query_base += " AND DM1744.SOLICITANTE LIKE %s "
            params_base.append(f'%{f_solicitante}%')
        if f_start:
            query_base += " AND DM1744.DATA_CAD >= %s "
            params_base.append(f_start.replace('-', ''))
        if f_end:
            query_base += " AND DM1744.DATA_CAD <= %s "
            params_base.append(f_end.replace('-', ''))
        
        if f_assunto:
            query_base += " AND DM1744.COD_ASSUNTO = %s "
            params_base.append(f_assunto)
        
        if f_ativo:
            if ',' in str(f_ativo):
                ids = f_ativo.split(',')
                placeholders = ','.join(['%s'] * len(ids))
                query_base += f" AND DM1744.COD_ATIVO IN ({placeholders}) "
                params_base.extend(ids)
            else:
                query_base += " AND DM1744.COD_ATIVO = %s "
                params_base.append(f_ativo)
        
        if f_aprovador:
            # Limpar o nome do aprovador para busca mais flexível (remover sufixos TI)
            clean_approver = f_aprovador.upper().split(" - ")[0].split(" -")[0].strip()
            query_base += f""" AND (
                EXISTS (
                    SELECT 1 FROM BANCO01.DM1745 
                    JOIN public.DS0300 ON (DS0300.COD_USUARIO = DM1745.COD_USUARIO)
                    WHERE DM1745.COD_SOLICITACAO = DM1744.COD_SOLICITACAO 
                      AND (UPPER({text_col}) LIKE '%%AUTORIZAÇÃO%%' AND UPPER({text_col}) LIKE '%%APROVADA%%')
                      AND (UPPER(DS0300.NOME_USUARIO) LIKE %s OR UPPER({text_col}) LIKE %s)
                ) OR EXISTS (
                    SELECT 1 FROM public.DS0300 DSRESP
                    WHERE DSRESP.COD_USUARIO = DM1744.COD_USUARIO_RESPONS
                      AND UPPER(DSRESP.NOME_USUARIO) LIKE %s
                )
            ) """
            params_base.append(f'%{clean_approver}%')
            params_base.append(f'%APROVADA POR {clean_approver}%')
            params_base.append(f'%{clean_approver}%')

        if f_statuses:
            placeholders = ','.join(['%s'] * len(f_statuses))
            query_base += f" AND DM1744.COD_STATUS_DOC IN ({placeholders}) "
            params_base.extend(f_statuses)

        # Coluna 1: Aberta
        # Filtramos adicionalmente pelos status da coluna
        q_aberta = query_base + " AND DM1744.COD_STATUS_DOC IN ('IM', 'AB') ORDER BY DM1744.DATA_CAD ASC, DM1744.HORA_CAD ASC"
        cur.execute(q_aberta, params_base)
        rows_aberta = cur.fetchall()
        aberta = []
        for row in rows_aberta:
            d = dict(zip(['id', 'titulo', 'status'], row))
            cur.execute("SELECT 1 FROM BANCO01.DM1745 WHERE COD_SOLICITACAO = %s AND COD_USUARIO > 0 LIMIT 1", (d['id'],))
            d['no_iteration'] = cur.fetchone() is None
            aberta.append(d)

        # Coluna 2: Aguardando
        q_aguardando = query_base + " AND DM1744.COD_STATUS_DOC = 'AA' ORDER BY DM1744.DATA_CAD ASC, DM1744.HORA_CAD ASC"
        cur.execute(q_aguardando, params_base)
        aguardando = [dict(zip(['id', 'titulo', 'status'], row)) for row in cur.fetchall()]

        # Coluna 3: Andamento
        q_andamento = query_base + " AND DM1744.COD_STATUS_DOC IN ('EA', 'AN') ORDER BY DM1744.DATA_CAD ASC, DM1744.HORA_CAD ASC"
        cur.execute(q_andamento, params_base)
        andamento = [dict(zip(['id', 'titulo', 'status'], row)) for row in cur.fetchall()]

        # Coluna 4: Avaliação
        q_avaliacao = query_base + " AND DM1744.COD_STATUS_DOC = 'AV' ORDER BY DM1744.DATA_CAD ASC, DM1744.HORA_CAD ASC"
        cur.execute(q_avaliacao, params_base)
        avaliacao = [dict(zip(['id', 'titulo', 'status'], row)) for row in cur.fetchall()]

        # Buscar notas locais para todos os IDs coletados
        all_ids = [int(t['id']) for t in aberta + aguardando + andamento + avaliacao]
        tickets_with_notes = set()
        if all_ids:
            try:
                l_conn = get_local_connection()
                l_cur = l_conn.cursor()
                l_cur.execute(f"SELECT DISTINCT cod_solicitacao FROM notes WHERE cod_solicitacao IN ({','.join(['?'] * len(all_ids))})", all_ids)
                tickets_with_notes = {int(row[0]) for row in l_cur.fetchall()}
                l_conn.close()
            except: pass

        # Processar cada chamado
        for t in aberta + aguardando + andamento + avaliacao:
            t['has_note'] = int(t['id']) in tickets_with_notes
            t['tipo'] = classify_ticket(t['titulo'])
            
            # Verificar status de autorização
            cur.execute(f"SELECT UPPER({text_col}) FROM BANCO01.DM1745 WHERE COD_SOLICITACAO = %s", (t['id'],))
            comentarios = [row[0] for row in cur.fetchall() if row[0]]
            
            t['waiting_auth'] = any('SOLICIT' in c and 'AUTORIZAÇÃO' in c for c in comentarios)
            t['auth_approved'] = any(('AUTORIZAÇÃO' in c and 'APROVADA' in c) or 'SOLICITAÇÃO APROVADA' in c for c in comentarios)
            
            # Se já aprovou, não está mais "esperando"
            if t['auth_approved']: t['waiting_auth'] = False

        # Filtro de tipo por Python (já que a classificação é via heurística)
        if f_tipo:
            aberta = [t for t in aberta if t['tipo'] == f_tipo]
            aguardando = [t for t in aguardando if t['tipo'] == f_tipo]
            andamento = [t for t in andamento if t['tipo'] == f_tipo]
            avaliacao = [t for t in avaliacao if t['tipo'] == f_tipo]

        cur.close()
        conn.close()
        return jsonify({
            "aberta": aberta,
            "aguardando": aguardando,
            "andamento": andamento,
            "avaliacao": avaliacao
        })
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/api/erp/chamados_pendentes')
def get_pending_tickets():
    try:
        conn = get_erp_connection()
        cur = conn.cursor()
        
        # Chamados 'IM' (Aberta) sem registros na DM1745 (iterações)
        # Filtramos pelo Depto 16
        query = """
            SELECT 
                DM1744.COD_SOLICITACAO, 
                DM1744.TITULO_SOLICITACAO, 
                DM1744.DATA_CAD, 
                DM1744.HORA_CAD,
                DS0300.NOME_USUARIO as SOLICITANTE
            FROM BANCO01.DM1744 
            LEFT JOIN public.DS0300 ON (DS0300.COD_USUARIO = DM1744.COD_USUARIO)
            WHERE DM1744.COD_STATUS_DOC = 'IM'
              AND DM1744.COD_ASSUNTO IN (
                  SELECT COD_ASSUNTO 
                  FROM BANCO01.DC1966 
                  WHERE COD_DEPAR = 16
              )
              AND NOT EXISTS (
                  SELECT 1 FROM BANCO01.DM1745 
                  WHERE COD_SOLICITACAO = DM1744.COD_SOLICITACAO 
                    AND COD_USUARIO > 0
              )
            ORDER BY DM1744.DATA_CAD ASC, DM1744.HORA_CAD ASC
        """
        
        cur.execute(query)
        rows = cur.fetchall()
        columns = [col[0].lower() for col in cur.description]
        
        # Buscar quais destes chamados têm notas locais
        ticket_ids = [int(row[0]) for row in rows if row[0]]
        tickets_with_notes = set()
        if ticket_ids:
            try:
                l_conn = get_local_connection()
                l_cur = l_conn.cursor()
                # Não usamos row_factory aqui para facilitar a extração direta do set
                l_cur.execute(f"SELECT DISTINCT cod_solicitacao FROM notes WHERE cod_solicitacao IN ({','.join(['?'] * len(ticket_ids))})", ticket_ids)
                tickets_with_notes = {int(row[0]) for row in l_cur.fetchall()}
                l_conn.close()
            except Exception as e:
                print(f"Erro ao buscar notas locais: {e}")
                pass

        results = []
        for row in rows:
            d = dict(zip(columns, row))
            # Formatar a hora de CAD para algo usável (HH.MMSS -> HH:MM:SS)
            h_val = float(d['hora_cad']) if d['hora_cad'] else 0
            hh = int(h_val)
            mm = int((h_val - hh) * 100)
            ss = int(((h_val - hh) * 100 - mm) * 100)
            d['hora_cad_fmt'] = f"{hh:02d}:{mm:02d}:{ss:02d}"
            
            # Formatar a data (YYYYMMDD -> YYYY-MM-DD)
            dt_str = str(d['data_cad'])
            d['data_cad_iso'] = f"{dt_str[0:4]}-{dt_str[4:6]}-{dt_str[6:8]}"
            
            d['has_local_note'] = int(d['cod_solicitacao']) in tickets_with_notes
            d['tipo'] = classify_ticket(d['titulo_solicitacao'])
            
            results.append(d)

        cur.close()
        conn.close()
        return jsonify(results)
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/produtividade')
def produtividade_page():
    return render_template('produtividade.html')

@app.route('/chamados')
def chamados_page():
    return render_template('chamados.html')

@app.route('/api/erp/produtividade')
def get_erp_productivity():
    try:
        from datetime import datetime, timedelta
        start_date_str = request.args.get('start_date')
        end_date_str = request.args.get('end_date')
        
        if start_date_str and end_date_str:
            start_dt = datetime.strptime(start_date_str, '%Y-%m-%d')
            end_dt = datetime.strptime(end_date_str, '%Y-%m-%d')
        else:
            now = datetime.now()
            end_dt = now
            start_dt = now - timedelta(days=6)

        period_days = []
        curr = start_dt
        while curr <= end_dt:
            period_days.append(int(curr.strftime('%Y%m%d')))
            curr += timedelta(days=1)

        conn = get_erp_connection()
        cur = conn.cursor()

        # Identificar coluna de texto na DM1745 (comentários)
        cur.execute("SELECT * FROM BANCO01.DM1745 LIMIT 1")
        all_cols_1745 = [col[0].lower() for col in cur.description]
        text_col = next((c for c in all_cols_1745 if 'descr' in c or 'texto' in c or 'obs' in c), "DESCR_ACOMP")

        results = []
        for d_erp in reversed(period_days):
            # Buscar todos os chamados que tiveram alguma movimentação no dia (Data de Cadastro ou Data de Baixa)
            cur.execute(f"""
                SELECT 
                    DM1744.COD_SOLICITACAO,
                    DM1744.TITULO_SOLICITACAO,
                    DM1744.COD_STATUS_DOC,
                    DM1744.DATA_CAD,
                    DM1744.DATA_BAIXA,
                    DM1744.DATA_INIC_ATEND
                FROM BANCO01.DM1744
                WHERE (DM1744.DATA_CAD = %s OR DM1744.DATA_BAIXA = %s OR DM1744.DATA_INIC_ATEND = %s)
                  AND DM1744.COD_ASSUNTO IN (SELECT COD_ASSUNTO FROM BANCO01.DC1966 WHERE COD_DEPAR = 16)
                ORDER BY DM1744.COD_SOLICITACAO DESC
            """, (d_erp, d_erp, d_erp))
            
            tickets = cur.fetchall()
            day_data = {
                "data": f"{str(d_erp)[6:8]}/{str(d_erp)[4:6]}/{str(d_erp)[0:4]}",
                "chamados": []
            }

            for t in tickets:
                cod = t[0]
                titulo = t[1]
                status = t[2]
                
                # Buscar todos os comentários do chamado para análise de quem fez o quê
                cur.execute(f"""
                    SELECT 
                        DS0300.NOME_USUARIO,
                        DM1745.{text_col},
                        DM1745.DATA_GRAV,
                        DM1745.HORA_GRAV
                    FROM BANCO01.DM1745 
                    JOIN public.DS0300 ON (DS0300.COD_USUARIO = DM1745.COD_USUARIO)
                    WHERE DM1745.COD_SOLICITACAO = %s AND DM1745.COD_USUARIO > 0
                    ORDER BY DM1745.DATA_GRAV ASC, DM1745.HORA_GRAV ASC
                """, (cod,))
                comms = cur.fetchall()

                atendente = "---"
                aprovador = "---"
                finalizador = "---"
                encerrador = "---"

                if comms:
                    # 1. Atendimento Iniciado por (Primeiro comentário técnico)
                    atendente = comms[0][0]

                    for c in comms:
                        u_name = c[0]
                        txt = str(c[1]).upper()

                        # 2. Aprovador (Busca no texto por "APROVADA POR [NOME]")
                        if "APROVADA POR" in txt:
                            # Tenta extrair o nome após "APROVADA POR "
                            try:
                                parts = txt.split("APROVADA POR")
                                if len(parts) > 1:
                                    # Pega o que vem depois e limpa (pode ter status depois)
                                    nome_extraido = parts[1].split(".")[0].split("\r")[0].split("\n")[0].strip()
                                    aprovador = nome_extraido if nome_extraido else u_name
                                else:
                                    aprovador = u_name
                            except:
                                aprovador = u_name
                        elif ("AUTORIZAÇÃO" in txt and "APROVADA" in txt):
                            aprovador = u_name
                        
                        # 3. Finalizador (Busca no texto por "FINALIZADA POR [NOME]")
                        if "FINALIZADA POR" in txt:
                            try:
                                parts = txt.split("FINALIZADA POR")
                                if len(parts) > 1:
                                    nome_extraido = parts[1].split(".")[0].split("\r")[0].split("\n")[0].strip()
                                    finalizador = nome_extraido if nome_extraido else u_name
                                else:
                                    finalizador = u_name
                            except:
                                finalizador = u_name
                        elif "SOLICITAÇÃO FINALIZADA" in txt or "FINALIZADO" in txt:
                            finalizador = u_name

                        # 4. Encerrador (Se o status é BA, o último comentário técnico costuma ser o encerramento)
                        if status == 'BA':
                            encerrador = comms[-1][0]

                day_data["chamados"].append({
                    "cod": cod,
                    "titulo": titulo,
                    "atendente": atendente,
                    "aprovador": aprovador,
                    "finalizador": finalizador,
                    "encerrador": encerrador,
                    "status": status
                })
            
            if day_data["chamados"]:
                results.append(day_data)

        cur.close()
        conn.close()
        return jsonify(results)
    except Exception as e:
        return jsonify({"error": str(e)}), 500

if __name__ == '__main__':
    os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
    os.makedirs(app.config['GENERATED_FOLDER'], exist_ok=True)
    init_local_db()
    app.run(debug=True, host='0.0.0.0', port=5000)
