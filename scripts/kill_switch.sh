#!/usr/bin/env bash
set -euo pipefail

# Kill switch that stops both apps no matter how they were started.
"$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/stop_servers.sh" || true
systemctl --user stop dsa-complexity-web.service dsa-visualizer-web.service 2>/dev/null || true

echo "Kill switch executed: both app servers stopped if they were running."
