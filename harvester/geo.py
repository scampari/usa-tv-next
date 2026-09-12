"""Locate stream hosts: resolve each to an address, then look up its country
and owning network through ip-api.

Lookups are cached in data/host_geo.json and sent in batches, because the free
service allows 45 requests a minute with up to 100 addresses in each.
"""
from __future__ import annotations

import asyncio
import json
import socket
from collections.abc import Iterable
from concurrent.futures import ThreadPoolExecutor
from urllib.parse import urlparse

import aiohttp

from harvester.config import DATA_DIR

CACHE_PATH = DATA_DIR / "host_geo.json"
BATCH_URL = "http://ip-api.com/batch?fields=status,countryCode,as,query"
BATCH_SIZE = 100
BATCH_PAUSE = 2.0
RESOLVE_CONCURRENCY = 32
RESOLVE_TIMEOUT = 10.0

_RESOLVE_EXECUTOR = ThreadPoolExecutor(max_workers=RESOLVE_CONCURRENCY, thread_name_prefix="geo")

# Networks that serve content worldwide from whichever edge is nearest, so
# their country describes the viewer's location rather than the broadcaster's.
CDN_NETWORKS = (
    "cloudflare", "akamai", "amazon", "aws", "fastly", "google", "microsoft",
    "azure", "limelight", "edgecast", "stackpath", "cdn77", "bunny", "level 3",
    "lumen", "cogent", "gcore", "verizon", "highwinds", "incapsula", "ovh",
    "hetzner", "digitalocean", "linode", "vultr", "leaseweb", "cloudfront",
)


def is_cdn(network: str | None) -> bool:
    """True when an address belongs to a content delivery network."""
    text = (network or "").lower()
    return any(name in text for name in CDN_NETWORKS)


def host_of(url: str) -> str:
    try:
        return urlparse(url).hostname or ""
    except ValueError:
        return ""


def load_cache() -> dict[str, dict]:
    if CACHE_PATH.exists():
        try:
            return json.loads(CACHE_PATH.read_text())
        except json.JSONDecodeError:
            return {}
    return {}


async def _resolve(host: str, sem: asyncio.Semaphore) -> tuple[str, str]:
    loop = asyncio.get_running_loop()
    async with sem:
        try:
            address = await asyncio.wait_for(
                loop.run_in_executor(_RESOLVE_EXECUTOR, socket.gethostbyname, host),
                timeout=RESOLVE_TIMEOUT,
            )
            return host, address
        except (OSError, asyncio.TimeoutError):
            return host, ""


async def _lookup(addresses: list[str]) -> dict[str, dict]:
    located: dict[str, dict] = {}
    async with aiohttp.ClientSession() as session:
        for start in range(0, len(addresses), BATCH_SIZE):
            batch = addresses[start:start + BATCH_SIZE]
            try:
                async with session.post(BATCH_URL, json=batch, timeout=aiohttp.ClientTimeout(total=30)) as response:
                    payload = await response.json(content_type=None)
            except (aiohttp.ClientError, asyncio.TimeoutError, json.JSONDecodeError):
                continue
            for entry in payload or []:
                if entry.get("status") == "success":
                    located[entry["query"]] = {
                        "country": entry.get("countryCode", ""),
                        "network": entry.get("as", ""),
                    }
            if start + BATCH_SIZE < len(addresses):
                await asyncio.sleep(BATCH_PAUSE)
    return located


async def locate_hosts(hosts: Iterable[str], use_cache: bool = True) -> dict[str, dict]:
    """Return {host: {"address", "country", "network"}} for every host given.

    Hosts that cannot be resolved or located are returned with empty values, so
    callers can tell "unknown" apart from "known to be somewhere else".
    """
    wanted = {host for host in hosts if host}
    cache = load_cache() if use_cache else {}
    missing = sorted(wanted - set(cache))

    if missing:
        sem = asyncio.Semaphore(RESOLVE_CONCURRENCY)
        resolved = dict(await asyncio.gather(*[_resolve(host, sem) for host in missing]))
        located = await _lookup(sorted({address for address in resolved.values() if address}))
        for host in missing:
            address = resolved.get(host, "")
            details = located.get(address, {})
            cache[host] = {
                "address": address,
                "country": details.get("country", ""),
                "network": details.get("network", ""),
            }
        CACHE_PATH.parent.mkdir(parents=True, exist_ok=True)
        CACHE_PATH.write_text(json.dumps(cache, separators=(",", ":"), sort_keys=True))

    return {host: cache.get(host, {"address": "", "country": "", "network": ""}) for host in wanted}
