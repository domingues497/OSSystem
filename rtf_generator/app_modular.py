from flask import Flask
from config import Config
from routes.erp_routes import erp_bp
from routes.local_routes import local_bp
from routes.web_routes import web_bp
from database.local_connection import init_local_db
import os
import logging

def create_app():
    app = Flask(__name__)
    app.config.from_object(Config)

    # Configurar logging
    logging.basicConfig(level=logging.INFO)
    app.logger.setLevel(logging.INFO)

    # Inicializar pastas necessárias
    os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
    os.makedirs(app.config['GENERATED_FOLDER'], exist_ok=True)
    
    # Inicializar banco local
    init_local_db(app.config['LOCAL_DB'])

    # Registrar Blueprints
    app.register_blueprint(web_bp)
    app.register_blueprint(erp_bp, url_prefix='/api/erp')
    app.register_blueprint(local_bp, url_prefix='/api/local')

    return app

if __name__ == '__main__':
    app = create_app()
    app.run(debug=True, host='0.0.0.0', port=5000)
