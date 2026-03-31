from database.local_connection import get_local_connection

class LocalAlertRepository:
    def __init__(self, db_path):
        self.db_path = db_path

    def was_sent(self, cod_solicitacao, alert_type):
        conn = get_local_connection(self.db_path)
        cur = conn.cursor()
        cur.execute("SELECT 1 FROM alerts WHERE cod_solicitacao = ? AND alert_type = ? LIMIT 1", (cod_solicitacao, alert_type))
        exists = cur.fetchone() is not None
        conn.close()
        return exists

    def mark_sent(self, cod_solicitacao, alert_type):
        conn = get_local_connection(self.db_path)
        cur = conn.cursor()
        cur.execute("INSERT INTO alerts (cod_solicitacao, alert_type) VALUES (?, ?)", (cod_solicitacao, alert_type))
        conn.commit()
        conn.close()
