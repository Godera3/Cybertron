# Cybertron · Phase 0

Your Linux Mint system, themed as Primus/Cybertron.

**Phase 0 — Foundation + Micronus Prime (thermal & power)**

- `cyblib` — shared contract library (atomic status JSON files)
- `cyb-micronus.service` — thermal & power monitoring
- `cybertron.target` — master systemd target

### Quickstart

```bash
cd ~/Desktop/cybertron && sudo ./install.sh
```

### Verify

```bash
cat /run/cybertron/micronus.json
systemctl status cyb-micronus.service
```
