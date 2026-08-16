# Shim

A lightweight process that collects this machine's system state and serves it as one
JSON payload conforming to the `Snapshot` contract (`schema.py`). Runs unmodified on
rivendell, the Mac Mini, and the Windows dev box.

## Setup

Use `uv` for easy python version and package management

```bash
git clone git@github.com:wintermute834/homelab-shim.git
uv venv
source .venv/bin/activate
uv pip install -r requirements.txt
# rivendell only, for GPU metrics:
uv pip install pynvml
```

## Run

```bash
uvicorn server:app --host 0.0.0.0 --port 8765
```

Bind to the LAN only. Do not expose to the internet.

## Endpoints

| Method | Path      | Purpose                                     |
|--------|-----------|---------------------------------------------|
| GET    | `/health` | Cheap liveness check for the polling loop   |
| GET    | `/state`  | Full system snapshot (the contract payload) |

## Test

```bash
curl -s http://localhost:8765/state | python3 -m json.tool
```
