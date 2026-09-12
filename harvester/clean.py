"""Remove streams that do not belong in a US TV addon and label the rest with
where they broadcast from.

Runs over what is already published, so a rule added today also clears out
links earlier runs let through.
"""
from __future__ import annotations

import asyncio
import collections

from rich.console import Console

from harvester.filters import broadcast_country, describe, last_resort, rejection
from harvester.geo import host_of, locate_hosts
from harvester.publish import load_catalog, write_addon
from harvester.state import load_streams

console = Console()

AUDIO_LABEL = "Audio"


async def _clean(dry_run: bool) -> dict:
    catalog = load_catalog()
    channels = catalog["metas"]

    records = {stream["url"]: stream for stream in load_streams() or []}
    console.print(f"[bold]Harvested records available:[/] {len(records)}")

    hosts = {host_of(stream["url"]) for channel in channels for stream in channel.get("streams", [])}
    host_geo = await locate_hosts(hosts)
    console.print(f"[bold]Located {sum(1 for v in host_geo.values() if v.get('country'))} of {len(hosts)} hosts[/]")

    reasons: collections.Counter[str] = collections.Counter()
    countries: collections.Counter[str] = collections.Counter()
    removed = 0
    labelled = 0

    rescued = 0

    def label(stream: dict) -> dict:
        nonlocal labelled
        country = broadcast_country(stream["url"], records.get(stream["url"]), host_geo)
        countries[country or "unknown"] += 1
        description = describe(stream.get("description", ""), country)
        if description != stream.get("description"):
            labelled += 1
        stream["description"] = description
        return stream

    for channel in channels:
        kept: list[dict] = []
        dropped: list[tuple[dict, str]] = []
        for stream in channel.get("streams", []):
            reason = rejection(
                stream["url"], records.get(stream["url"]), host_geo, stream.get("name") == AUDIO_LABEL
            )
            if reason:
                dropped.append((stream, reason))
            else:
                kept.append(stream)

        if not kept:
            sole_source = last_resort(dropped)
            rescued_ids = {id(stream) for stream in sole_source}
            dropped = [(s, r) for s, r in dropped if id(s) not in rescued_ids]
            kept = sole_source
            rescued += len(sole_source)

        for _, reason in dropped:
            reasons[reason.split(" says ")[0].split(" only serves ")[0]] += 1
        removed += len(dropped)
        channel["streams"] = [label(stream) for stream in kept]

    playable = sum(1 for channel in channels if channel["streams"])
    console.print(f"[bold]Removed {removed} streams[/], relabelled {labelled}, kept {rescued} as a channel's only source")
    for reason, count in reasons.most_common():
        console.print(f"  {count:5} {reason}")
    console.print(f"[bold]Remaining by country:[/] {dict(countries.most_common(8))}")
    console.print(f"[bold]Channels with a stream:[/] {playable} of {len(channels)}")

    if dry_run:
        console.print("[yellow]Dry run — no files modified[/]")
    else:
        write_addon(catalog)

    return {"removed": removed, "labelled": labelled, "rescued": rescued, "channels": playable}


def clean(dry_run: bool = False) -> dict:
    return asyncio.run(_clean(dry_run))
