from utils.datetime_utils import format_erp_date, format_erp_time, erp_to_datetime, format_duration
from utils.classifier import classify_ticket

TRELLO_ROTULO_SETORES = {
    1: "Café",
    2: "Comercial",
    3: "Compras",
    4: "Contabilidade",
    5: "dat",
    6: "Financeiro",
    7: "fiscal",
    8: "loja",
    9: "manutenção",
    10: "RH",
    11: "ração",
    12: "t.i",
    14: "ubs",
    16: "Auditoria",
    17: "Balança",
    18: "Custos",
    22: "Pecuária",
    26: "Posto",
    36: "Cadastro",
}

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
        atendente_atual = self.local_repo.get_assignee_by_ticket(cod_solicitacao)
        
        # 2. Buscar dados base do ERP
        erp_data = self.erp_repo.buscar_chamado_por_id(cod_solicitacao)
        if not erp_data:
            return None

        trello_card_id = erp_data.get('trello_card_id')
        trello_label_id = erp_data.get('trello_label_id')
        try:
            trello_label_id = int(trello_label_id) if trello_label_id is not None and str(trello_label_id).strip() != '' else None
        except Exception:
            trello_label_id = None
        trello_setor = TRELLO_ROTULO_SETORES.get(trello_label_id) if trello_label_id is not None else None
        erp_data['trello'] = {
            "integrado": bool(trello_card_id),
            "card_id": trello_card_id or "",
            "rotulo_id": trello_label_id,
            "setor": trello_setor or "",
            "sem_rotulo": bool(trello_card_id) and trello_label_id is None,
        }

        try:
            auth_req = int(erp_data.get('auth_req_count') or 0)
        except Exception:
            auth_req = 0
        try:
            auth_appr = int(erp_data.get('auth_appr_count') or 0)
        except Exception:
            auth_appr = 0
        erp_data['aprovacao_gerencia'] = {
            "solicitado": auth_req,
            "aprovado": auth_appr,
        }

        # 3. Buscar comentários
        comentarios = self.erp_repo.buscar_comentarios_chamado(cod_solicitacao)
        
        # 4. Formatação e Enriquecimento
        erp_data['data_cad_fmt'] = format_erp_date(erp_data['data_cad'])
        erp_data['anotacoes_locais'] = local_notes
        erp_data['atendente_atual'] = atendente_atual
        
        # 5. Analisar Fluxo (Lógica extraída do app.py)
        dt_abertura = erp_to_datetime(erp_data['data_cad'], erp_data.get('hora_cad'))
        hora_abertura = format_erp_time(erp_data.get('hora_cad'))
        usuario_abertura = erp_data.get('criador') or erp_data.get('solicitante') or ''
        fluxo = {
            "abertura": {"status": "completed", "data": erp_data['data_cad_fmt'], "hora": hora_abertura, "usuario": usuario_abertura, "dt": dt_abertura},
            "primeiro_atendimento": {"status": "pending", "data": "", "hora": "", "usuario": "", "dt": None},
            "autorizacao_gerencia": {"status": "pending", "data": "", "hora": "", "usuario": "", "dt": None},
            "aprovado_andamento": {"status": "pending", "data": "", "hora": "", "usuario": "", "dt": None},
            "finalizacao": {"status": "pending", "data": "", "hora": "", "usuario": "", "dt": None},
            "encerramento": {"status": "pending", "data": "", "hora": "", "usuario": "", "dt": None}
        }

        # Primeiro Atendimento oficial
        if erp_data.get('data_inic_atend') and int(erp_data['data_inic_atend']) > 0:
            dt_inic = erp_to_datetime(erp_data['data_inic_atend'], erp_data.get('hora_inic_atend'))
            fluxo["primeiro_atendimento"] = {"status": "completed", "data": format_erp_date(erp_data['data_inic_atend']), "hora": format_erp_time(erp_data.get('hora_inic_atend')), "usuario": "", "dt": dt_inic}

        foi_aprovado = False
        comentarios_fmt = []
        user_cache = {}
        
        def _norm(s):
            return " ".join((s or "").replace("\r", " ").replace("\n", " ").split()).strip()

        def _extract_after(text, marker):
            t = _norm(text)
            idx = t.lower().find(marker.lower())
            if idx < 0:
                return ""
            return t[idx + len(marker):].strip()

        def _cut_before_any(s, needles):
            low = s.lower()
            best = None
            for n in needles:
                i = low.find(n.lower())
                if i >= 0:
                    best = i if best is None else min(best, i)
            out = s[:best].strip() if best is not None else s.strip()
            return out.rstrip(" .,-")

        def _extract_actor_from_text(text):
            if not text:
                return ""
            t = _norm(text)
            low = t.lower()

            if "solicitação aprovada por" in low or "solicitacao aprovada por" in low:
                tail = _extract_after(t, "Solicitação aprovada por")
                if not tail:
                    tail = _extract_after(t, "Solicitacao aprovada por")
                return _cut_before_any(tail, ["Solicitação atualizada", "Solicitacao atualizada", "Aguardando", "Mensagem do"])

            if "solicitação finalizada por" in low or "solicitacao finalizada por" in low:
                tail = _extract_after(t, "Solicitação finalizada por")
                if not tail:
                    tail = _extract_after(t, "Solicitacao finalizada por")
                return _cut_before_any(tail, ["Aguardando", "Mensagem do"])

            if "solicitação encerrada por" in low or "solicitacao encerrada por" in low:
                tail = _extract_after(t, "Solicitação encerrada por")
                if not tail:
                    tail = _extract_after(t, "Solicitacao encerrada por")
                return _cut_before_any(tail, ["Mensagem do"])

            if "aprovado por:" in low or "aprovada por:" in low:
                tail = _extract_after(t, "Aprovado por:")
                if not tail:
                    tail = _extract_after(t, "Aprovada por:")
                return _cut_before_any(tail, ["Data", "Data/hora"])

            return ""
        
        # Ordenar comentários para análise de fluxo (ASC para cronologia)
        comms_asc = sorted(comentarios, key=lambda r: (r['data_grav'], r['hora_grav']))
        
        for row in comms_asc:
            # Identificar colunas de texto de forma dinâmica (como no repositório)
            txt_content = str(row.get('descr_acompanhante') or row.get('descr_acomp') or row.get('texto') or row.get('obs') or "")
            txt_upper = txt_content.upper()
            dt_fmt = format_erp_date(row['data_grav'])
            dt_obj = erp_to_datetime(row['data_grav'], row['hora_grav'])
            hora_evt = format_erp_time(row.get('hora_grav'))
            cod_usuario = row.get('cod_usuario')
            u_name = ""
            if cod_usuario and int(cod_usuario) > 0:
                if int(cod_usuario) in user_cache:
                    u_name = user_cache[int(cod_usuario)]
                else:
                    u_name = self.erp_repo.buscar_usuario_por_id(cod_usuario)
                    user_cache[int(cod_usuario)] = u_name
            
            is_system_auth = "SOLICITAÇÃO DE AUTORIZAÇÃO" in txt_upper
            is_system_status_change = "SOLICITAÇÃO ATUALIZADA PARA O STATUS" in txt_upper
            is_system_msg = is_system_auth or is_system_status_change

            # Etapa 2: Primeiro Atendimento via comentário (fallback)
            if fluxo["primeiro_atendimento"]["status"] == "pending" and not is_system_msg:
                fluxo["primeiro_atendimento"] = {"status": "completed", "data": dt_fmt, "hora": hora_evt, "usuario": u_name, "dt": dt_obj}
            elif fluxo["primeiro_atendimento"]["status"] == "completed" and not is_system_msg and not fluxo["primeiro_atendimento"].get("usuario"):
                fluxo["primeiro_atendimento"]["usuario"] = u_name
            
            # Etapa 3: Autorização da Gerência
            if ("SOLICITAÇÃO DE AUTORIZAÇÃO" in txt_upper and "FOI APROVADA" in txt_upper) or ("AUTORIZAÇÃO" in txt_upper and "APROVADA" in txt_upper):
                if fluxo["autorizacao_gerencia"]["status"] == "pending":
                    actor = _extract_actor_from_text(txt_content)
                    fluxo["autorizacao_gerencia"] = {"status": "completed", "data": dt_fmt, "hora": hora_evt, "usuario": actor, "dt": dt_obj}
            
            # Etapa 4: Aprovado e em Andamento
            if ("SOLICITAÇÃO APROVADA POR" in txt_upper) or ("SOLICITAÇÃO ATUALIZADA PARA O STATUS: ANDAMENTO" in txt_upper) or ("SOLICITAÇÃO ATUALIZADA PARA O STATUS: EA" in txt_upper):
                if fluxo["aprovado_andamento"]["status"] == "pending":
                    foi_aprovado = True
                    actor = _extract_actor_from_text(txt_content)
                    fluxo["aprovado_andamento"] = {"status": "completed", "data": dt_fmt, "hora": hora_evt, "usuario": actor, "dt": dt_obj}
            
            # Etapa 5: Finalização via comentário (fallback)
            if (("SOLICITAÇÃO FINALIZADA" in txt_upper) or ("SOLICITACAO FINALIZADA" in txt_upper) or (("SOLICIT" in txt_upper) and ("FINALIZAD" in txt_upper) and ("ENCERRAD" not in txt_upper))):
                if fluxo["finalizacao"]["status"] == "pending":
                    actor = _extract_actor_from_text(txt_content)
                    fluxo["finalizacao"] = {"status": "completed", "data": dt_fmt, "hora": hora_evt, "usuario": actor, "dt": dt_obj}
            
            # Etapa 6: Encerramento via comentário (prioridade sobre DATA_BAIXA quando diverge)
            if "ENCERRAD" in txt_upper and "SOLICIT" in txt_upper:
                if fluxo["encerramento"]["status"] == "pending":
                    actor = _extract_actor_from_text(txt_content)
                    fluxo["encerramento"] = {"status": "completed", "data": dt_fmt, "hora": hora_evt, "usuario": actor, "dt": dt_obj}

            # Formatar comentário para exibição (reverso no final ou inserção no topo)
            if cod_usuario and int(cod_usuario) > 0:
                comentarios_fmt.insert(0, {
                    "data": dt_fmt,
                    "hora": hora_evt,
                    "usuario": u_name,
                    "texto": txt_content,
                    "destacar": ("AUTORIZAÇÃO" in txt_upper and "APROVADA" in txt_upper) or ("SOLICITAÇÃO" in txt_upper and "APROVADA" in txt_upper)
                })

        if erp_data['cod_status_doc'] in ['AV', 'BA'] and fluxo["finalizacao"]["status"] == "pending":
            for row in reversed(comms_asc):
                txt_content = str(row.get('descr_acompanhante') or row.get('descr_acomp') or row.get('texto') or row.get('obs') or "")
                txt_upper = txt_content.upper()
                if (("SOLICITAÇÃO FINALIZADA" in txt_upper) or ("SOLICITACAO FINALIZADA" in txt_upper) or (("SOLICIT" in txt_upper) and ("FINALIZAD" in txt_upper) and ("ENCERRAD" not in txt_upper))):
                    dt_obj = erp_to_datetime(row['data_grav'], row['hora_grav'])
                    if not dt_obj:
                        continue
                    hora_evt = format_erp_time(row.get('hora_grav'))
                    actor = _extract_actor_from_text(txt_content)
                    fluxo["finalizacao"] = {"status": "completed", "data": format_erp_date(row['data_grav']), "hora": hora_evt, "usuario": actor, "dt": dt_obj}
                    break

        if erp_data['cod_status_doc'] == 'BA' and fluxo["encerramento"]["status"] == "pending":
            for row in reversed(comms_asc):
                txt_content = str(row.get('descr_acompanhante') or row.get('descr_acomp') or row.get('texto') or row.get('obs') or "")
                txt_upper = txt_content.upper()
                if ("ENCERRAD" in txt_upper) and ("SOLICIT" in txt_upper):
                    dt_obj = erp_to_datetime(row['data_grav'], row['hora_grav'])
                    if not dt_obj:
                        continue
                    hora_evt = format_erp_time(row.get('hora_grav'))
                    actor = _extract_actor_from_text(txt_content)
                    fluxo["encerramento"] = {"status": "completed", "data": format_erp_date(row['data_grav']), "hora": hora_evt, "usuario": actor, "dt": dt_obj}
                    break

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
