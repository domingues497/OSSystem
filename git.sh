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

# Se houver token configurado, usa GIT_ASKPASS para autenticação HTTPS
# sem gravar o segredo no script ou no comando.
ASKPASS_FILE=""
cleanup() {
  if [ -n "${ASKPASS_FILE:-}" ] && [ -f "$ASKPASS_FILE" ]; then
    rm -f "$ASKPASS_FILE"
  fi
}
trap cleanup EXIT

if [ -n "${GITHUB_TOKEN:-}" ]; then
  export GIT_TERMINAL_PROMPT=0
  export GITHUB_USERNAME="${GITHUB_USERNAME:-domingues497}"
  ASKPASS_FILE="$(mktemp)"
  cat >"$ASKPASS_FILE" <<'EOF'
#!/usr/bin/env sh
case "$1" in
  *Username*) printf '%s\n' "${GITHUB_USERNAME:-domingues497}" ;;
  *Password*) printf '%s\n' "${GITHUB_TOKEN:-}" ;;
  *) printf '\n' ;;
esac
EOF
  chmod 700 "$ASKPASS_FILE"
  export GIT_ASKPASS="$ASKPASS_FILE"
fi

cd /opt/rtf_generator
git pull --ff-only

cd /opt/rtf_generator/rtf_generator
if [ ! -d "venv" ]; then
  python3 -m venv venv
fi
./venv/bin/pip install -U pip
./venv/bin/pip install -r requirements.txt

$SUDO systemctl restart rtf_generator
$SUDO systemctl status rtf_generator --no-pager
