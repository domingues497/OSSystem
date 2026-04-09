import sqlite3
import os

def get_local_connection(db_path):
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    return conn

def init_local_db(db_path):
    conn = get_local_connection(db_path)
    cur = conn.cursor()
    cur.execute("""
        CREATE TABLE IF NOT EXISTS notes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            cod_solicitacao INTEGER NOT NULL,
            note TEXT NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    cur.execute("""
        CREATE TABLE IF NOT EXISTS alerts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            cod_solicitacao INTEGER NOT NULL,
            alert_type TEXT NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    cur.execute("""
        CREATE TABLE IF NOT EXISTS access_daily (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            day_erp INTEGER NOT NULL,
            ip TEXT NOT NULL,
            count INTEGER NOT NULL DEFAULT 0,
            first_seen TEXT,
            last_seen TEXT,
            last_path TEXT,
            user_agent TEXT,
            UNIQUE(day_erp, ip)
        )
    """)
    conn.commit()
    conn.close()
