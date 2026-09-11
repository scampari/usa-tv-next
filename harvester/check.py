"""Check addon data before publishing.

Fails when the catalog, genre slices, meta and stream files disagree, or when
the number of channels with a working stream falls sharply against a git
revision. The drop guard stops a run that could not reach stream hosts (for
example a blocked network) from publishing an addon with nothing to play.
"""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import click

BASE_DIR = Path(__file__).resolve().parent.parent
CATALOG_PATH = BASE_DIR / "catalog" / "tv" / "all.json"
GENRE_DIR = BASE_DIR / "catalog" / "tv" / "all"
META_DIR = BASE_DIR / "meta" / "tv"
STREAM_DIR = BASE_DIR / "stream" / "tv"


def _channels_with_streams(metas: list[dict]) -> int:
    return sum(1 for ch in metas if ch.get("streams"))


def consistency_problems() -> list[str]:
    problems: list[str] = []
    catalog = json.loads(CATALOG_PATH.read_text())["metas"]
    by_id = {ch["id"]: ch for ch in catalog}

    in_genres: set[str] = set()
    for genre_file in GENRE_DIR.glob("genre=*.json"):
        genre = genre_file.stem.split("=", 1)[1]
        for ch in json.loads(genre_file.read_text())["metas"]:
            in_genres.add(ch["id"])
            if ch != by_id.get(ch["id"]):
                problems.append(f"{genre_file.name}: {ch['id']} differs from catalog")
            if ch.get("genre") != genre:
                problems.append(f"{genre_file.name}: {ch['id']} has genre {ch.get('genre')}")

    missing = {i for i, ch in by_id.items() if ch.get("genre")} - in_genres
    if missing:
        problems.append(f"{len(missing)} catalog channels missing from genre files")

    for channel_id, ch in by_id.items():
        meta_file = META_DIR / f"{channel_id}.json"
        if meta_file.exists() and json.loads(meta_file.read_text())["meta"] != ch:
            problems.append(f"meta {channel_id} differs from catalog")
        stream_file = STREAM_DIR / f"{channel_id}.json"
        if not stream_file.exists():
            problems.append(f"stream file missing for {channel_id}")
        elif json.loads(stream_file.read_text())["streams"] != ch.get("streams", []):
            problems.append(f"stream {channel_id} differs from catalog")

    return problems


def baseline_count(ref: str) -> int:
    blob = subprocess.run(
        ["git", "show", f"{ref}:catalog/tv/all.json"],
        cwd=BASE_DIR, capture_output=True, text=True, check=True,
    ).stdout
    return _channels_with_streams(json.loads(blob)["metas"])


@click.command()
@click.option("--baseline-ref", default=None, help="Git revision to compare working channel count against")
@click.option("--max-drop", type=float, default=0.15, show_default=True, help="Largest allowed fractional drop")
def main(baseline_ref: str | None, max_drop: float) -> None:
    problems = consistency_problems()
    current = _channels_with_streams(json.loads(CATALOG_PATH.read_text())["metas"])
    click.echo(f"channels with streams: {current}")

    if baseline_ref:
        before = baseline_count(baseline_ref)
        click.echo(f"channels with streams at {baseline_ref}: {before}")
        if before and current < before * (1 - max_drop):
            problems.append(f"working channels fell from {before} to {current}, more than {max_drop:.0%}")

    for problem in problems[:20]:
        click.echo(problem, err=True)
    if problems:
        click.echo(f"{len(problems)} problems found", err=True)
        sys.exit(1)
    click.echo("all checks passed")


if __name__ == "__main__":
    main()
