"""Inject working harvested streams into existing Stremio addon catalogs."""
from __future__ import annotations

import asyncio
import json
import re
from urllib.parse import urlparse

from harvester.filters import broadcast_country, describe
from harvester.geo import host_of, locate_hosts
from harvester.models import ParsedStream
from harvester.publish import BASE_DIR, CATALOG_PATH, write_addon
from harvester.state import load_streams

_NON_US_SUFFIXES = [
    "international", "italia", "indonesia", "finland", "arabic", "uk ",
    "canada", "brasil", "brazil", "india", "japan", "korea", "turkish",
    "turkey", "europe", "asia", "africa", "españa", "france", "french",
    "german", "deutsch", "portugal", "chinese", "russian", "australia",
    "philippines", "pakistan", "middle east", "baltia", "baltic",
    "français", "pусский", "español", " sub", " ava",
]

_NON_US_URL_PATTERNS = ["qvcuk", "tvkaista.net"]


def _normalize(name: str) -> str:
    return re.sub(r"[^a-z0-9]", "", name.lower())


def _quality_label(result: dict) -> str:
    res = (result.get("codecs") or {}).get("resolution", "")
    if not res:
        codec = (result.get("codecs") or {}).get("video", "")
        if not codec:
            return "Audio"
        return "SD"
    w = int(res.split("x")[0]) if "x" in res else 0
    if w >= 1920:
        return "FHD"
    if w >= 1280:
        return "HD"
    if w >= 720:
        return "SD"
    return "SD"


def _source_tag(url: str) -> str:
    host = urlparse(url).hostname or ""
    parts = host.replace("www.", "").split(".")
    if len(parts) >= 2:
        return parts[0][:12].upper()
    return "HV"


def _make_stream_entry(result: dict) -> dict:
    quality = _quality_label(result)
    tag = _source_tag(result["url"])
    return {
        "url": result["url"],
        "behaviorHints": {"notWebReady": True},
        "name": quality,
        "description": f"HV:{tag}",
    }


def _match_streams(channels: list[dict], working: list[dict], catalog_norms: set[str]) -> dict[str, list[dict]]:
    """Match working streams to catalog channels. Returns {channel_id: [results]}."""
    matches: dict[str, list[dict]] = {}

    for ch in channels:
        ch_name = ch["name"]
        ch_norm = _normalize(ch_name)
        ch_lower = ch_name.lower().strip()
        ch_id = ch["id"]

        for r in working:
            stream_name = (r.get("channel_name") or "").strip()
            if not stream_name:
                continue
            s_norm = _normalize(stream_name)
            s_lower = stream_name.lower().strip()

            if s_norm == ch_norm:
                matches.setdefault(ch_id, []).append(r)
                continue

            if len(ch_norm) < 3:
                continue
            if not s_norm.startswith(ch_norm):
                continue
            if not s_lower.startswith(ch_lower):
                continue
            if len(s_lower) > len(ch_lower) and s_lower[len(ch_lower)] not in " ([-/":
                continue

            suffix = stream_name[len(ch_name):].lower()
            if any(ind in suffix for ind in _NON_US_SUFFIXES):
                continue

            url_lower = r.get("url", "").lower()
            if any(pat in url_lower for pat in _NON_US_URL_PATTERNS):
                continue

            more_specific = any(
                other != ch_norm and other.startswith(ch_norm) and s_norm.startswith(other)
                for other in catalog_norms
            )
            if more_specific:
                continue

            matches.setdefault(ch_id, []).append(r)

    return matches


def catalog_candidates(streams: list[ParsedStream]) -> list[ParsedStream]:
    """Keep only harvested streams that inject could attach to a catalog channel.

    Harvests hold well over 100k streams and under 2% match a catalog
    channel, so testing only these keeps a run to minutes instead of hours.
    """
    channels = json.loads(CATALOG_PATH.read_text())["metas"]
    catalog_norms = {_normalize(ch["name"]) for ch in channels}
    entries = [{"channel_name": s.channel_name, "url": s.url} for s in streams]
    matches = _match_streams(channels, entries, catalog_norms)
    matched_urls = {r["url"] for rs in matches.values() for r in rs}
    return [s for s in streams if s.url in matched_urls]


def inject(test_results_path: str = "data/test_results.json", host_geo: dict[str, dict] | None = None) -> dict:
    results_path = BASE_DIR / test_results_path
    results = json.loads(results_path.read_text())
    working = [r for r in results if r["status"] == "working"]

    catalog = json.loads(CATALOG_PATH.read_text())
    channels = catalog["metas"]

    catalog_norms = {_normalize(ch["name"]) for ch in channels}

    channel_matches = _match_streams(channels, working, catalog_norms)

    # A test result carries no tvg-id, so the country a stream claims for
    # itself has to come from the harvested record with the same URL.
    records = {stream["url"]: stream for stream in load_streams() or []}
    if host_geo is None:
        host_geo = asyncio.run(locate_hosts({host_of(r["url"]) for r in working}))

    stats = {"channels_updated": 0, "streams_added": 0, "streams_skipped": 0}

    for ch in channels:
        streams = ch.get("streams", [])
        existing_urls = {s["url"] for s in streams}

        new_streams = [
            r for r in channel_matches.get(ch["id"], [])
            if r["url"] not in existing_urls
        ]

        added = 0
        for r in new_streams:
            record = records.get(r["url"])
            # Where a stream broadcasts from is decided for the channel as a
            # whole, by clean, so that a channel with no US source keeps one.
            if _quality_label(r) == "Audio":
                stats["streams_skipped"] += 1
                continue
            entry = _make_stream_entry(r)
            entry["description"] = describe(entry["description"], broadcast_country(r["url"], record, host_geo))
            streams.append(entry)
            existing_urls.add(r["url"])
            added += 1

        if added:
            stats["streams_added"] += added
            stats["channels_updated"] += 1

        ch["streams"] = streams

    write_addon(catalog)

    return stats


if __name__ == "__main__":
    stats = inject()
    print(f"Channels updated: {stats['channels_updated']}")
    print(f"Streams added: {stats['streams_added']}")
