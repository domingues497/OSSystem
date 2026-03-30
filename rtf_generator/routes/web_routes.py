from flask import Blueprint, render_template, request, send_file, redirect, url_for
from werkzeug.utils import secure_filename
import os
import re
from config import Config

web_bp = Blueprint('web', __name__)

def extract_fields(filepath):
    with open(filepath, 'r', encoding='utf-8', errors='ignore') as f:
        content = f.read()
    fields = re.findall(r'\{\{(.*?)\}\}', content)
    return list(set(fields))

@web_bp.route('/')
def index():
    return render_template('index.html')

@web_bp.route('/upload', methods=['POST'])
def upload_file():
    if 'rtf_file' not in request.files:
        return redirect(request.url)
    file = request.files['rtf_file']
    if file.filename == '':
        return redirect(request.url)
    if file:
        filename = secure_filename(file.filename)
        filepath = os.path.join(Config.UPLOAD_FOLDER, filename)
        file.save(filepath)
        return redirect(url_for('web.edit_file', filename=filename))

@web_bp.route('/edit/<filename>')
def edit_file(filename):
    filepath = os.path.join(Config.UPLOAD_FOLDER, filename)
    fields = extract_fields(filepath)
    return render_template('edit.html', filename=filename, fields=fields)

@web_bp.route('/generate/<filename>', methods=['POST'])
def generate_file(filename):
    original_filepath = os.path.join(Config.UPLOAD_FOLDER, filename)
    with open(original_filepath, 'r', encoding='utf-8', errors='ignore') as f:
        content = f.read()

    form_data = request.form
    for field, value in form_data.items():
        content = content.replace(f'{{{{{field}}}}}', value)

    new_filename = f'generated_{filename}'
    generated_filepath = os.path.join(Config.GENERATED_FOLDER, new_filename)
    with open(generated_filepath, 'w', encoding='utf-8') as f:
        f.write(content)

    return send_file(generated_filepath, as_attachment=True)

@web_bp.route('/produtividade')
def produtividade_page():
    return render_template('produtividade.html')

@web_bp.route('/chamados')
def chamados_page():
    return render_template('chamados.html')
