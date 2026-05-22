import os
import logging
from pathlib import Path
from dotenv import load_dotenv
from flask import Flask, request

_backend_env_path = Path(__file__).resolve().parent.parent / "backend" / ".env"
load_dotenv(dotenv_path=_backend_env_path, override=False)

from config import Config
from routes.erp_routes import erp_bp
from routes.local_routes import local_bp
from routes.notify_routes import notify_bp
from routes.web_routes import web_bp
from database.local_connection import init_local_db
from repositories.local_access_repository import LocalAccessRepository

def create_app():
    app = Flask(__name__)
    app.config.from_object(Config)

    # Configurar logging
    logging.basicConfig(level=logging.INFO)
    app.logger.setLevel(logging.INFO)

    # Inicializar pastas necessárias
    os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
    os.makedirs(app.config['GENERATED_FOLDER'], exist_ok=True)
    
    # Inicializar schema/tabelas auxiliares apenas quando explicitamente habilitado
    if app.config.get('INIT_LOCAL_DB_ON_START'):
        init_local_db(app.config['LOCAL_DB'])
    access_repo = LocalAccessRepository(app.config['LOCAL_DB'])

    @app.before_request
    def _track_access():
        try:
            p = request.path or ""
            if p.startswith("/static/") or p == "/favicon.ico":
                return
            xff = (request.headers.get("X-Forwarded-For") or "").split(",")[0].strip()
            ip = xff or (request.remote_addr or "")
            ua = request.headers.get("User-Agent") or ""
            
            # Log de acesso em arquivo de texto
            log_path = os.path.join(app.root_path, "access.log")
            from datetime import datetime
            now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            with open(log_path, "a", encoding="utf-8") as f:
                f.write(f"{now_str}|{ip}|{p}|{ua}\n")
        except Exception as e:
            app.logger.error(f"Erro ao gravar access.log: {e}")
            return

    # Registrar Blueprints
    app.register_blueprint(web_bp)
    app.register_blueprint(erp_bp, url_prefix='/api/erp')
    app.register_blueprint(local_bp, url_prefix='/api/local')
    app.register_blueprint(notify_bp, url_prefix='/api/notify')

    return app

if __name__ == '__main__':
    app = create_app()
    app.run(debug=True, host='0.0.0.0', port=5000)
