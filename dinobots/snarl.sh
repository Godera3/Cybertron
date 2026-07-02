#!/usr/bin/env bash
# Snarl — clear temp space (older than 24h, .tmp, .cache)
set -euo pipefail
b4=$(du -s /tmp 2>/dev/null | awk '{print $1}')
find /tmp -type f \( -name '*.tmp' -o -name '*.cache' \) -atime +0 -delete 2>/dev/null || true
after=$(du -s /tmp 2>/dev/null | awk '{print $1}')
freed=$(( (b4 - after) / 1024 ))
echo "snarl: freed ~${freed}M in /tmp"
