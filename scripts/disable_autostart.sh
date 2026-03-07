#!/usr/bin/env bash
set -euo pipefail

systemctl --user disable --now dsa-complexity-web.service dsa-visualizer-web.service || true
rm -f "$HOME/.config/systemd/user/dsa-complexity-web.service"
rm -f "$HOME/.config/systemd/user/dsa-visualizer-web.service"
systemctl --user daemon-reload

echo "Autostart disabled and service files removed."
