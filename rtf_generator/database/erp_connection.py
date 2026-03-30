import psycopg2
import os

def get_erp_connection():
    return psycopg2.connect(
        dbname=os.getenv("ERP_DB_NAME"),
        user=os.getenv("ERP_DB_USER"),
        password=os.getenv("ERP_DB_PASS"),
        host=os.getenv("ERP_DB_HOST"),
        port=os.getenv("ERP_DB_PORT")
    )
