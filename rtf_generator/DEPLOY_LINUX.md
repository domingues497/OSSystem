# Deploy no Linux (Git + Gunicorn + systemd + Nginx)

## 1) Preparar o repositório (Windows)

Na raiz do projeto:

```bash
git init
git add .
git commit -m "Initial commit"
```

Crie o repositório remoto (GitHub/GitLab) e faça push:

```bash
git remote add origin <URL_DO_REPO>
git branch -M main
git push -u origin main
```

## 2) Preparar o servidor (Ubuntu/Debian)

Instalar dependências:

```bash
sudo apt update
sudo apt install -y python3 python3-venv python3-pip nginx
```

Se for usar PostgreSQL remoto, não precisa instalar servidor Postgres, mas pode precisar de DNS/rota/liberação de porta.

## 3) Clonar e configurar a aplicação

```bash
sudo mkdir -p /opt/rtf_generator
sudo chown -R $USER:$USER /opt/rtf_generator
cd /opt/rtf_generator
git clone https://github.com/domingues497/OSSystem.git .
cd rtf_generator
python3 -m venv venv
./venv/bin/pip install -U pip
./venv/bin/pip install -r requirements.txt
```

## 4) Configurar variáveis de ambiente

Copie o exemplo e ajuste:

```bash
cp .env.example .env
nano .env
```

Campos principais:

- ERP_DB_HOST / ERP_DB_PORT / ERP_DB_NAME / ERP_DB_USER / ERP_DB_PASS
- DASHBOARD_USER_COD
- LOCAL_DB (recomendado usar caminho persistente, ex.: `/var/lib/rtf_generator/local_notes.db`)

Criar diretório de dados (se usar LOCAL_DB em /var/lib):

```bash
sudo mkdir -p /var/lib/rtf_generator
sudo chown -R $USER:$USER /var/lib/rtf_generator
```

## 5) Rodar via systemd (Gunicorn)

Copie o service:

```bash
sudo cp deploy/rtf_generator.service /etc/systemd/system/rtf_generator.service
sudo systemctl daemon-reload
sudo systemctl enable --now rtf_generator
sudo systemctl status rtf_generator --no-pager
```

Logs:

```bash
journalctl -u rtf_generator -f
```

## 6) Publicar via Nginx

```bash
sudo cp deploy/nginx_rtf_generator.conf /etc/nginx/sites-available/rtf_generator
sudo ln -sf /etc/nginx/sites-available/rtf_generator /etc/nginx/sites-enabled/rtf_generator
sudo nginx -t
sudo systemctl reload nginx
```

## 7) Teste

Local (no servidor):

```bash
curl -I http://127.0.0.1:8000/
curl -I http://localhost/
```

## 7.1) Relatório diário de IPs (Telegram)

Para enviar 1 vez ao dia (18:30) um resumo dos IPs que acessaram o sistema no dia, configure um cron no servidor:

```bash
crontab -e
```

Adicionar:

```bash
30 18 * * * curl -s -X POST http://127.0.0.1:8000/api/notify/access_report >/dev/null 2>&1
```

## 8) Atualização (deploy de novas versões)

```bash
cd /opt/rtf_generator
git pull
cd rtf_generator
./venv/bin/pip install -r requirements.txt
sudo systemctl restart rtf_generator
```

## Observação: app_modular

O deploy via Gunicorn/systemd sobe a aplicação pelo arquivo `wsgi.py`, que instancia o app usando `app_modular.create_app()`.
