from database.local_connection import TABLE_ALERTS, get_local_connection

class LocalAlertRepository:
    def __init__(self, db_path):
        self.db_path = db_path

    def was_sent(self, cod_solicitacao, alert_type):
        conn = get_local_connection(self.db_path)
        cur = conn.cursor()
        cur.execute(
            f"SELECT 1 FROM {TABLE_ALERTS} WHERE cod_solicitacao = %s AND alert_type = %s LIMIT 1",
            (cod_solicitacao, alert_type)
        )
        exists = cur.fetchone() is not None
        conn.close()
        return exists

    def mark_sent(self, cod_solicitacao, alert_type):
        conn = get_local_connection(self.db_path)
        cur = conn.cursor()
        cur.execute(
            f"INSERT INTO {TABLE_ALERTS} (cod_solicitacao, alert_type) VALUES (%s, %s)",
            (cod_solicitacao, alert_type)
        )
        conn.commit()
        conn.close()
