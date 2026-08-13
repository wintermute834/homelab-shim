"""
Collect system state and shape it into the Snapshot contract.

Every collector is defensive: hardware or services that aren't present on a given
machine yield None rather than raising, so the same shim binary runs unmodified on
rivendell (Linux + NVIDIA), the Mac Mini (no GPU), and the Windows dev box.
"""

import socket
import time
import re
from datetime import datetime, timezone

import httpx
import psutil

from schema import *



MB = 1024**2
GB = 1024**3
LLAMA_URL = "http://localhost:8080"

# Filesystem types that are virtual, in-memory, or otherwise not real storage we
# want to monitor. Reporting these pollutes the snapshot and, worse, lets a junk
# mount land at disk[0] and false-fire the disk-usage alert rule.
_PSEUDO_FSTYPES = {
    "squashfs",
    "overlay",
    "tmpfs",
    "devtmpfs",
    "ramfs",
    "proc",
    "sysfs",
    "cgroup",
    "cgroup2",
    "fuse.snapfuse",
    "9p",  # WSL host-mount transport
}

# Mount-point prefixes to skip outright (WSL/Docker plumbing, snap loop mounts).
_PSEUDO_MOUNT_PREFIXES = (
    "/mnt/wsl",
    "/snap",
    "/var/lib/docker",
    "/boot", # boot partitions arent necessary

    # mac garbage
    "/System/Volumes/Update/", # system updates
    "/System/Volumes/Hardware",
    "/System/Volumes/iSCPreboot", # boot
    "/System/Volumes/xarts"
)


def _is_real_disk(mountpoint: str, fstype: str) -> bool:
    if fstype.lower() in _PSEUDO_FSTYPES:
        return False

    if mountpoint.startswith(_PSEUDO_MOUNT_PREFIXES):
        return False

    return True


def hostname() -> str:
    hostname = socket.gethostname()

    if hostname.endswith(".local"):
        return hostname[:-6]

    else:
        return hostname


def utc_now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")


def collect_cpu() -> Cpu:
    # interval=None returns the load since the previous call; the daemon polls on a
    # schedule so successive samples are meaningful without blocking here.
    load = psutil.cpu_percent(interval=None)
    core_count = psutil.cpu_count(logical=True)

    try:
        load_avg_1m = psutil.getloadavg()[0] * 100 / (core_count or 1) # load is for all cores combined

    except (AttributeError, OSError):
        load_avg_1m = None  # not available on stock Windows

    return Cpu(
        core_count = core_count or 0,
        load_percent = round(load, 1),
        load_percent_avg_1m = round(load_avg_1m, 1) if load_avg_1m is not None else None,
    )


def collect_memory() -> Memory:
    vm = psutil.virtual_memory()

    return Memory(
        total_gb = round(vm.total / GB, 1),
        used_gb = round(vm.used / GB, 1),
        used_percent = round(vm.percent, 1),
    )


def collect_disk() -> list[Disk]:
    disks: dict[str, tuple[str, int, int, int]] = {} # {"device": ("mount", total_sum, used_sum, num_parts)}

    for part in psutil.disk_partitions(all=False):
        if not _is_real_disk(part.mountpoint, part.fstype): continue

        if part.device.startswith("/dev/disk"): # mac splits disks weirdly, have to combine their allocated space
            result = re.search("(/dev/disk[0-9]+)", part.device)

            if result is None: continue

            device = result.group()

        else:
            device = part.mountpoint

        try:
            usage = psutil.disk_usage(part.mountpoint)

        except (PermissionError, OSError): continue  # e.g. an unreadable or disconnected mount

        if device in disks:
            disks[device] = (
                min(disks[device][0], part.mountpoint, key=len),
                disks[device][1] + usage.total,
                disks[device][2] + usage.used,
                disks[device][3] + 1
            )
        
        else:
            disks[device] = (part.mountpoint, usage.total, usage.used, 1)

    return [
        Disk(
            mount = disk[0],
            total_gb = round(disk[1] / disk[3] / GB, 1), # divide by total partitions
            used_gb = round(disk[2] / GB, 1),
            used_percent = round(disk[2] / disk[1] * disk[3] * 100, 1)
        )
        for _, disk in disks.items()
    ]


def collect_gpu() -> Gpu | None:
    """NVIDIA GPU statistics via NVML. Returns None when no NVIDIA GPU or driver is present."""

    try:
        import pynvml # type: ignore
    except ImportError:
        return None

    try:
        pynvml.nvmlInit()
    except Exception:
        return None

    try:
        handle = pynvml.nvmlDeviceGetHandleByIndex(0)
        name = pynvml.nvmlDeviceGetName(handle)

        if isinstance(name, bytes):
            name = name.decode()

        mem = pynvml.nvmlDeviceGetMemoryInfo(handle)

        try:
            util = pynvml.nvmlDeviceGetUtilizationRates(handle).gpu
        except Exception:
            util = None

        try:
            temp = pynvml.nvmlDeviceGetTemperature(handle, pynvml.NVML_TEMPERATURE_GPU)
        except Exception:
            temp = None

        return Gpu(
            name = name,
            memory_total_mb = mem.total // MB,
            memory_used_mb = mem.used // MB,
            utilization_percent = util,
            temperature_c = temp,
        )

    except Exception:
        return None

    finally:
        try:
            pynvml.nvmlShutdown()
        except Exception:
            pass


def collect_network() -> Network:
    interfaces = [name for name in psutil.net_if_stats() if name != "lo"]

    return Network(
        interfaces = interfaces,
        reachable = True
    )


def collect_llama() -> LlamaCppService | None:
    """
    Query the local llama.cpp API for running status and models.

    `/v1/models` lists every linked model its state.

    Returns None on machines that don't run llama.cpp (Mac Mini, Windows box) so the
    field reads as "not applicable" rather than "down".
    """

    try:
        '''
        localhost:port/v1/models Format:

        {"data": [
            {
                "id": "Qwen3.5-4B",
                "path": "~/llama/models/Qwen3.5-4B-MTP-Q4-K-M.gguf",
                "status": {
                    "value": "loaded",
                    "args": ["llama-server", "-ctx", "4096"]
                },
                "architecture": {
                    "input_modalities": [
                        "text",
                        "image"
                    ],
                    "output_modalities": [
                        "text"
                    ]
                }
            },
            ...
        ]}
        '''
        tags_resp = httpx.get(f"{LLAMA_URL}/v1/models", timeout=2.0)
        tags_resp.raise_for_status()

    except httpx.HTTPError:
        return None  # llama.cpp not running or not installed on this machine

    data: list[dict[str, str | dict[str, str | list[str]]]] = tags_resp.json().get("data", [])

    models = [
        Model(
            name = model.get("id", "NULL"),                                              # type: ignore
            status = model.get("status", {}).get("value", "NULL"),                       # type: ignore
            input_modalities = model.get("architecture", {}).get("input_modalities", []) # type: ignore
        )
        for model in data if model.get("id", "default") != "default"
    ]

    return LlamaCppService(
        running = True,
        models = models
    )


def collect_snapshot() -> Snapshot:
    llama_cpp = collect_llama()

    return Snapshot(
        hostname = hostname(),
        utc_timestamp = utc_now(),
        cpu = collect_cpu(),
        memory = collect_memory(),
        disk = collect_disk(),
        gpu = collect_gpu(),
        network = collect_network(),
        services = Services(llama_cpp=llama_cpp),
        uptime_hours = round((time.time() - psutil.boot_time()) / 3600, 1),
    )
