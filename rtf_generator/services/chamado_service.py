from utils.datetime_utils import format_erp_date, format_erp_time, erp_to_datetime, format_duration
from utils.classifier import classify_ticket

class ChamadoService:
    def __init__(self, erp_repo, local_repo):
        self.erp_repo = erp_repo
        self.local_repo = local_repo

    def listar_chamados(self, filtros):
        """
        Lista chamados com base em múltiplos filtros e enriquece com dados locais.
        """
        # 1. Construir query base no repositório
        # O repositório já tem buscar_chamados_lista que aceita query e params
        # Vamos construir a query aqui ou delegar para o repositório?
        # Para seguir o padrão Service-Repository, a lógica de construção de query 
        # complexa (especialmente filtros de texto e subqueries) deve estar no repositório
        # ou o Service deve passar os parâmetros limpos.
        
        # Como o repositório erp_repository.py já tem uma estrutura, vamos usar buscar_chamados_lista
        # Mas precisamos que o repositório forneça uma forma de filtrar.
        # Vou atualizar o ERPRepository para ter um método mais amigável de listagem.
        
        # Por enquanto, vamos implementar a lógica de enriquecimento aqui
        results = self.erp_repo.listar_chamados_com_filtros(filtros)
        
        # Buscar notas locais em lote para os IDs retornados
        ticket_ids = [int(r['cod_solicitacao']) for r in results]
        tickets_with_notes = self.local_repo.get_ticket_ids_with_notes(ticket_ids) if ticket_ids else set()
        
        # Enriquecer resultados
        enriquecidos = []
        for d in results:
            d['data_cad_fmt'] = format_erp_date(d['data_cad'])
            # status_name já deve vir do repositório ou ser mapeado aqui
            d['has_local_note'] = int(d['cod_solicitacao']) in tickets_with_notes
            d['tipo'] = classify_ticket(d['titulo_solicitacao'])
            
            # Filtro de tipo por Python (pós-classificação)
            tipo_filter = filtros.get('tipo')
            if tipo_filter and d['tipo'] != tipo_filter:
                continue
                
            enriquecidos.append(d)
            
        return enriquecidos

    def detalhar_chamado(self, cod_solicitacao):
        # 1. Buscar notas locais
        local_notes = self.local_repo.get_notes_by_ticket(cod_solicitacao)
        
        # 2. Buscar dados base do ERP
        erp_data = self.erp_repo.buscar_chamado_por_id(cod_solicitacao)
        if not erp_data:
            return None

        # 3. Buscar comentários
        comentarios = self.erp_repo.buscar_comentarios_chamado(cod_solicitacao)
        
        # 4. Formatação e Enriquecimento
        erp_data['data_cad_fmt'] = format_erp_date(erp_data['data_cad'])
        erp_data['anotacoes_locais'] = local_notes
        
        # 5. Analisar Fluxo (Lógica extraída do app.py)
        dt_abertura = erp_to_datetime(erp_data['data_cad'], erp_data.get('hora_cad'))
        fluxo = {
            "abertura": {"status": "completed", "data": erp_data['data_cad_fmt'], "dt": dt_abertura},
            "primeiro_atendimento": {"status": "pending", "data": "", "dt": None},
            "autorizacao_gerencia": {"status": "pending", "data": "", "dt": None},
            "aprovado_andamento": {"status": "pending", "data": "", "dt": None},
            "finalizacao": {"status": "pending", "data": "", "dt": None},
            "encerramento": {"status": "pending", "data": "", "dt": None}
        }

        # Primeiro Atendimento oficial
        if erp_data.get('data_inic_atend') and int(erp_data['data_inic_atend']) > 0:
            dt_inic = erp_to_datetime(erp_data['data_inic_atend'], erp_data.get('hora_inic_atend'))
            fluxo["primeiro_atendimento"] = {"status": "completed", "data": format_erp_date(erp_data['data_inic_atend']), "dt": dt_inic}

        foi_aprovado = False
        comentarios_fmt = []
        
        # Ordenar comentários para análise de fluxo (ASC para cronologia)
        comms_asc = sorted(comentarios, key=lambda r: (r['data_grav'], r['hora_grav']))
        
        for row in comms_asc:
            # Identificar colunas de texto de forma dinâmica (como no repositório)
            txt_content = str(row.get('descr_acompanhante') or row.get('descr_acomp') or row.get('texto') or row.get('obs') or "")
            txt_upper = txt_content.upper()
            dt_fmt = format_erp_date(row['data_grav'])
            dt_obj = erp_to_datetime(row['data_grav'], row['hora_grav'])
            
            is_system_auth = "SOLICITAÇÃO DE AUTORIZAÇÃO" in txt_upper
            is_system_status_change = "SOLICITAÇÃO ATUALIZADA PARA O STATUS" in txt_upper
            is_system_msg = is_system_auth or is_system_status_change

            # Etapa 2: Primeiro Atendimento via comentário (fallback)
            if fluxo["primeiro_atendimento"]["status"] == "pending" and not is_system_msg:
                fluxo["primeiro_atendimento"] = {"status": "completed", "data": dt_fmt, "dt": dt_obj}
            
            # Etapa 3: Autorização da Gerência
            if ("SOLICITAÇÃO DE AUTORIZAÇÃO" in txt_upper and "FOI APROVADA" in txt_upper) or ("AUTORIZAÇÃO" in txt_upper and "APROVADA" in txt_upper):
                if fluxo["autorizacao_gerencia"]["status"] == "pending":
                    fluxo["autorizacao_gerencia"] = {"status": "completed", "data": dt_fmt, "dt": dt_obj}
            
            # Etapa 4: Aprovado e em Andamento
            if ("SOLICITAÇÃO APROVADA POR" in txt_upper) or ("SOLICITAÇÃO ATUALIZADA PARA O STATUS: ANDAMENTO" in txt_upper) or ("SOLICITAÇÃO ATUALIZADA PARA O STATUS: EA" in txt_upper):
                if fluxo["aprovado_andamento"]["status"] == "pending":
                    foi_aprovado = True
                    fluxo["aprovado_andamento"] = {"status": "completed", "data": dt_fmt, "dt": dt_obj}
            
            # Etapa 5: Finalização via comentário (fallback)
            if ("FINALIZAD" in txt_upper or "CONCLUÍD" in txt_upper or "SOLUCIONAD" in txt_upper or "RESOLVID" in txt_upper):
                if fluxo["finalizacao"]["status"] == "pending":
                    fluxo["finalizacao"] = {"status": "completed", "data": dt_fmt, "dt": dt_obj}

            # Formatar comentário para exibição (reverso no final ou inserção no topo)
            cod_usuario = row.get('cod_usuario')
            if cod_usuario and int(cod_usuario) > 0:
                u_name = self.erp_repo.buscar_usuario_por_id(cod_usuario)
                comentarios_fmt.insert(0, {
                    "data": dt_fmt,
                    "hora": format_erp_time(row['hora_grav']),
                    "usuario": u_name,
                    "texto": txt_content,
                    "destacar": ("AUTORIZAÇÃO" in txt_upper and "APROVADA" in txt_upper) or ("SOLICITAÇÃO" in txt_upper and "APROVADA" in txt_upper)
                })

        # Finalização T.I (Status AV ou BA)
        if erp_data['cod_status_doc'] in ['AV', 'BA']:
            if fluxo["finalizacao"]["status"] == "pending":
                data_fin = comentarios_fmt[0]['data'] if comentarios_fmt else erp_data['data_cad_fmt']
                dt_fin = erp_to_datetime(erp_data.get('data_baixa'), erp_data.get('hora_baixa')) or dt_abertura
                fluxo["finalizacao"] = {"status": "completed", "data": data_fin, "dt": dt_fin}

        # Encerramento (Status BA)
        if erp_data['cod_status_doc'] == 'BA':
            data_baixa = format_erp_date(erp_data.get('data_baixa')) or erp_data['data_cad_fmt']
            dt_baixa = erp_to_datetime(erp_data.get('data_baixa'), erp_data.get('hora_baixa')) or dt_abertura
            fluxo["encerramento"] = {"status": "completed", "data": data_baixa, "dt": dt_baixa}

        # Calcular durações entre etapas
        keys = ["abertura", "primeiro_atendimento", "autorizacao_gerencia", "aprovado_andamento", "finalizacao", "encerramento"]
        for i in range(len(keys)):
            k1 = keys[i]
            if fluxo[k1]["status"] == "completed":
                for j in range(i + 1, len(keys)):
                    k2 = keys[j]
                    if fluxo[k2]["status"] == "completed":
                        dt1, dt2 = fluxo[k1]["dt"], fluxo[k2]["dt"]
                        if dt1 and dt2 and dt2 >= dt1:
                            fluxo[k1]["duracao_proxima"] = format_duration(dt2 - dt1)
                            for mid in range(i + 1, j):
                                fluxo[keys[mid]]["status"] = "skipped"
                        break
            elif fluxo[k1]["status"] == "pending":
                fluxo[k1]["duracao_proxima"] = ""

        # Limpar dt para JSON
        for k in fluxo:
            if "dt" in fluxo[k]: del fluxo[k]["dt"]

        erp_data['foi_aprovado'] = foi_aprovado
        erp_data['comentarios_erp'] = comentarios_fmt
        erp_data['fluxo_etapas'] = fluxo
        return erp_data

    def buscar_pendentes(self):
        """Busca chamados que ainda não tiveram interação técnica."""
        results = self.erp_repo.buscar_chamados_pendentes_base()
        ticket_ids = [int(r['cod_solicitacao']) for r in results]
        tickets_with_notes = self.local_repo.get_ticket_ids_with_notes(ticket_ids) if ticket_ids else set()
        
        for d in results:
            # Formatar hora e data
            h_val = float(d['hora_cad']) if d['hora_cad'] else 0
            hh = int(h_val)
            mm = int((h_val - hh) * 100)
            ss = int(((h_val - hh) * 100 - mm) * 100)
            d['hora_cad_fmt'] = f"{hh:02d}:{mm:02d}:{ss:02d}"
            
            dt_str = str(d['data_cad'])
            d['data_cad_iso'] = f"{dt_str[0:4]}-{dt_str[4:6]}-{dt_str[6:8]}"
            d['has_local_note'] = int(d['cod_solicitacao']) in tickets_with_notes
            d['tipo'] = classify_ticket(d['titulo_solicitacao'])
            
        return results
