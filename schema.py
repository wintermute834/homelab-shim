"""
Structured data contract for shim payloads.

Every machine returns the same top-level structure. Fields that don't apply to a
machine (e.g. `gpu` on the Mac Mini) are returned as None, never omitted, so the
schema stays consistent across the fleet. See project-homelab-assistant.md.
"""

from pydantic import BaseModel



__all__ = (
    "Cpu",
    "Memory",
    "Disk",
    "Gpu",
    "Network",
    "Model",
    "LlamaCppService",
    "Services",
    "Snapshot"
)



class Cpu(BaseModel):
    core_count: int
    load_percent: float
    load_percent_avg_1m: float | None  # None on platforms without load average (Windows)


class Memory(BaseModel):
    total_gb: float
    used_gb: float
    used_percent: float


class Disk(BaseModel):
    mount: str
    total_gb: float
    used_gb: float
    used_percent: float


class Gpu(BaseModel):
    name: str
    memory_total_mb: int
    memory_used_mb: int
    utilization_percent: int | None
    temperature_c: int | None


class Network(BaseModel):
    interfaces: list[str]
    reachable: bool


class Model(BaseModel):
    name: str
    status: str  # unloaded, loading, loaded, sleeping
    input_modalities: list[str]


class LlamaCppService(BaseModel):
    running: bool
    models: list[Model]


class Services(BaseModel):
    llama_cpp: LlamaCppService | None = None


class Snapshot(BaseModel):
    hostname: str
    utc_timestamp: str  # sortable format YYYY-MM-DD HH:MM:SS
    cpu: Cpu            #            e.g. 2026-08-12 00:23:12
    memory: Memory
    disk: list[Disk]
    gpu: Gpu | None
    network: Network
    services: Services
    uptime_hours: float
