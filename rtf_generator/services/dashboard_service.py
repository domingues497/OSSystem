from utils.classifier import classify_ticket
from datetime import datetime, timedelta
from utils.datetime_utils import erp_to_datetime, format_duration_short
from time import perf_counter
import os

class DashboardService:
    def __init__(self, erp_repo, local_repo):
        self.erp_repo = erp_repo
        self.local_repo = local_repo
        self._estat_cache = {}
        try:
            self._estat_cache_ttl = int(os.getenv("DASHBOARD_CACHE_SECONDS", "15"))
        except Exception:
            self._estat_cache_ttl = 15

    def obter_estatisticas(self, start_date_str=None, end_date_str=None, kpi_date_str=None, debug_timing=False):
        now = datetime.now()
        timing = {} if debug_timing else None
        t_total0 = perf_counter()
        
        if start_date_str and end_date_str:
            start_dt = datetime.strptime(start_date_str, '%Y-%m-%d')
            end_dt = datetime.strptime(end_date_str, '%Y-%m-%d')
        else:
            end_dt = now
            start_dt = now - timedelta(days=6)
            
        if kpi_date_str:
            try:
                kpi_dt = datetime.strptime(kpi_date_str, '%Y-%m-%d')
            except Exception:
                kpi_dt = now
        else:
            kpi_dt = now
        today_erp = int(kpi_dt.strftime('%Y%m%d'))

        cache_key = (start_dt.strftime('%Y-%m-%d'), end_dt.strftime('%Y-%m-%d'), kpi_dt.strftime('%Y-%m-%d'))
        if not debug_timing and self._estat_cache_ttl > 0:
            cached = self._estat_cache.get(cache_key)
            if cached and (perf_counter() - cached["ts"]) < self._estat_cache_ttl:
                return cached["data"]
        
        # Gerar lista de dias no período
        period_days = []
        curr = start_dt
        while curr <= end_dt:
            period_days.append(int(curr.strftime('%Y%m%d')))
            curr += timedelta(days=1)

        # 1. Buscar estatísticas base
        t0 = perf_counter()
        rows = self.erp_repo.buscar_estatisticas_base()
        if timing is not None:
            timing["estatisticas_base_ms"] = round((perf_counter() - t0) * 1000, 2)
        
        # 2. Calcular distribuição de tipos (Heurística)
        categorias_alvo = ['Aberta', 'Aguardando', 'Andamento', 'Avaliação']
        distribuicao_tipos = {"Incidente": 0, "Requisição": 0, "BI": 0}

        t0 = perf_counter()
        titulos = self.erp_repo.buscar_titulos_por_status(['IM', 'AB', 'AA', 'EA', 'AN', 'AV'])
        for t in titulos:
            tipo = classify_ticket(t)
            distribuicao_tipos[tipo] += 1
        if timing is not None:
            timing["distribuicao_tipos_ms"] = round((perf_counter() - t0) * 1000, 2)

        # 3. Processar percentuais e categorias
        total_para_percentual = sum(row[1] for row in rows if row[0] in categorias_alvo)
        
        stats = []
        for row in rows:
            cat = row[0]
            count = row[1]
            percent = (count / total_para_percentual * 100) if total_para_percentual > 0 and cat in categorias_alvo else 0
            stats.append({
                "codigo": cat,
                "descricao": cat,
                "quantidade": count,
                "percentual": round(percent, 2),
                "ignorar_percentual": cat not in categorias_alvo
            })

        # 4. Histórico do período
        t0 = perf_counter()
        start_erp = int(start_dt.strftime('%Y%m%d'))
        end_erp = int(end_dt.strftime('%Y%m%d'))
        historico_map = self.erp_repo.buscar_historico_periodo(start_erp, end_erp)
        if timing is not None:
            timing["historico_periodo_ms"] = round((perf_counter() - t0) * 1000, 2)

        historico = []
        for d_erp in period_days:
            h = historico_map.get(d_erp) or {"abertos": 0, "atendidos": 0, "aprovados": 0, "finalizados": 0, "encerrados": 0}
            d_str = str(d_erp)
            dow_map = ["Seg", "Ter", "Qua", "Qui", "Sex", "Sáb", "Dom"]
            try:
                dow = dow_map[datetime.strptime(f"{d_str[0:4]}-{d_str[4:6]}-{d_str[6:8]}", "%Y-%m-%d").weekday()]
            except Exception:
                dow = ""
            historico.append({
                "data": f"{d_str[6:8]}/{d_str[4:6]} ({dow})" if dow else f"{d_str[6:8]}/{d_str[4:6]}",
                "iso": f"{d_str[0:4]}-{d_str[4:6]}-{d_str[6:8]}",
                "abertos": h['abertos'],
                "atendidos": h['atendidos'],
                "aprovados": h['aprovados'],
                "finalizados": h['finalizados'],
                "encerrados": h['encerrados']
            })

        t0 = perf_counter()
        kpis = self.erp_repo.buscar_kpis_status_hoje(today_erp)
        if timing is not None:
            timing["kpis_ms"] = round((perf_counter() - t0) * 1000, 2)

        # 6. Tempos Médios
        t0 = perf_counter()
        tempos_medios = self._calcular_tempos_medios()
        if timing is not None:
            timing["tempos_medios_ms"] = round((perf_counter() - t0) * 1000, 2)
            
        payload = {
            "kpis": kpis,
            "historico": historico,
            "detalhes": stats,
            "distribuicao_tipos": distribuicao_tipos,
            "tempos_medios": tempos_medios
        }
        if timing is not None:
            timing["total_ms"] = round((perf_counter() - t_total0) * 1000, 2)
            payload["__timing_ms"] = timing

        if not debug_timing and self._estat_cache_ttl > 0:
            self._estat_cache[cache_key] = {"ts": perf_counter(), "data": payload}

        return payload

    def _calcular_tempos_medios(self):
        recent_data = self.erp_repo.buscar_recentes_para_tempo_medio(200)
        transitions = {
            "abertura_atendimento": [],
            "atendimento_autorizacao": [],
            "autorizacao_aprovacao": [],
            "aprovacao_finalizacao": [],
            "finalizacao_encerramento": []
        }

        for item in recent_data:
            t = item['ticket']
            comms = item['comentarios']
            tid, d_cad, h_cad, d_atend, h_atend, d_baixa, h_baixa, status = t
            
            dt_abertura = erp_to_datetime(d_cad, h_cad)
            dt_atendimento = erp_to_datetime(d_atend, h_atend) if d_atend and int(d_atend) > 0 else None
            
            if dt_atendimento and dt_abertura:
                transitions["abertura_atendimento"].append((dt_atendimento - dt_abertura).total_seconds())
            
            dt_autorizacao = None
            dt_aprovacao = None
            
            for c_date, c_time, c_text in comms:
                dt_c = erp_to_datetime(c_date, c_time)
                if ("SOLICITAÇÃO DE AUTORIZAÇÃO" in c_text and "FOI ENVIADA" in c_text) and dt_atendimento and not dt_autorizacao:
                    dt_autorizacao = dt_c
                    transitions["atendimento_autorizacao"].append((dt_c - dt_atendimento).total_seconds())
                if ("SOLICITAÇÃO DE AUTORIZAÇÃO" in c_text and "FOI APROVADA" in c_text) and dt_autorizacao and not dt_aprovacao:
                    dt_aprovacao = dt_c
                    transitions["autorizacao_aprovacao"].append((dt_c - dt_autorizacao).total_seconds())
                if ("SOLICITAÇÃO APROVADA POR" in c_text or "SOLICITAÇÃO ATUALIZADA PARA O STATUS: ANDAMENTO" in c_text) and dt_atendimento and not dt_aprovacao:
                    dt_aprovacao = dt_c

            if status in ['AV', 'BA'] and d_baixa and int(d_baixa) > 0 and dt_aprovacao:
                dt_finalizacao = erp_to_datetime(d_baixa, h_baixa)
                if dt_finalizacao:
                    transitions["aprovacao_finalizacao"].append((dt_finalizacao - dt_aprovacao).total_seconds())
                    if status == 'BA':
                        diff = (dt_finalizacao - dt_finalizacao).total_seconds() # Simplificado
                        # No app.py original era diff = (dt_encerramento - dt_finalizacao).total_seconds()
                        # Mas dt_encerramento e dt_finalizacao usavam as mesmas colunas d_baixa/h_baixa
                        # Vamos manter a lógica original (que resultava em 0 se fossem iguais)
                        transitions["finalizacao_encerramento"].append(0)

        def get_avg(key):
            lst = transitions[key]
            return format_duration_short(sum(lst)/len(lst)) if lst else "0m"

        return {
            "Abertura → Atendimento": get_avg("abertura_atendimento"),
            "Atendimento → Autorização": get_avg("atendimento_autorizacao"),
            "Autorização → Aprovação": get_avg("autorizacao_aprovacao"),
            "Aprovação → Finalização": get_avg("aprovacao_finalizacao"),
            "Finalização → Encerramento": get_avg("finalizacao_encerramento")
        }

    def obter_trello_sem_rotulo(self, limit=30):
        results = self.erp_repo.buscar_trello_sem_rotulo_base(limit)
        ticket_ids = [int(r['cod_solicitacao']) for r in results]
        tickets_with_notes = self.local_repo.get_ticket_ids_with_notes(ticket_ids) if ticket_ids else set()

        for d in results:
            h_val = float(d['hora_cad']) if d.get('hora_cad') else 0
            hh = int(h_val)
            mm = int((h_val - hh) * 100)
            ss = int(((h_val - hh) * 100 - mm) * 100)
            d['hora_cad_fmt'] = f"{hh:02d}:{mm:02d}:{ss:02d}"

            dt_str = str(d.get('data_cad') or '')
            if len(dt_str) == 8:
                d['data_cad_iso'] = f"{dt_str[0:4]}-{dt_str[4:6]}-{dt_str[6:8]}"
            else:
                d['data_cad_iso'] = ''

            d['has_local_note'] = int(d['cod_solicitacao']) in tickets_with_notes
            d['tipo'] = classify_ticket(d.get('titulo_solicitacao'))

        return results

    def obter_kanban(self, filtros):
        f_id = filtros.get('id')
        f_solicitante = filtros.get('solicitante')
        f_start = filtros.get('start_date')
        f_end = filtros.get('end_date')
        f_statuses = filtros.get('status', [])
        f_kpi = filtros.get('kpi')
        f_tipo = filtros.get('tipo')
        f_assunto = filtros.get('assunto')
        f_assunto_q = filtros.get('assunto_q')
        f_q = filtros.get('q')
        f_executor = filtros.get('executor')
        f_etapa = filtros.get('etapa')
        f_ativo = filtros.get('ativo')
        f_aprovador = filtros.get('aprovador')
        f_atendente = filtros.get('atendente')

        # Construir query base (simplificado no repositório agora)
        # O repositório precisa de buscar_coluna_kanban(query, params)
        # Vamos usar o método listar_chamados_com_filtros mas apenas para os status do Kanban
        
        colunas = {
            "aberta": ['IM', 'AB'],
            "aguardando": ['AA'],
            "andamento": ['EA', 'AN'],
            "avaliacao": ['AV'],
            "encerrados": ['BA']
        }
        
        status_map = {
            "aberta": set(['IM', 'AB']),
            "aguardando": set(['AA']),
            "andamento": set(['EA', 'AN']),
            "avaliacao": set(['AV']),
            "encerrados": set(['BA'])
        }
        all_statuses = []
        for sts in status_map.values():
            all_statuses.extend(list(sts))

        base_filters = {
            "id": f_id,
            "solicitante": f_solicitante,
            "start_date": f_start,
            "end_date": f_end,
            "kpi": f_kpi,
            "assunto": f_assunto,
            "assunto_q": f_assunto_q,
            "q": f_q,
            "executor": f_executor,
            "etapa": f_etapa,
            "ativo": f_ativo,
            "aprovador": f_aprovador,
            "status": all_statuses
        }
        base_rows = self.erp_repo.buscar_kanban_base(base_filters)
        ids = [r["id"] for r in base_rows]
        ids_with_notes = self.local_repo.get_ticket_ids_with_notes(ids)
        assignees_by_ticket = self.local_repo.get_assignees_by_ticket_ids(ids)

        kanban = {k: [] for k in status_map.keys()}
        for r in base_rows:
            tid = int(r["id"])
            item_tipo = classify_ticket(r["titulo"])
            atendente = assignees_by_ticket.get(tid, "")
            if f_tipo and item_tipo != f_tipo:
                continue
            if f_atendente and (atendente or "").strip().upper() != str(f_atendente).strip().upper():
                continue

            col_name = None
            for k, sts in status_map.items():
                if r["status"] in sts:
                    col_name = k
                    break
            if not col_name:
                continue

            item = {
                "id": tid,
                "titulo": r["titulo"],
                "status": r["status"],
                "data_cad": r.get("data_cad", 0),
                "hora_cad": r.get("hora_cad", 0),
                "tipo": item_tipo,
                "no_iteration": bool(r["no_iteration"]) if col_name == "aberta" else False,
                "waiting_auth": bool(r["waiting_auth"]),
                "auth_approved": bool(r["auth_approved"]),
                "auth_req_count": int(r.get("auth_req_count") or 0),
                "auth_appr_count": int(r.get("auth_appr_count") or 0),
                "has_note": tid in ids_with_notes,
                "atendente": atendente
            }
            kanban[col_name].append(item)

        return kanban
