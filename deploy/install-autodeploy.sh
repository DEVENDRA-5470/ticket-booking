#!/usr/bin/env bash
set -Eeuo pipefail
APP_DIR="${APP_DIR:-$HOME/ticket-booking}"
[ -f "$APP_DIR/deploy/deploy.sh" ] || { echo "deploy.sh missing"; exit 1; }
sudo install -m 0755 "$APP_DIR/deploy/deploy.sh" /usr/local/bin/ticketflow-deploy
sudo install -m 0644 "$APP_DIR/deploy/ticketflow-autodeploy.service" /etc/systemd/system/ticketflow-autodeploy.service
sudo install -m 0644 "$APP_DIR/deploy/ticketflow-autodeploy.timer" /etc/systemd/system/ticketflow-autodeploy.timer
sudo systemctl daemon-reload
sudo systemctl enable --now ticketflow-autodeploy.timer
sudo systemctl start ticketflow-autodeploy.service
sudo systemctl status ticketflow-autodeploy.timer --no-pager
