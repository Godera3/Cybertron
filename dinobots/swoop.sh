#!/usr/bin/env bash
# Swoop — proactive health scan: disk, mem, inodes
set -euo pipefail
issues=""
# Check root inodes
inode_pct=$(df -i / --output=pcent 2>/dev/null | tail -1 | tr -d ' %')
if [ "${inode_pct:-0}" -gt 90 ]; then
    issues="${issues} inodes=${inode_pct}%"
fi
# Check root disk
disk_pct=$(df / --output=pcent 2>/dev/null | tail -1 | tr -d ' %')
if [ "${disk_pct:-0}" -gt 85 ]; then
    issues="${issues} disk=${disk_pct}%"
fi
# OOM risk (swap + mem)
swap_used=$(free -m | awk '/Swap:/ {print $3}')
if [ "${swap_used:-0}" -gt 1024 ]; then
    issues="${issues} swap=${swap_used}M"
fi
if [ -n "$issues" ]; then
    echo "swoop: issues found:${issues}"
else
    echo "swoop: all clear"
fi
