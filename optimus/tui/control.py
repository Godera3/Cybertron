"""Socket client — asks optimusd to perform whitelisted privileged actions."""
from __future__ import annotations
import json, socket
from cyblib import paths


def send_command(line: str, timeout: float = 3.0) -> dict:
    try:
        with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as s:
            s.settimeout(timeout)
            s.connect(str(paths.SOCK))
            s.sendall(line.encode())
            data = s.recv(4096).decode("utf-8", "replace")
        return json.loads(data)
    except (OSError, json.JSONDecodeError) as e:
        return {"ok": False, "error": f"optimusd unreachable: {e}"}
