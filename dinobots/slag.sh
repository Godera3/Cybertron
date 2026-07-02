#!/usr/bin/env bash
# Slag — kill frozen (T) processes
set -euo pipefail
IFS=$'\n\t'
count=0
for pid in $(ps -eo stat,pid --no-headers 2>/dev/null | awk '/^T/ {print $2}'); do
    kill -9 "$pid" 2>/dev/null && ((count++)) || true
done
echo "slag: killed ${count} frozen process(es)"
