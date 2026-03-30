import os
from dotenv import load_dotenv

load_dotenv()

class Config:
    UPLOAD_FOLDER = os.environ.get('UPLOAD_FOLDER', 'uploads')
    GENERATED_FOLDER = os.environ.get('GENERATED_FOLDER', 'generated')
    LOCAL_DB = os.path.join(os.path.dirname(__file__), 'local_notes.db')
    
    ERP_DB_NAME = os.getenv("ERP_DB_NAME")
    ERP_DB_USER = os.getenv("ERP_DB_USER")
    ERP_DB_PASS = os.getenv("ERP_DB_PASS")
    ERP_DB_HOST = os.getenv("ERP_DB_HOST")
    ERP_DB_PORT = os.getenv("ERP_DB_PORT")
