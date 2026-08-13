"""
Homelab assistant shim - collects local system state as a structured snapshot.
"""

from typing import Optional

import httpx

from .schema import Snapshot



def get_shim(url: str = "http://localhost:8765") -> Optional[Snapshot]:
    try:
        response = httpx.get(f"{url}/state")
        response.raise_for_status()

        return Snapshot(**response.json())

    except httpx.HTTPError:
        return None
