#!/usr/bin/env bash
set -euo pipefail

SUDO=""
if [ "$(id -u)" -ne 0 ]; then
  SUDO="sudo"
fi

# Carrega credenciais opcionais fora do repositório.
# Exemplo de arquivo:
#   GITHUB_USERNAME=domingues497
#   GITHUB_TOKEN=ghp_xxx
DEPLOY_ENV="${DEPLOY_ENV:-/root/.config/rtf_generator/deploy.env}"
if [ -f "$DEPLOY_ENV" ]; then
  # shellcheck disable=SC1090
  . "$DEPLOY_ENV"
fi

# Normaliza valores carregados do arquivo para evitar problemas com CRLF
# ou espacos acidentais no inicio/fim.
trim_var() {
  printf '%s' "$1" | tr -d '\r' | sed 's/^[[:space:]]*//;s/[[:space:]]*$//'
}
GITHUB_USERNAME="$(trim_var "${GITHUB_USERNAME:-}")"
GITHUB_TOKEN="$(trim_var "${GITHUB_TOKEN:-}")"

if [ -n "${GITHUB_TOKEN:-}" ] && [ -z "${GITHUB_USERNAME:-}" ]; then
  GITHUB_USERNAME="domingues497"
fi

if [ -f "$DEPLOY_ENV" ] && { [ -z "${GITHUB_USERNAME:-}" ] || [ -z "${GITHUB_TOKEN:-}" ]; }; then
  echo "Erro: arquivo $DEPLOY_ENV encontrado, mas as variáveis não foram carregadas corretamente."
  echo "Use exatamente:"
  echo "  GITHUB_USERNAME=domingues497"
  echo "  GITHUB_TOKEN=seu_token"
  exit 1
fi

cd /opt/rtf_generator
if [ -n "${GITHUB_TOKEN:-}" ]; then
  AUTH_B64="$(printf '%s' "${GITHUB_USERNAME}:${GITHUB_TOKEN}" | base64 | tr -d '\n\r')"
  git -c credential.helper= -c http.extraHeader="AUTHORIZATION: basic ${AUTH_B64}" pull --ff-only
else
  git pull --ff-only
fi

cd /opt/rtf_generator/rtf_generator
if [ ! -d "venv" ]; then
  python3 -m venv venv
fi
./venv/bin/pip install -U pip
./venv/bin/pip install -r requirements.txt

$SUDO systemctl restart rtf_generator
$SUDO systemctl status rtf_generator --no-pager
