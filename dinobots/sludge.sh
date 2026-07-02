#!/usr/bin/env bash
# Sludge — reap zombie processes
set -euo pipefail
count=0
for pid in $(ps -eo stat,pid --no-headers 2>/dev/null | awk '/^Z/ {print $2}'); do
    # send SIGCHLD to parent to trigger reaping
    ppid=$(ps -o ppid= -p "$pid" 2>/dev/null | tr -d ' ')
    [ -n "$ppid" ] && kill -CHLD "$ppid" 2>/dev/null && ((count++)) || true
done
echo "sludge: reaped ${count} zombie(s)"
