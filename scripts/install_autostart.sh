#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
SYSTEMD_USER_DIR="$HOME/.config/systemd/user"

mkdir -p "$SYSTEMD_USER_DIR"

cat > "$SYSTEMD_USER_DIR/dsa-complexity-web.service" <<EOF
[Unit]
Description=DSA Complexity Web App
After=network.target

[Service]
Type=simple
WorkingDirectory=$ROOT_DIR
ExecStart=/usr/bin/env python3 $ROOT_DIR/web_app/server.py
Restart=always
RestartSec=2

[Install]
WantedBy=default.target
EOF

cat > "$SYSTEMD_USER_DIR/dsa-visualizer-web.service" <<EOF
[Unit]
Description=DSA Visualizer Web App
After=network.target

[Service]
Type=simple
WorkingDirectory=$ROOT_DIR
ExecStart=/usr/bin/env python3 $ROOT_DIR/visualizer_app/server.py
Restart=always
RestartSec=2

[Install]
WantedBy=default.target
EOF

systemctl --user daemon-reload
systemctl --user enable --now dsa-complexity-web.service
systemctl --user enable --now dsa-visualizer-web.service

echo "Autostart enabled."
echo "Use kill switch: systemctl --user stop dsa-complexity-web dsa-visualizer-web"
echo "Status: systemctl --user status dsa-complexity-web dsa-visualizer-web"
