#!/usr/bin/env bash
set -euo pipefail

REPO_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
INSTALL_DIR="/opt/cloudflare-ddns"
SERVICE_NAME="cloudflare-ddns.service"
TIMER_NAME="cloudflare-ddns.timer"

echo "[*] Installing Cloudflare-DDNS to ${INSTALL_DIR}"
sudo mkdir -p "${INSTALL_DIR}"

echo "[*] Copying application files"
sudo rm -rf "${INSTALL_DIR}/app"
sudo mkdir -p "${INSTALL_DIR}"
sudo cp -r "${REPO_DIR}/app" "${INSTALL_DIR}/"
sudo cp "${REPO_DIR}/requirements.txt" "${INSTALL_DIR}/"
sudo cp "${REPO_DIR}/README.md" "${INSTALL_DIR}/"
sudo cp "${REPO_DIR}/README.ru.md" "${INSTALL_DIR}/"
sudo cp "${REPO_DIR}/LICENSE" "${INSTALL_DIR}/"
sudo cp "${REPO_DIR}/scripts/cloudflare-ddns" "/usr/local/bin/cloudflare-ddns"

if [[ ! -f "${INSTALL_DIR}/.env" ]]; then
  echo "[*] Creating .env from .env.example"
  sudo cp "${REPO_DIR}/.env.example" "${INSTALL_DIR}/.env"
else
  echo "[*] Keeping existing ${INSTALL_DIR}/.env"
fi

echo "[*] Creating Python virtual environment"
sudo python3 -m venv "${INSTALL_DIR}/.venv"
sudo "${INSTALL_DIR}/.venv/bin/pip" install --upgrade pip
sudo "${INSTALL_DIR}/.venv/bin/pip" install -r "${INSTALL_DIR}/requirements.txt"

echo "[*] Installing systemd units"
sudo cp "${REPO_DIR}/systemd/${SERVICE_NAME}" "/etc/systemd/system/${SERVICE_NAME}"
sudo cp "${REPO_DIR}/systemd/${TIMER_NAME}" "/etc/systemd/system/${TIMER_NAME}"

echo "[*] Reloading systemd and enabling timer"
sudo systemctl daemon-reload
sudo systemctl enable --now "${TIMER_NAME}"

echo
echo "[+] Installation completed"
echo "[!] Edit config: sudo nano ${INSTALL_DIR}/.env"
echo "[!] Validate config: cloudflare-ddns validate"
echo "[!] Dry run: cloudflare-ddns check"
echo "[!] One run: cloudflare-ddns once"
echo "[!] Daemon mode: sudo systemctl start ${SERVICE_NAME}"
echo "[!] Stop: cloudflare-ddns stop"
echo "[!] Restart: cloudflare-ddns restart"
echo "[!] Logs: sudo journalctl -u ${SERVICE_NAME} -n 100 --no-pager"
