import os
import psycopg2

LOCAL_SCHEMA = os.getenv("LOCAL_DB_SCHEMA", "capalti")
TABLE_NOTES = f"{LOCAL_SCHEMA}.chamados_notes"
TABLE_ALERTS = f"{LOCAL_SCHEMA}.chamados_alerts"
TABLE_ACCESS_DAILY = f"{LOCAL_SCHEMA}.chamados_access_daily"
TABLE_TICKET_ASSIGNEES = f"{LOCAL_SCHEMA}.chamados_ticket_assignees"

def get_local_connection(_db_config=None):
    return psycopg2.connect(
        dbname=os.getenv("ERP_DB_NAME"),
        user=os.getenv("ERP_DB_USER"),
        password=os.getenv("ERP_DB_PASS"),
        host=os.getenv("ERP_DB_HOST"),
        port=os.getenv("ERP_DB_PORT")
    )

def init_local_db(schema_name=None):
    schema = schema_name or LOCAL_SCHEMA
    conn = get_local_connection(schema)
    cur = conn.cursor()
    cur.execute(f"CREATE SCHEMA IF NOT EXISTS {schema}")
    cur.execute(f"""
        CREATE TABLE IF NOT EXISTS {schema}.chamados_notes (
            id BIGSERIAL PRIMARY KEY,
            cod_solicitacao BIGINT NOT NULL,
            note TEXT NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    cur.execute(f"""
        CREATE TABLE IF NOT EXISTS {schema}.chamados_alerts (
            id BIGSERIAL PRIMARY KEY,
            cod_solicitacao BIGINT NOT NULL,
            alert_type TEXT NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    cur.execute(f"""
        CREATE TABLE IF NOT EXISTS {schema}.chamados_access_daily (
            id BIGSERIAL PRIMARY KEY,
            day_erp INTEGER NOT NULL,
            ip TEXT NOT NULL,
            count INTEGER NOT NULL DEFAULT 0,
            first_seen TIMESTAMP,
            last_seen TIMESTAMP,
            last_path TEXT,
            user_agent TEXT,
            UNIQUE(day_erp, ip)
        )
    """)
    cur.execute(f"""
        CREATE TABLE IF NOT EXISTS {schema}.chamados_ticket_assignees (
            cod_solicitacao BIGINT PRIMARY KEY,
            atendente TEXT NOT NULL,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    conn.commit()
    conn.close()
