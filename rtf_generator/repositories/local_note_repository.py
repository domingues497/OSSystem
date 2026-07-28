from database.local_connection import (
    TABLE_CHAMADOS_USUARIOS,
    TABLE_NOTES,
    TABLE_TICKET_ASSIGNEES,
    get_local_connection,
)
from utils.datetime_utils import format_display_datetime

class LocalNoteRepository:
    def __init__(self, db_path):
        self.db_path = db_path

    def insert_note(self, cod_solicitacao, note):
        conn = get_local_connection(self.db_path)
        cur = conn.cursor()
        cur.execute(
            f"INSERT INTO {TABLE_NOTES} (cod_solicitacao, note) VALUES (%s, %s)",
            (cod_solicitacao, note)
        )
        conn.commit()
        conn.close()

    def get_notes_by_ticket(self, cod_solicitacao):
        conn = get_local_connection(self.db_path)
        cur = conn.cursor()
        cur.execute(
            f"SELECT note, created_at FROM {TABLE_NOTES} WHERE cod_solicitacao = %s ORDER BY created_at DESC",
            (cod_solicitacao,)
        )
        rows = cur.fetchall()
        conn.close()
        return [{"note": r[0], "created_at": format_display_datetime(r[1])} for r in rows]

    def get_ticket_ids_with_notes(self, ticket_ids):
        if not ticket_ids: return set()
        conn = get_local_connection(self.db_path)
        cur = conn.cursor()
        placeholders = ','.join(['%s'] * len(ticket_ids))
        cur.execute(
            f"SELECT DISTINCT cod_solicitacao FROM {TABLE_NOTES} WHERE cod_solicitacao IN ({placeholders})",
            ticket_ids
        )
        ids = {int(r[0]) for r in cur.fetchall()}
        conn.close()
        return ids

    def has_note(self, cod_solicitacao):
        conn = get_local_connection(self.db_path)
        cur = conn.cursor()
        cur.execute(f"SELECT 1 FROM {TABLE_NOTES} WHERE cod_solicitacao = %s LIMIT 1", (cod_solicitacao,))
        exists = cur.fetchone() is not None
        conn.close()
        return exists

    def upsert_assignee(self, cod_solicitacao, atendente):
        conn = get_local_connection(self.db_path)
        cur = conn.cursor()
        cur.execute(
            """
            INSERT INTO {table} (cod_solicitacao, atendente, updated_at)
            VALUES (%s, %s, CURRENT_TIMESTAMP)
            ON CONFLICT(cod_solicitacao) DO UPDATE SET
                atendente = EXCLUDED.atendente,
                updated_at = CURRENT_TIMESTAMP
            """.format(table=TABLE_TICKET_ASSIGNEES),
            (cod_solicitacao, atendente)
        )
        conn.commit()
        conn.close()

    def delete_assignee(self, cod_solicitacao):
        conn = get_local_connection(self.db_path)
        cur = conn.cursor()
        cur.execute(f"DELETE FROM {TABLE_TICKET_ASSIGNEES} WHERE cod_solicitacao = %s", (cod_solicitacao,))
        conn.commit()
        conn.close()

    def get_assignee_by_ticket(self, cod_solicitacao):
        conn = get_local_connection(self.db_path)
        cur = conn.cursor()
        cur.execute(
            f"SELECT atendente FROM {TABLE_TICKET_ASSIGNEES} WHERE cod_solicitacao = %s LIMIT 1",
            (cod_solicitacao,)
        )
        row = cur.fetchone()
        conn.close()
        return row[0] if row else ""

    def get_assignees_by_ticket_ids(self, ticket_ids):
        if not ticket_ids:
            return {}
        conn = get_local_connection(self.db_path)
        cur = conn.cursor()
        placeholders = ",".join(["%s"] * len(ticket_ids))
        cur.execute(
            f"SELECT cod_solicitacao, atendente FROM {TABLE_TICKET_ASSIGNEES} WHERE cod_solicitacao IN ({placeholders})",
            ticket_ids
        )
        rows = cur.fetchall()
        conn.close()
        return {int(r[0]): r[1] for r in rows}

    def get_distinct_assignees(self):
        conn = get_local_connection(self.db_path)
        cur = conn.cursor()
        cur.execute(
            f"""
            SELECT DISTINCT atendente
            FROM {TABLE_TICKET_ASSIGNEES}
            WHERE atendente IS NOT NULL
              AND BTRIM(atendente) <> ''
            ORDER BY atendente
            """
        )
        rows = cur.fetchall()
        conn.close()
        return [r[0] for r in rows]

    def upsert_chamados_usuario_contato(self, cod_usuario, teams_user=None, whatsapp_user=None, cod_gestor=None):
        conn = get_local_connection(self.db_path)
        cur = conn.cursor()
        cur.execute(
            f"""
            UPDATE {TABLE_CHAMADOS_USUARIOS}
            SET teams_user = %s,
                whatsapp_user = %s,
                cod_gestor = %s
            WHERE cod_usuario = %s
            """,
            (teams_user, whatsapp_user, cod_gestor, int(cod_usuario)),
        )
        if cur.rowcount == 0:
            cur.execute(
                f"""
                INSERT INTO {TABLE_CHAMADOS_USUARIOS} (cod_usuario, teams_user, whatsapp_user, cod_gestor)
                VALUES (%s, %s, %s, %s)
                """,
                (int(cod_usuario), teams_user, whatsapp_user, cod_gestor),
            )
        conn.commit()
        conn.close()
