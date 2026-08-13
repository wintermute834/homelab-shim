# Shim

A lightweight process that collects this machine's system state and serves it as one
JSON payload conforming to the `Snapshot` contract (`schema.py`). It does **not** talk
to the LLM and keeps **no** history - it only reports current state. Runs unmodified on
rivendell, the Mac Mini, and the Windows dev box.

## Setup

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
# rivendell only, for GPU metrics:
pip install pynvml
```

## Run

```bash
uvicorn shim.server:app --host 0.0.0.0 --port 8765
```

Bind to the LAN only. Do not expose to the internet.

## Endpoints

| Method | Path      | Purpose                                     |
|--------|-----------|---------------------------------------------|
| GET    | `/state`  | Full system snapshot (the contract payload) |
| GET    | `/health` | Cheap liveness check for the polling loop   |

## Test

```bash
curl -s http://localhost:8765/state | python3 -m json.tool
```
