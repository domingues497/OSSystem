import os
import logging
import threading
import time
from datetime import datetime, timedelta
from pathlib import Path
from dotenv import load_dotenv
from flask import Flask, request

_backend_env_path = Path(__file__).resolve().parent.parent / "backend" / ".env"
load_dotenv(dotenv_path=_backend_env_path, override=False)

from config import Config
from routes.erp_routes import erp_bp
from routes.local_routes import local_bp
from routes.notify_routes import notify_bp, run_access_report_job
from routes.web_routes import web_bp
from database.local_connection import init_local_db
from repositories.local_access_repository import LocalAccessRepository

_access_report_scheduler_started = False

def _env_bool(name, default=True):
    raw = os.getenv(name)
    if raw is None:
        return bool(default)
    return str(raw).strip().lower() in {"1", "true", "yes", "y", "on"}

def _parse_hhmm(value, default_h=18, default_m=30):
    raw = (value or "").strip()
    if not raw:
        return default_h, default_m
    try:
        parts = raw.split(":")
        h = int(parts[0])
        m = int(parts[1]) if len(parts) > 1 else 0
        if h < 0 or h > 23 or m < 0 or m > 59:
            return default_h, default_m
        return h, m
    except Exception:
        return default_h, default_m

def _next_run_at(hour, minute, now=None):
    now = now or datetime.now()
    run_at = now.replace(hour=hour, minute=minute, second=0, microsecond=0)
    if run_at <= now:
        run_at = run_at + timedelta(days=1)
    return run_at

def _start_access_report_scheduler(app):
    global _access_report_scheduler_started
    if _access_report_scheduler_started:
        return
    if app.debug and os.environ.get("WERKZEUG_RUN_MAIN") != "true":
        return

    tg_targets = [t.strip() for t in (os.getenv("TELEGRAM_CHAT_IDS", "") or "").split(",") if t.strip()]
    has_tg = bool(os.getenv("TELEGRAM_BOT_TOKEN")) and bool(tg_targets)
    if not has_tg:
        return

    if not _env_bool("ACCESS_REPORT_DAILY_ENABLED", True):
        return

    hour, minute = _parse_hhmm(os.getenv("ACCESS_REPORT_DAILY_AT", "18:30"), 18, 30)

    def loop():
        while True:
            try:
                next_run = _next_run_at(hour, minute)
                sleep_sec = max(0.0, (next_run - datetime.now()).total_seconds())
                time.sleep(sleep_sec)
                result = run_access_report_job(force=True, dry_run=False)
                status = int(result.get("status") or 0)
                payload = result.get("payload") or {}
                if status >= 400:
                    app.logger.warning(f"access_report diário falhou: {payload}")
                else:
                    if payload.get("sent"):
                        app.logger.info(f"access_report diário enviado: {payload}")
            except Exception as e:
                try:
                    app.logger.exception(e)
                except Exception:
                    pass
                time.sleep(10)

    t = threading.Thread(target=loop, daemon=True, name="access-report-daily")
    t.start()
    _access_report_scheduler_started = True

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

    _start_access_report_scheduler(app)

    return app

if __name__ == '__main__':
    app = create_app()
    app.run(debug=True, host='0.0.0.0', port=5000)
