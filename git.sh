#!/usr/bin/env bash
set -euo pipefail

SUDO=""
if [ "$(id -u)" -ne 0 ]; then
  SUDO="sudo"
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
