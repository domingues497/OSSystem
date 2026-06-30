import os
import psycopg2

LOCAL_SCHEMA = os.getenv("LOCAL_DB_SCHEMA", "capalti")
TABLE_NOTES = f"{LOCAL_SCHEMA}.chamados_notes"
TABLE_ALERTS = f"{LOCAL_SCHEMA}.chamados_alerts"
TABLE_ACCESS_DAILY = f"{LOCAL_SCHEMA}.chamados_access_daily"
TABLE_TICKET_ASSIGNEES = f"{LOCAL_SCHEMA}.chamados_ticket_assignees"
TABLE_USERS = f"{LOCAL_SCHEMA}.chamados_users"
TABLE_USER_DEPARTMENTS = f"{LOCAL_SCHEMA}.chamados_user_departments"
TABLE_USER_SUBJECTS = f"{LOCAL_SCHEMA}.chamados_user_subjects"

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
    cur.execute(
        "SELECT 1 FROM information_schema.schemata WHERE schema_name = %s LIMIT 1",
        (schema,),
    )
    schema_exists = cur.fetchone() is not None
    if not schema_exists:
        cur.execute(f"CREATE SCHEMA {schema}")
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
    cur.execute(f"""
        CREATE TABLE IF NOT EXISTS {schema}.chamados_users (
            id BIGSERIAL PRIMARY KEY,
            username TEXT NOT NULL UNIQUE,
            password_hash TEXT NOT NULL,
            display_name TEXT NOT NULL,
            profile TEXT NOT NULL DEFAULT 'subject',
            is_active BOOLEAN NOT NULL DEFAULT TRUE,
            last_login_at TIMESTAMP NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    cur.execute(f"""
        CREATE TABLE IF NOT EXISTS {schema}.chamados_user_departments (
            user_id BIGINT NOT NULL REFERENCES {schema}.chamados_users(id) ON DELETE CASCADE,
            cod_depar INTEGER NOT NULL,
            nome_departamento TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            PRIMARY KEY (user_id, cod_depar)
        )
    """)
    cur.execute(f"""
        CREATE TABLE IF NOT EXISTS {schema}.chamados_user_subjects (
            user_id BIGINT NOT NULL REFERENCES {schema}.chamados_users(id) ON DELETE CASCADE,
            cod_assunto INTEGER NOT NULL,
            descr_assunto TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            PRIMARY KEY (user_id, cod_assunto)
        )
    """)
    conn.commit()
    conn.close()
