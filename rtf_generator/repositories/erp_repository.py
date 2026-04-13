from database.erp_connection import get_erp_connection
from utils.datetime_utils import format_erp_date, format_erp_time, erp_to_datetime
from utils.classifier import classify_ticket
from utils.text_utils import extract_approver_from_text
import os

class ERPRepository:
    def __init__(self):
        self.status_map = {
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

    def _get_text_col(self, cur):
        cur.execute("SELECT * FROM BANCO01.DM1745 LIMIT 1")
        all_cols = [col[0].lower() for col in cur.description]
        return next((c for c in all_cols if 'descr' in c or 'texto' in c or 'obs' in c), "DESCR_ACOMP")

    def buscar_assuntos(self, tipo=None):
        conn = get_erp_connection()
        cur = conn.cursor()
        
        # Se houver filtro de tipo, precisamos buscar os assuntos que pertencem a esse tipo
        # Como o tipo é classificado em Python, vamos buscar os chamados abertos e classificá-los
        if tipo:
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
                if classify_ticket(titulo) == tipo:
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
        return assuntos

    def buscar_ativos(self, tipo=None, assunto=None):
        conn = get_erp_connection()
        cur = conn.cursor()
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
        if assunto:
            query += " AND DM1744.COD_ASSUNTO = %s"
            params.append(assunto)
            
        cur.execute(query, params)
        rows = cur.fetchall()
        
        grouped = {}
        for row in rows:
            cod, descr, ident, titulo, cod_assunto = row
            if tipo and classify_ticket(titulo) != tipo:
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
        return ativos

    def buscar_aprovadores(self):
        conn = get_erp_connection()
        cur = conn.cursor()
        text_col = self._get_text_col(cur)
        
        query_operadores = """
            SELECT DISTINCT DS0300.NOME_USUARIO 
            FROM public.DS0300 
            JOIN BANCO01.DC1964 ON (DC1964.COD_USUARIO = DS0300.COD_USUARIO)
            WHERE DC1964.COD_DEPAR = 16
            ORDER BY DS0300.NOME_USUARIO
        """
        cur.execute(query_operadores)
        tecnicos_ti = {row[0].strip() for row in cur.fetchall()}
        
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
            if u_name and ("TI" in u_name.upper() or "T.I" in u_name.upper()):
                aprovadores_finais.add(u_name.strip())
            
            nome_ext = extract_approver_from_text(txt_upper, tecnicos_ti)
            if nome_ext:
                aprovadores_finais.add(nome_ext)
                
        cur.close()
        conn.close()
        return sorted(list(aprovadores_finais))

    def buscar_status(self):
        conn = get_erp_connection()
        cur = conn.cursor()
        cur.execute("SELECT DISTINCT COD_STATUS_DOC FROM BANCO01.DM1744 WHERE COD_STATUS_DOC IS NOT NULL ORDER BY COD_STATUS_DOC")
        statuses = [{"code": r[0], "name": self.status_map.get(r[0], r[0])} for r in cur.fetchall()]
        cur.close()
        conn.close()
        return statuses

    def buscar_chamado_por_id(self, cod_solicitacao):
        conn = get_erp_connection()
        cur = conn.cursor()
        cur.execute("""
            SELECT 
                DM1744.PRIORIDADE, DM1744.COD_STATUS_DOC, DM1744.DATA_CAD, DM1744.HORA_CAD,
                DM1744.DATA_INIC_ATEND, DM1744.HORA_INIC_ATEND, DM1744.DATA_BAIXA, DM1744.HORA_BAIXA,
                DS0300.NOME_USUARIO as SOLICITANTE, DM1744.COD_SOLICITACAO, DM1744.TITULO_SOLICITACAO,
                DM1744.DESCR_SOLICITACAO, DC1629.DESCR_ATIVO, DC1629.IDENT_ATIVO as TAG
            FROM BANCO01.DM1744 
            LEFT JOIN public.DS0300 ON (DS0300.COD_USUARIO = DM1744.COD_USUARIO)
            LEFT JOIN BANCO01.DC1629 ON (DC1629.COD_ATIVO = DM1744.COD_ATIVO)
            WHERE DM1744.COD_SOLICITACAO = %s
        """, (cod_solicitacao,))
        row = cur.fetchone()
        if not row: return None
        columns = [col[0].lower() for col in cur.description]
        data = dict(zip(columns, row))
        cur.close()
        conn.close()
        return data

    def buscar_comentarios_chamado(self, cod_solicitacao):
        conn = get_erp_connection()
        cur = conn.cursor()
        cur.execute("SELECT * FROM BANCO01.DM1745 WHERE COD_SOLICITACAO = %s ORDER BY DATA_GRAV DESC, HORA_GRAV DESC", (cod_solicitacao,))
        rows = cur.fetchall()
        columns = [col[0].lower() for col in cur.description]
        data = [dict(zip(columns, r)) for r in rows]
        cur.close()
        conn.close()
        return data

    def buscar_usuario_por_id(self, cod_usuario):
        conn = get_erp_connection()
        cur = conn.cursor()
        cur.execute("SELECT NOME_USUARIO FROM public.DS0300 WHERE COD_USUARIO = %s", (cod_usuario,))
        row = cur.fetchone()
        name = row[0] if row else "Desconhecido"
        cur.close()
        conn.close()
        return name

    def buscar_estatisticas_base(self):
        conn = get_erp_connection()
        cur = conn.cursor()
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
        cur.close()
        conn.close()
        return rows

    def buscar_historico_dia(self, d_erp):
        conn = get_erp_connection()
        cur = conn.cursor()
        text_col = self._get_text_col(cur)
        dashboard_user_cod = int(os.getenv("DASHBOARD_USER_COD", "1538"))

        cur.execute(f"""
            WITH chamados_escopo AS (
                SELECT DM1744.COD_SOLICITACAO
                FROM BANCO01.DM1744
                WHERE DM1744.NUM_BD IN (
                    SELECT B.NUM_BD
                    FROM BANCO01.DC1964 A
                    INNER JOIN BANCO01.DC1965 B ON (B.COD_DEPAR = A.COD_DEPAR)
                    WHERE A.COD_USUARIO = %s
                )
                AND DM1744.COD_ASSUNTO IN (
                    SELECT B.COD_ASSUNTO
                    FROM BANCO01.DC1964 A
                    INNER JOIN BANCO01.DC1966 B ON (B.COD_DEPAR = A.COD_DEPAR)
                    WHERE A.COD_USUARIO = %s
                )
            )
            SELECT
                (SELECT COUNT(*)
                 FROM BANCO01.DM1744
                 INNER JOIN chamados_escopo C ON (C.COD_SOLICITACAO = DM1744.COD_SOLICITACAO)
                 WHERE DM1744.DATA_CAD = %s
                ) AS abertos,
                (SELECT COUNT(*)
                 FROM BANCO01.DM1744
                 INNER JOIN chamados_escopo C ON (C.COD_SOLICITACAO = DM1744.COD_SOLICITACAO)
                 WHERE DM1744.DATA_INIC_ATEND = %s
                ) AS atendidos,
                (SELECT COUNT(DISTINCT H.COD_SOLICITACAO)
                 FROM BANCO01.DM1745 H
                 INNER JOIN chamados_escopo C ON (C.COD_SOLICITACAO = H.COD_SOLICITACAO)
                 WHERE H.DATA_GRAV = %s
                   AND UPPER(H.{text_col}) LIKE '%%AUTORIZA%%'
                   AND UPPER(H.{text_col}) LIKE '%%APROVAD%%'
                ) AS aprovados,
                (SELECT COUNT(DISTINCT H.COD_SOLICITACAO)
                 FROM BANCO01.DM1745 H
                 INNER JOIN chamados_escopo C ON (C.COD_SOLICITACAO = H.COD_SOLICITACAO)
                 WHERE H.DATA_GRAV = %s
                   AND UPPER(H.{text_col}) LIKE '%%SOLICIT%%'
                   AND UPPER(H.{text_col}) LIKE '%%FINALIZAD%%'
                   AND UPPER(H.{text_col}) NOT LIKE '%%ENCERRAD%%'
                ) AS finalizados,
                (SELECT COUNT(*)
                 FROM BANCO01.DM1744
                 INNER JOIN chamados_escopo C ON (C.COD_SOLICITACAO = DM1744.COD_SOLICITACAO)
                 WHERE DM1744.DATA_BAIXA = %s AND DM1744.COD_STATUS_DOC = 'BA'
                ) AS encerrados
        """, (dashboard_user_cod, dashboard_user_cod, d_erp, d_erp, d_erp, d_erp, d_erp))
        abertos, atendidos, aprovados, finalizados, encerrados = cur.fetchone() or (0, 0, 0, 0, 0)

        cur.close()
        conn.close()
        return {"abertos": int(abertos or 0), "atendidos": int(atendidos or 0), "aprovados": int(aprovados or 0), "finalizados": int(finalizados or 0), "encerrados": int(encerrados or 0)}

    def buscar_kpis_status_hoje(self, d_erp):
        conn = get_erp_connection()
        cur = conn.cursor()
        text_col = self._get_text_col(cur)
        dashboard_user_cod = int(os.getenv("DASHBOARD_USER_COD", "1538"))

        cur.execute(f"""
            WITH chamados_escopo AS (
                SELECT DM1744.COD_SOLICITACAO
                FROM BANCO01.DM1744
                WHERE DM1744.NUM_BD IN (
                    SELECT B.NUM_BD
                    FROM BANCO01.DC1964 A
                    INNER JOIN BANCO01.DC1965 B ON (B.COD_DEPAR = A.COD_DEPAR)
                    WHERE A.COD_USUARIO = %s
                )
                AND DM1744.COD_ASSUNTO IN (
                    SELECT B.COD_ASSUNTO
                    FROM BANCO01.DC1964 A
                    INNER JOIN BANCO01.DC1966 B ON (B.COD_DEPAR = A.COD_DEPAR)
                    WHERE A.COD_USUARIO = %s
                )
            ),
            chamados_nao_baixados AS (
                SELECT DM1744.COD_SOLICITACAO
                FROM BANCO01.DM1744
                INNER JOIN chamados_escopo C ON (C.COD_SOLICITACAO = DM1744.COD_SOLICITACAO)
                WHERE DM1744.COD_STATUS_DOC <> 'BA'
            ),
            today_msgs AS (
                SELECT
                    H.COD_SOLICITACAO,
                    H.{text_col} AS TXT_RAW,
                    UPPER(H.{text_col}) AS TXT_UPPER
                FROM BANCO01.DM1745 H
                INNER JOIN chamados_escopo C ON (C.COD_SOLICITACAO = H.COD_SOLICITACAO)
                WHERE H.DATA_GRAV = %s
            ),
            enviado_aprovacao_today AS (
                SELECT DISTINCT COD_SOLICITACAO
                FROM today_msgs
                WHERE TXT_UPPER LIKE '%%SOLICIT%%'
                  AND TXT_UPPER LIKE '%%AUTORIZA%%'
                  AND TXT_UPPER LIKE '%%GERENT%%'
            ),
            auth_approved_today AS (
                SELECT DISTINCT COD_SOLICITACAO
                FROM today_msgs
                WHERE TXT_UPPER LIKE '%%AUTORIZA%%'
                  AND TXT_UPPER LIKE '%%APROVAD%%'
            ),
            andamento_today AS (
                SELECT DISTINCT COD_SOLICITACAO
                FROM today_msgs
                WHERE TXT_UPPER LIKE '%%STATUS:%%ANDAMENTO%%'
            ),
            finalizados_today AS (
                SELECT DISTINCT COD_SOLICITACAO
                FROM today_msgs
                WHERE TXT_UPPER LIKE '%%SOLICIT%%'
                  AND TXT_UPPER LIKE '%%FINALIZAD%%'
                  AND TXT_UPPER NOT LIKE '%%ENCERRAD%%'
            )
            SELECT
                (SELECT COUNT(*)
                 FROM BANCO01.DM1744
                 INNER JOIN chamados_escopo C ON (C.COD_SOLICITACAO = DM1744.COD_SOLICITACAO)
                 WHERE DM1744.DATA_CAD = %s
                ) AS abertos_hoje,
                (SELECT COUNT(*) FROM (SELECT DISTINCT COD_SOLICITACAO FROM enviado_aprovacao_today) X) AS enviado_aprovacao_hoje,
                (SELECT COUNT(*) FROM (SELECT DISTINCT COD_SOLICITACAO FROM auth_approved_today) X) AS aprovados_hoje,
                (SELECT COUNT(*) FROM (SELECT DISTINCT COD_SOLICITACAO FROM andamento_today) X) AS andamento_hoje,
                (SELECT COUNT(*) FROM (SELECT DISTINCT COD_SOLICITACAO FROM finalizados_today) X) AS finalizados_hoje,
                (SELECT COUNT(*)
                 FROM BANCO01.DM1744
                 INNER JOIN chamados_escopo C ON (C.COD_SOLICITACAO = DM1744.COD_SOLICITACAO)
                 WHERE DM1744.DATA_BAIXA = %s AND DM1744.COD_STATUS_DOC = 'BA'
                ) AS baixados_hoje
        """, (dashboard_user_cod, dashboard_user_cod, d_erp, d_erp, d_erp))

        row = cur.fetchone() or (0, 0, 0, 0, 0, 0)
        cur.close()
        conn.close()
        return {
            "abertos_hoje": int(row[0] or 0),
            "enviado_aprovacao_hoje": int(row[1] or 0),
            "aprovados_hoje": int(row[2] or 0),
            "andamento_hoje": int(row[3] or 0),
            "finalizados_hoje": int(row[4] or 0),
            "baixados_hoje": int(row[5] or 0),
        }

    def buscar_recentes_para_tempo_medio(self, limit=200):
        conn = get_erp_connection()
        cur = conn.cursor()
        text_col = self._get_text_col(cur)
        cur.execute(f"""
            SELECT COD_SOLICITACAO, DATA_CAD, HORA_CAD, DATA_INIC_ATEND, HORA_INIC_ATEND, DATA_BAIXA, HORA_BAIXA, COD_STATUS_DOC
            FROM BANCO01.DM1744 
            WHERE DM1744.COD_ASSUNTO IN (SELECT COD_ASSUNTO FROM BANCO01.DC1966 WHERE COD_DEPAR = 16)
            ORDER BY DATA_CAD DESC, HORA_CAD DESC
            LIMIT %s
        """, (limit,))
        tickets = cur.fetchall()
        
        results = []
        for t in tickets:
            tid = t[0]
            cur.execute(f"SELECT DATA_GRAV, HORA_GRAV, UPPER({text_col}) FROM BANCO01.DM1745 WHERE COD_SOLICITACAO = %s ORDER BY DATA_GRAV ASC, HORA_GRAV ASC", (tid,))
            comms = cur.fetchall()
            results.append({"ticket": t, "comentarios": comms})
            
        cur.close()
        conn.close()
        return results

    def buscar_produtividade_por_tecnico(self, start_erp, end_erp):
        conn = get_erp_connection()
        cur = conn.cursor()
        text_col = self._get_text_col(cur)
        dashboard_user_cod = int(os.getenv("DASHBOARD_USER_COD", "1538"))
        cur.execute(f"""
            WITH chamados_escopo AS (
                SELECT DM1744.COD_SOLICITACAO
                FROM BANCO01.DM1744
                WHERE DM1744.NUM_BD IN (
                    SELECT B.NUM_BD
                    FROM BANCO01.DC1964 A
                    INNER JOIN BANCO01.DC1965 B ON (B.COD_DEPAR = A.COD_DEPAR)
                    WHERE A.COD_USUARIO = %s
                )
                AND DM1744.COD_ASSUNTO IN (
                    SELECT B.COD_ASSUNTO
                    FROM BANCO01.DC1964 A
                    INNER JOIN BANCO01.DC1966 B ON (B.COD_DEPAR = A.COD_DEPAR)
                    WHERE A.COD_USUARIO = %s
                )
            ),
            chamados_nao_baixados AS (
                SELECT DM1744.COD_SOLICITACAO
                FROM BANCO01.DM1744
                INNER JOIN chamados_escopo C ON (C.COD_SOLICITACAO = DM1744.COD_SOLICITACAO)
                WHERE DM1744.COD_STATUS_DOC <> 'BA'
            )
            SELECT
                T.TIPO,
                T.DATA_GRAV,
                T.COD_SOLICITACAO,
                T.TEXTO
            FROM (
                SELECT
                    'enviado' AS TIPO,
                    H.DATA_GRAV,
                    H.COD_SOLICITACAO,
                    H.{text_col} AS TEXTO
                FROM BANCO01.DM1745 H
                INNER JOIN chamados_nao_baixados C ON (C.COD_SOLICITACAO = H.COD_SOLICITACAO)
                WHERE H.DATA_GRAV BETWEEN %s AND %s
                  AND H.{text_col} LIKE '%%solicitou a autorização de um gerente para a execução do serviço%%'
                UNION ALL
                SELECT
                    'andamento' AS TIPO,
                    H.DATA_GRAV,
                    H.COD_SOLICITACAO,
                    H.{text_col} AS TEXTO
                FROM BANCO01.DM1745 H
                INNER JOIN chamados_escopo C ON (C.COD_SOLICITACAO = H.COD_SOLICITACAO)
                WHERE H.DATA_GRAV BETWEEN %s AND %s
                  AND H.{text_col} LIKE '%%Solicitação aprovada por%%Solicitação atualizada para o status: Andamento.%%'
                UNION ALL
                SELECT
                    'finalizado' AS TIPO,
                    H.DATA_GRAV,
                    H.COD_SOLICITACAO,
                    H.{text_col} AS TEXTO
                FROM BANCO01.DM1745 H
                INNER JOIN chamados_escopo C ON (C.COD_SOLICITACAO = H.COD_SOLICITACAO)
                WHERE H.DATA_GRAV BETWEEN %s AND %s
                  AND H.{text_col} LIKE '%%Solicitação finalizada por%%'
                UNION ALL
                SELECT
                    'encerrado' AS TIPO,
                    H.DATA_GRAV,
                    H.COD_SOLICITACAO,
                    H.{text_col} AS TEXTO
                FROM BANCO01.DM1745 H
                INNER JOIN chamados_escopo C ON (C.COD_SOLICITACAO = H.COD_SOLICITACAO)
                WHERE H.DATA_GRAV BETWEEN %s AND %s
                  AND H.{text_col} LIKE '%%Solicitação encerrada por%%'
            ) T
            ORDER BY T.DATA_GRAV ASC, T.TIPO ASC, T.COD_SOLICITACAO ASC
        """, (
            dashboard_user_cod,
            dashboard_user_cod,
            start_erp,
            end_erp,
            start_erp,
            end_erp,
            start_erp,
            end_erp,
            start_erp,
            end_erp,
        ))
        rows = cur.fetchall()
        results = [
            {
                "tipo": r[0],
                "data_grav": int(r[1]),
                "cod_solicitacao": int(r[2]),
                "texto": r[3] or "",
            }
            for r in rows
        ]
        cur.close()
        conn.close()
        return results

    def buscar_chamados_lista(self, query, params):
        conn = get_erp_connection()
        cur = conn.cursor()
        cur.execute(query, params)
        rows = cur.fetchall()
        columns = [col[0].lower() for col in cur.description]
        results = [dict(zip(columns, row)) for row in rows]
        cur.close()
        conn.close()
        return results

    def buscar_coluna_kanban(self, query, params):
        conn = get_erp_connection()
        cur = conn.cursor()
        cur.execute(query, params)
        rows = cur.fetchall()
        results = [dict(zip(['id', 'titulo', 'status'], row)) for row in rows]
        cur.close()
        conn.close()
        return results

    def verificar_iteracao_chamado(self, cod_solicitacao):
        conn = get_erp_connection()
        cur = conn.cursor()
        cur.execute("SELECT 1 FROM BANCO01.DM1745 WHERE COD_SOLICITACAO = %s AND COD_USUARIO > 0 LIMIT 1", (cod_solicitacao,))
        has_iter = cur.fetchone() is not None
        cur.close()
        conn.close()
        return has_iter

    def buscar_comentarios_kanban(self, cod_solicitacao):
        conn = get_erp_connection()
        cur = conn.cursor()
        text_col = self._get_text_col(cur)
        cur.execute(f"SELECT UPPER({text_col}) FROM BANCO01.DM1745 WHERE COD_SOLICITACAO = %s", (cod_solicitacao,))
        comms = [row[0] for row in cur.fetchall() if row[0]]
        cur.close()
        conn.close()
        return comms

    def buscar_chamados_pendentes_base(self):
        conn = get_erp_connection()
        cur = conn.cursor()
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
              AND DM1744.COD_ASSUNTO IN (SELECT COD_ASSUNTO FROM BANCO01.DC1966 WHERE COD_DEPAR = 16)
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
        results = [dict(zip(columns, row)) for row in rows]
        cur.close()
        conn.close()
        return results

    def buscar_chamados_abertos_recentes_base(self, start_erp, limit=80):
        conn = get_erp_connection()
        cur = conn.cursor()
        cur.execute("""
            SELECT
                DM1744.COD_SOLICITACAO,
                DM1744.TITULO_SOLICITACAO,
                DM1744.COD_STATUS_DOC,
                DM1744.DATA_CAD,
                DM1744.HORA_CAD,
                DS0300.NOME_USUARIO as SOLICITANTE
            FROM BANCO01.DM1744
            LEFT JOIN public.DS0300 ON (DS0300.COD_USUARIO = DM1744.COD_USUARIO)
            WHERE DM1744.COD_ASSUNTO IN (SELECT COD_ASSUNTO FROM BANCO01.DC1966 WHERE COD_DEPAR = 16)
              AND DM1744.DATA_CAD >= %s
            ORDER BY DM1744.DATA_CAD DESC, DM1744.HORA_CAD DESC, DM1744.COD_SOLICITACAO DESC
            LIMIT %s
        """, (start_erp, int(limit)))
        rows = cur.fetchall()
        columns = [col[0].lower() for col in cur.description]
        results = [dict(zip(columns, row)) for row in rows]
        cur.close()
        conn.close()
        return results

    def listar_chamados_com_filtros(self, filtros):
        """
        Método consolidado para listar chamados com todos os filtros do dashboard/lista.
        """
        status_filter = filtros.get('status', [])
        cod_solicitacao_filter = filtros.get('cod_solicitacao')
        solicitante_filter = filtros.get('solicitante')
        start_date = filtros.get('start_date')
        end_date = filtros.get('end_date')
        kpi_type = filtros.get('kpi') 
        assunto_filter = filtros.get('assunto') 
        ativo_filter = filtros.get('ativo') 
        aprovador_filter = filtros.get('aprovador')
        limit = filtros.get('limit')

        conn = get_erp_connection()
        cur = conn.cursor()
        text_col = self._get_text_col(cur)
        dashboard_user_cod = int(os.getenv("DASHBOARD_USER_COD", "1538"))

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
            WHERE DM1744.COD_ASSUNTO IN (SELECT COD_ASSUNTO FROM BANCO01.DC1966 WHERE COD_DEPAR = 16)
        """
        
        params = []

        if aprovador_filter:
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
                    WHERE DSRESP.COD_USUARIO = DM1744.COD_USUARIO_RESPONS
                      AND UPPER(DSRESP.NOME_USUARIO) LIKE %s
                )
            )"""
            params.extend([f"%{clean_approver}%", f"%APROVADA POR {clean_approver}%", f"%{clean_approver}%"])

        if kpi_type == 'abertos_hoje':
            if start_date:
                query += " AND DM1744.DATA_CAD >= %s"
                params.append(int(start_date.replace('-', '')))
            if end_date:
                query += " AND DM1744.DATA_CAD <= %s"
                params.append(int(end_date.replace('-', '')))
        elif kpi_type == 'enviado_aprovacao_hoje':

            query += """
                AND DM1744.NUM_BD IN (
                    SELECT B.NUM_BD
                    FROM BANCO01.DC1964 A
                    INNER JOIN BANCO01.DC1965 B ON (B.COD_DEPAR = A.COD_DEPAR)
                    WHERE A.COD_USUARIO = %s
                )
                AND DM1744.COD_ASSUNTO IN (
                    SELECT B.COD_ASSUNTO
                    FROM BANCO01.DC1964 A
                    INNER JOIN BANCO01.DC1966 B ON (B.COD_DEPAR = A.COD_DEPAR)
                    WHERE A.COD_USUARIO = %s
                )
            """
            params.extend([dashboard_user_cod, dashboard_user_cod])
            query += f""" AND EXISTS (
                SELECT 1
                FROM BANCO01.DM1745
                WHERE DM1745.COD_SOLICITACAO = DM1744.COD_SOLICITACAO
                  AND DM1745.{text_col} LIKE '%%solicitou a autorização de um gerente para a execução do serviço%%'
            """
            if start_date:
                query += " AND DM1745.DATA_GRAV >= %s"
                params.append(int(start_date.replace('-', '')))
            if end_date:
                query += " AND DM1745.DATA_GRAV <= %s"
                params.append(int(end_date.replace('-', '')))
            query += ")"
        elif kpi_type == 'aprovados_hoje':
            
            query += """
                AND DM1744.NUM_BD IN (
                    SELECT B.NUM_BD
                    FROM BANCO01.DC1964 A
                    INNER JOIN BANCO01.DC1965 B ON (B.COD_DEPAR = A.COD_DEPAR)
                    WHERE A.COD_USUARIO = %s
                )
                AND DM1744.COD_ASSUNTO IN (
                    SELECT B.COD_ASSUNTO
                    FROM BANCO01.DC1964 A
                    INNER JOIN BANCO01.DC1966 B ON (B.COD_DEPAR = A.COD_DEPAR)
                    WHERE A.COD_USUARIO = %s
                )
            """
            params.extend([dashboard_user_cod, dashboard_user_cod])
            query += f""" AND EXISTS (
                SELECT 1
                FROM BANCO01.DM1745
                WHERE COD_SOLICITACAO = DM1744.COD_SOLICITACAO
                  AND (
                        {text_col} LIKE '%%A solicitação de autorização para gerência de número%%foi aprovada.%%'
                  )
            """
            if start_date:
                query += " AND DATA_GRAV >= %s"
                params.append(int(start_date.replace('-', '')))
            if end_date:
                query += " AND DATA_GRAV <= %s"
                params.append(int(end_date.replace('-', '')))
            query += ")"
        elif kpi_type == 'andamento_hoje':
            query += """
                AND DM1744.NUM_BD IN (
                    SELECT B.NUM_BD
                    FROM BANCO01.DC1964 A
                    INNER JOIN BANCO01.DC1965 B ON (B.COD_DEPAR = A.COD_DEPAR)
                    WHERE A.COD_USUARIO = %s
                )
                AND DM1744.COD_ASSUNTO IN (
                    SELECT B.COD_ASSUNTO
                    FROM BANCO01.DC1964 A
                    INNER JOIN BANCO01.DC1966 B ON (B.COD_DEPAR = A.COD_DEPAR)
                    WHERE A.COD_USUARIO = %s
                )
            """
            params.extend([dashboard_user_cod, dashboard_user_cod])
            query += f""" AND EXISTS (
                SELECT 1
                FROM BANCO01.DM1745
                WHERE COD_SOLICITACAO = DM1744.COD_SOLICITACAO
                  AND (
                        {text_col} LIKE '%%Solicitação aprovada por%%Solicitação atualizada para o status: Andamento.%%'
                  )
            """
            if start_date:
                query += " AND DATA_GRAV >= %s"
                params.append(int(start_date.replace('-', '')))
            if end_date:
                query += " AND DATA_GRAV <= %s"
                params.append(int(end_date.replace('-', '')))
            query += ")"
        elif kpi_type == 'finalizados_hoje':
            query += """
                AND DM1744.NUM_BD IN (
                    SELECT B.NUM_BD
                    FROM BANCO01.DC1964 A
                    INNER JOIN BANCO01.DC1965 B ON (B.COD_DEPAR = A.COD_DEPAR)
                    WHERE A.COD_USUARIO = %s
                )
                AND DM1744.COD_ASSUNTO IN (
                    SELECT B.COD_ASSUNTO
                    FROM BANCO01.DC1964 A
                    INNER JOIN BANCO01.DC1966 B ON (B.COD_DEPAR = A.COD_DEPAR)
                    WHERE A.COD_USUARIO = %s
                )
            """
            params.extend([dashboard_user_cod, dashboard_user_cod])
            query += f""" AND EXISTS (
                SELECT 1
                FROM BANCO01.DM1745
                WHERE COD_SOLICITACAO = DM1744.COD_SOLICITACAO
                  AND (UPPER({text_col}) LIKE '%%SOLICITAÇÃO FINALIZADA POR%%')
            """
            if start_date:
                query += " AND DATA_GRAV >= %s"
                params.append(int(start_date.replace('-', '')))
            if end_date:
                query += " AND DATA_GRAV <= %s"
                params.append(int(end_date.replace('-', '')))
            query += ")"
        elif kpi_type == 'baixados_hoje':
            query += """
                AND DM1744.NUM_BD IN (
                    SELECT B.NUM_BD
                    FROM BANCO01.DC1964 A
                    INNER JOIN BANCO01.DC1965 B ON (B.COD_DEPAR = A.COD_DEPAR)
                    WHERE A.COD_USUARIO = %s
                )
                AND DM1744.COD_ASSUNTO IN (
                    SELECT B.COD_ASSUNTO
                    FROM BANCO01.DC1964 A
                    INNER JOIN BANCO01.DC1966 B ON (B.COD_DEPAR = A.COD_DEPAR)
                    WHERE A.COD_USUARIO = %s
                )
            """
            params.extend([dashboard_user_cod, dashboard_user_cod])
            query += f""" AND EXISTS (
                SELECT 1
                FROM BANCO01.DM1745
                WHERE COD_SOLICITACAO = DM1744.COD_SOLICITACAO
                  AND (
                        UPPER({text_col}) LIKE '%%SOLICITAÇÃO ENCERRADA POR%%'
                        OR UPPER({text_col}) LIKE '%%SOLICITACAO ENCERRADA POR%%'
                  )
            """
            if start_date:
                query += " AND DATA_GRAV >= %s"
                params.append(int(start_date.replace('-', '')))
            if end_date:
                query += " AND DATA_GRAV <= %s"
                params.append(int(end_date.replace('-', '')))
            query += ")"
        elif kpi_type == 'abertos':
            if start_date:
                query += " AND DM1744.DATA_CAD >= %s"
                params.append(int(start_date.replace('-', '')))
            if end_date:
                query += " AND DM1744.DATA_CAD <= %s"
                params.append(int(end_date.replace('-', '')))
        elif kpi_type == 'aprovados':
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
            if start_date: query += " AND DM1744.DATA_BAIXA >= %s"; params.append(int(start_date.replace('-', '')))
            if end_date: query += " AND DM1744.DATA_BAIXA <= %s"; params.append(int(end_date.replace('-', '')))
        elif kpi_type == 'encerrados':
            query += " AND DM1744.COD_STATUS_DOC = 'BA'"
            if start_date: query += " AND DM1744.DATA_BAIXA >= %s"; params.append(int(start_date.replace('-', '')))
            if end_date: query += " AND DM1744.DATA_BAIXA <= %s"; params.append(int(end_date.replace('-', '')))
        else:
            if status_filter:
                if isinstance(status_filter, str): status_filter = status_filter.split(',')
                query += " AND DM1744.COD_STATUS_DOC IN %s"; params.append(tuple(status_filter))
            if start_date: query += " AND DM1744.DATA_CAD >= %s"; params.append(int(start_date.replace('-', '')))
            if end_date: query += " AND DM1744.DATA_CAD <= %s"; params.append(int(end_date.replace('-', '')))
        
        if cod_solicitacao_filter: query += " AND DM1744.COD_SOLICITACAO = %s"; params.append(cod_solicitacao_filter)
        if solicitante_filter: query += " AND UPPER(DS0300.NOME_USUARIO) LIKE %s"; params.append(f"%{solicitante_filter.upper()}%")
        if assunto_filter: query += " AND DM1744.COD_ASSUNTO = %s"; params.append(assunto_filter)
        if ativo_filter:
            if ',' in str(ativo_filter):
                ids = ativo_filter.split(',')
                query += f" AND DM1744.COD_ATIVO IN ({','.join(['%s']*len(ids))})"; params.extend(ids)
            else: query += " AND DM1744.COD_ATIVO = %s"; params.append(ativo_filter)
        
        query += " ORDER BY DM1744.DATA_CAD DESC, DM1744.COD_SOLICITACAO DESC"
        if limit is None:
            query += " LIMIT 100"
        else:
            try:
                limit_int = int(limit)
            except Exception:
                limit_int = 100
            if limit_int > 0:
                query += " LIMIT %s"
                params.append(limit_int)
        cur.execute(query, params)
        rows = cur.fetchall()
        columns = [col[0].lower() for col in cur.description]
        results = [dict(zip(columns, row)) for row in rows]
        
        # Mapear status_name
        for d in results:
            d['status_name'] = self.status_map.get(d['cod_status_doc'], d['cod_status_doc'])
            
        cur.close()
        conn.close()
        return results

    def buscar_kanban_base(self, filtros):
        status_filter = filtros.get('status', [])
        cod_solicitacao_filter = filtros.get('id') or filtros.get('cod_solicitacao')
        solicitante_filter = filtros.get('solicitante')
        start_date = filtros.get('start_date')
        end_date = filtros.get('end_date')
        kpi_type = filtros.get('kpi')
        assunto_filter = filtros.get('assunto')
        assunto_q = filtros.get('assunto_q')
        q_filter = filtros.get('q')
        executor_filter = filtros.get('executor')
        etapa_filter = (filtros.get('etapa') or '').strip().lower()
        ativo_filter = filtros.get('ativo')
        aprovador_filter = filtros.get('aprovador')

        conn = get_erp_connection()
        cur = conn.cursor()
        text_col = self._get_text_col(cur)
        dashboard_user_cod = int(os.getenv("DASHBOARD_USER_COD", "1538"))

        query = f"""
            SELECT
                DM1744.COD_SOLICITACAO,
                DM1744.TITULO_SOLICITACAO,
                DM1744.COD_STATUS_DOC,
                DM1744.DATA_CAD,
                DM1744.HORA_CAD,
                DS0300.NOME_USUARIO AS SOLICITANTE,
                NOT EXISTS (
                    SELECT 1
                    FROM BANCO01.DM1745 I
                    WHERE I.COD_SOLICITACAO = DM1744.COD_SOLICITACAO
                      AND I.COD_USUARIO > 0
                ) AS NO_ITERATION,
                (COALESCE(AUTH.req_count, 0) > COALESCE(AUTH.appr_count, 0)) AS WAITING_AUTH,
                (COALESCE(AUTH.appr_count, 0) > 0) AS AUTH_APPROVED,
                COALESCE(AUTH.req_count, 0) AS AUTH_REQ_COUNT,
                COALESCE(AUTH.appr_count, 0) AS AUTH_APPR_COUNT
            FROM BANCO01.DM1744
            LEFT JOIN public.DS0300 ON (DS0300.COD_USUARIO = DM1744.COD_USUARIO)
            LEFT JOIN BANCO01.DC1739 ON (DC1739.COD_ASSUNTO = DM1744.COD_ASSUNTO)
            LEFT JOIN LATERAL (
                SELECT
                    SUM(CASE WHEN (
                        (UPPER(X.{text_col}) LIKE '%%SOLICIT%%' AND UPPER(X.{text_col}) LIKE '%%AUTORIZA%%' AND UPPER(X.{text_col}) LIKE '%%FOI ENVIAD%%')
                        OR UPPER(X.{text_col}) LIKE '%%SOLICITOU A AUTORIZA%%'
                    ) THEN 1 ELSE 0 END) AS req_count,
                    SUM(CASE WHEN (
                        (UPPER(X.{text_col}) LIKE '%%AUTORIZA%%' AND UPPER(X.{text_col}) LIKE '%%APROVAD%%')
                    ) THEN 1 ELSE 0 END) AS appr_count
                FROM BANCO01.DM1745 X
                WHERE X.COD_SOLICITACAO = DM1744.COD_SOLICITACAO
            ) AUTH ON TRUE
            WHERE DM1744.COD_ASSUNTO IN (SELECT COD_ASSUNTO FROM BANCO01.DC1966 WHERE COD_DEPAR = 16)
        """

        params = []

        status_filter_set = set()
        if status_filter:
            if isinstance(status_filter, str):
                status_filter = status_filter.split(',')
            status_filter_set = set(status_filter)
            query += " AND DM1744.COD_STATUS_DOC IN %s"
            params.append(tuple(status_filter))

        if aprovador_filter:
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
                    WHERE DSRESP.COD_USUARIO = DM1744.COD_USUARIO_RESPONS
                      AND UPPER(DSRESP.NOME_USUARIO) LIKE %s
                )
            )"""
            params.extend([f"%{clean_approver}%", f"%APROVADA POR {clean_approver}%", f"%{clean_approver}%"])

        if kpi_type in {'abertos_hoje', 'enviado_aprovacao_hoje', 'aprovados_hoje', 'andamento_hoje', 'finalizados_hoje', 'baixados_hoje'}:
            query += """
                AND DM1744.NUM_BD IN (
                    SELECT B.NUM_BD
                    FROM BANCO01.DC1964 A
                    INNER JOIN BANCO01.DC1965 B ON (B.COD_DEPAR = A.COD_DEPAR)
                    WHERE A.COD_USUARIO = %s
                )
                AND DM1744.COD_ASSUNTO IN (
                    SELECT B.COD_ASSUNTO
                    FROM BANCO01.DC1964 A
                    INNER JOIN BANCO01.DC1966 B ON (B.COD_DEPAR = A.COD_DEPAR)
                    WHERE A.COD_USUARIO = %s
                )
            """
            params.extend([dashboard_user_cod, dashboard_user_cod])

        if kpi_type == 'abertos_hoje':
            if start_date:
                query += " AND DM1744.DATA_CAD >= %s"
                params.append(int(start_date.replace('-', '')))
            if end_date:
                query += " AND DM1744.DATA_CAD <= %s"
                params.append(int(end_date.replace('-', '')))
        elif kpi_type == 'enviado_aprovacao_hoje':
            query += f""" AND EXISTS (
                SELECT 1
                FROM BANCO01.DM1745 K
                WHERE K.COD_SOLICITACAO = DM1744.COD_SOLICITACAO
                  AND UPPER(K.{text_col}) LIKE '%%SOLICIT%%'
                  AND UPPER(K.{text_col}) LIKE '%%AUTORIZA%%'
                  AND UPPER(K.{text_col}) LIKE '%%GERENT%%'
            """
            if start_date:
                query += " AND K.DATA_GRAV >= %s"
                params.append(int(start_date.replace('-', '')))
            if end_date:
                query += " AND K.DATA_GRAV <= %s"
                params.append(int(end_date.replace('-', '')))
            query += ")"
        elif kpi_type == 'aprovados_hoje':
            query += f""" AND EXISTS (
                SELECT 1
                FROM BANCO01.DM1745 K
                WHERE K.COD_SOLICITACAO = DM1744.COD_SOLICITACAO
                  AND UPPER(K.{text_col}) LIKE '%%AUTORIZA%%'
                  AND UPPER(K.{text_col}) LIKE '%%APROVAD%%'
            """
            if start_date:
                query += " AND K.DATA_GRAV >= %s"
                params.append(int(start_date.replace('-', '')))
            if end_date:
                query += " AND K.DATA_GRAV <= %s"
                params.append(int(end_date.replace('-', '')))
            query += ")"
        elif kpi_type == 'andamento_hoje':
            query += f""" AND EXISTS (
                SELECT 1
                FROM BANCO01.DM1745 K
                WHERE K.COD_SOLICITACAO = DM1744.COD_SOLICITACAO
                  AND UPPER(K.{text_col}) LIKE '%%STATUS:%%ANDAMENTO%%'
            """
            if start_date:
                query += " AND K.DATA_GRAV >= %s"
                params.append(int(start_date.replace('-', '')))
            if end_date:
                query += " AND K.DATA_GRAV <= %s"
                params.append(int(end_date.replace('-', '')))
            query += ")"
        elif kpi_type == 'finalizados_hoje':
            query += f""" AND EXISTS (
                SELECT 1
                FROM BANCO01.DM1745 K
                WHERE K.COD_SOLICITACAO = DM1744.COD_SOLICITACAO
                  AND UPPER(K.{text_col}) LIKE '%%SOLICIT%%'
                  AND UPPER(K.{text_col}) LIKE '%%FINALIZAD%%'
                  AND UPPER(K.{text_col}) NOT LIKE '%%ENCERRAD%%'
            """
            if start_date:
                query += " AND K.DATA_GRAV >= %s"
                params.append(int(start_date.replace('-', '')))
            if end_date:
                query += " AND K.DATA_GRAV <= %s"
                params.append(int(end_date.replace('-', '')))
            query += ")"
        elif kpi_type == 'baixados_hoje':
            if start_date:
                query += " AND DM1744.DATA_BAIXA >= %s"
                params.append(int(start_date.replace('-', '')))
            if end_date:
                query += " AND DM1744.DATA_BAIXA <= %s"
                params.append(int(end_date.replace('-', '')))
            query += " AND DM1744.COD_STATUS_DOC = 'BA'"
        else:
            if ('BA' in status_filter_set) and (start_date or end_date):
                if start_date and end_date:
                    query += " AND ((DM1744.COD_STATUS_DOC = 'BA' AND DM1744.DATA_BAIXA BETWEEN %s AND %s) OR (DM1744.COD_STATUS_DOC <> 'BA' AND DM1744.DATA_CAD BETWEEN %s AND %s))"
                    start_erp = int(start_date.replace('-', ''))
                    end_erp = int(end_date.replace('-', ''))
                    params.extend([start_erp, end_erp, start_erp, end_erp])
                elif start_date:
                    query += " AND ((DM1744.COD_STATUS_DOC = 'BA' AND DM1744.DATA_BAIXA >= %s) OR (DM1744.COD_STATUS_DOC <> 'BA' AND DM1744.DATA_CAD >= %s))"
                    start_erp = int(start_date.replace('-', ''))
                    params.extend([start_erp, start_erp])
                elif end_date:
                    query += " AND ((DM1744.COD_STATUS_DOC = 'BA' AND DM1744.DATA_BAIXA <= %s) OR (DM1744.COD_STATUS_DOC <> 'BA' AND DM1744.DATA_CAD <= %s))"
                    end_erp = int(end_date.replace('-', ''))
                    params.extend([end_erp, end_erp])
            else:
                if start_date:
                    query += " AND DM1744.DATA_CAD >= %s"
                    params.append(int(start_date.replace('-', '')))
                if end_date:
                    query += " AND DM1744.DATA_CAD <= %s"
                    params.append(int(end_date.replace('-', '')))

        if cod_solicitacao_filter:
            query += " AND DM1744.COD_SOLICITACAO = %s"
            params.append(cod_solicitacao_filter)
        if solicitante_filter:
            query += " AND UPPER(DS0300.NOME_USUARIO) LIKE %s"
            params.append(f"%{solicitante_filter.upper()}%")
        if assunto_filter:
            query += " AND DM1744.COD_ASSUNTO = %s"
            params.append(assunto_filter)
        if assunto_q:
            query += " AND UPPER(COALESCE(DC1739.DESCR_ASSUNTO, '')) LIKE %s"
            params.append(f"%{str(assunto_q).upper()}%")
        if ativo_filter:
            if ',' in str(ativo_filter):
                ids = ativo_filter.split(',')
                query += f" AND DM1744.COD_ATIVO IN ({','.join(['%s']*len(ids))})"
                params.extend(ids)
            else:
                query += " AND DM1744.COD_ATIVO = %s"
                params.append(ativo_filter)
        if q_filter:
            like = f"%{str(q_filter).upper()}%"
            query += f""" AND (
                UPPER(COALESCE(DM1744.TITULO_SOLICITACAO, '')) LIKE %s
                OR UPPER(COALESCE(DM1744.DESCR_SOLICITACAO, '')) LIKE %s
                OR EXISTS(
                    SELECT 1 FROM BANCO01.DM1745 K
                    WHERE K.COD_SOLICITACAO = DM1744.COD_SOLICITACAO
                      AND UPPER(K.{text_col}) LIKE %s
                )
            )"""
            params.extend([like, like, like])
        if executor_filter:
            clean_exec = executor_filter.upper().split(" - ")[0].split(" -")[0].strip()
            if etapa_filter in {"", "qualquer", "all"}:
                query += f""" AND (
                    EXISTS (
                        SELECT 1 FROM BANCO01.DM1745 K
                        WHERE K.COD_SOLICITACAO = DM1744.COD_SOLICITACAO
                          AND (
                            UPPER(K.{text_col}) LIKE %s
                            OR UPPER(K.{text_col}) LIKE %s
                            OR UPPER(K.{text_col}) LIKE %s
                          )
                    )
                    OR EXISTS (
                        SELECT 1 FROM BANCO01.DM1745 K
                        JOIN public.DS0300 U ON (U.COD_USUARIO = K.COD_USUARIO)
                        WHERE K.COD_SOLICITACAO = DM1744.COD_SOLICITACAO
                          AND UPPER(U.NOME_USUARIO) LIKE %s
                    )
                )"""
                params.extend([
                    f"%APROVAD% POR {clean_exec}%",
                    f"%FINALIZAD% POR {clean_exec}%",
                    f"%ENCERRAD% POR {clean_exec}%",
                    f"%{clean_exec}%",
                ])
            elif etapa_filter in {"aprovado", "aprovacao"}:
                query += f""" AND EXISTS (
                    SELECT 1 FROM BANCO01.DM1745 K
                    WHERE K.COD_SOLICITACAO = DM1744.COD_SOLICITACAO
                      AND UPPER(K.{text_col}) LIKE %s
                )"""
                params.append(f"%APROVAD% POR {clean_exec}%")
            elif etapa_filter in {"finalizado", "finalizacao"}:
                query += f""" AND EXISTS (
                    SELECT 1 FROM BANCO01.DM1745 K
                    WHERE K.COD_SOLICITACAO = DM1744.COD_SOLICITACAO
                      AND UPPER(K.{text_col}) LIKE %s
                )"""
                params.append(f"%FINALIZAD% POR {clean_exec}%")
            elif etapa_filter in {"encerrado", "encerramento"}:
                query += f""" AND EXISTS (
                    SELECT 1 FROM BANCO01.DM1745 K
                    WHERE K.COD_SOLICITACAO = DM1744.COD_SOLICITACAO
                      AND UPPER(K.{text_col}) LIKE %s
                )"""
                params.append(f"%ENCERRAD% POR {clean_exec}%")
            elif etapa_filter in {"comentou", "comentario", "comentários", "comentarios"}:
                query += f""" AND EXISTS (
                    SELECT 1 FROM BANCO01.DM1745 K
                    JOIN public.DS0300 U ON (U.COD_USUARIO = K.COD_USUARIO)
                    WHERE K.COD_SOLICITACAO = DM1744.COD_SOLICITACAO
                      AND UPPER(U.NOME_USUARIO) LIKE %s
                )"""
                params.append(f"%{clean_exec}%")

        query += " ORDER BY DM1744.DATA_CAD DESC, DM1744.COD_SOLICITACAO DESC"

        cur.execute(query, params)
        rows = cur.fetchall()
        cur.close()
        conn.close()

        return [
            {
                "id": int(r[0]),
                "titulo": r[1],
                "status": r[2],
                "data_cad": int(r[3] or 0),
                "hora_cad": int(r[4] or 0),
                "solicitante": r[5],
                "no_iteration": bool(r[6]),
                "waiting_auth": bool(r[7]),
                "auth_approved": bool(r[8]),
                "auth_req_count": int(r[9] or 0),
                "auth_appr_count": int(r[10] or 0),
            }
            for r in rows
        ]

    def verificar_nota_local(self, cod_solicitacao):
        """Verifica se existe nota local para o chamado."""
        # Como o ERPRepository não deve acessar o banco SQLite diretamente (SRP),
        # este método é apenas um placeholder ou deve ser removido em favor do LocalNoteRepository.
        # No DashboardService, vamos usar o LocalNoteRepository.
        pass
        conn = get_erp_connection()
        cur = conn.cursor()
        text_col = self._get_text_col(cur)
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
        
        results = []
        for t in tickets:
            cod = t[0]
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
            results.append({"ticket": t, "comentarios": comms})
            
        cur.close()
        conn.close()
        return results
