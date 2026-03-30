from database.local_connection import get_local_connection

class LocalNoteRepository:
    def __init__(self, db_path):
        self.db_path = db_path

    def insert_note(self, cod_solicitacao, note):
        conn = get_local_connection(self.db_path)
        cur = conn.cursor()
        cur.execute("INSERT INTO notes (cod_solicitacao, note) VALUES (?, ?)", (cod_solicitacao, note))
        conn.commit()
        conn.close()

    def get_notes_by_ticket(self, cod_solicitacao):
        conn = get_local_connection(self.db_path)
        cur = conn.cursor()
        cur.execute("SELECT note, created_at FROM notes WHERE cod_solicitacao = ? ORDER BY created_at DESC", (cod_solicitacao,))
        rows = cur.fetchall()
        conn.close()
        return [{"note": r["note"], "created_at": r["created_at"]} for r in rows]

    def get_ticket_ids_with_notes(self, ticket_ids):
        if not ticket_ids: return set()
        conn = get_local_connection(self.db_path)
        cur = conn.cursor()
        placeholders = ','.join(['?'] * len(ticket_ids))
        cur.execute(f"SELECT DISTINCT cod_solicitacao FROM notes WHERE cod_solicitacao IN ({placeholders})", ticket_ids)
        ids = {int(r[0]) for r in cur.fetchall()}
        conn.close()
        return ids

    def has_note(self, cod_solicitacao):
        conn = get_local_connection(self.db_path)
        cur = conn.cursor()
        cur.execute("SELECT 1 FROM notes WHERE cod_solicitacao = ? LIMIT 1", (cod_solicitacao,))
        exists = cur.fetchone() is not None
        conn.close()
        return exists
