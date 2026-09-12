"""Write the addon files Stremio reads.

The catalog is the single source of truth: genre slices, meta and stream files
are all derived from it. Keeping that in one place is what stops them drifting
apart, which is how stream/tv kept serving links the catalog had already
replaced.
"""
from __future__ import annotations

import json
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
CATALOG_PATH = BASE_DIR / "catalog" / "tv" / "all.json"
GENRE_DIR = BASE_DIR / "catalog" / "tv" / "all"
META_DIR = BASE_DIR / "meta" / "tv"
STREAM_DIR = BASE_DIR / "stream" / "tv"


def load_catalog() -> dict:
    return json.loads(CATALOG_PATH.read_text())


def write_addon(catalog: dict) -> None:
    """Write the catalog and every file derived from it."""
    channels = catalog["metas"]
    CATALOG_PATH.write_text(json.dumps(catalog, separators=(",", ":")))

    genre_channels: dict[str, list] = {}
    for channel in channels:
        genre = channel.get("genre", "")
        if genre:
            genre_channels.setdefault(genre, []).append(channel)

    GENRE_DIR.mkdir(parents=True, exist_ok=True)
    for genre, members in genre_channels.items():
        genre_file = GENRE_DIR / f"genre={genre}.json"
        genre_file.write_text(json.dumps({"metas": members}, separators=(",", ":")))

    for channel in channels:
        meta_file = META_DIR / f"{channel['id']}.json"
        if meta_file.exists():
            meta_file.write_text(json.dumps({"meta": channel}, separators=(",", ":")))

        stream_file = STREAM_DIR / f"{channel['id']}.json"
        if stream_file.exists():
            stream_file.write_text(json.dumps({"streams": channel.get("streams", [])}, separators=(",", ":")))
