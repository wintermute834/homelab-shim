"""
Shim HTTP server.

The shim only collects and reports local state. It never talks to the LLM and holds
no history - that's the orchestrator's job. Bind to the LAN only; do not expose to
the internet.

Run:
    uvicorn server:app --host 0.0.0.0 --port 8765 --log-level debug
"""

from fastapi import FastAPI

from collectors import collect_snapshot
from schema import Snapshot



app = FastAPI(title="Homelab Shim", version="0.1.0")


@app.get("/state", response_model=Snapshot)
def state() -> Snapshot:
    """Return a fresh snapshot of this machine's current state."""
    return collect_snapshot()


@app.get("/health")
def health() -> dict[str, str]:
    """Cheap liveness check for the orchestrator's polling loop."""
    return {"status": "ok"}
