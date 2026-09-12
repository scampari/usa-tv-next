# USA TV Next

Static Stremio addon for US IPTV channels. GitHub raw URLs serve the JSON;
there is no application server. Follow the parent workspace's Git and testing rules.

## Harvester

Python 3.10+ managed with `uv`; stream verification requires `ffprobe`.
Run tests on zen, with concurrency sized for the host.

```bash
uv run python -m harvester harvest
uv run python -m harvester test --limit 100
uv run python -m harvester report
uv run python -m harvester run
uv run python -m harvester prune
uv run python -m harvester clean --dry-run
uv run python -m harvester.check --baseline-ref HEAD
uv run python -m harvester.inject
```

`run` performs harvest, test, inject and report; injection is also available on
its own and modifies the published catalog.
A harvest yields about 168k streams and under 2% match a catalog channel, so
`run` tests only those matches; `--all-streams` tests everything.
`clean` drops audio-only and non-US streams and labels the rest, and `check`
refuses to publish inconsistent data or a sharp fall in playable channels.
`sources.yaml` defines upstreams. `harvester/` owns parsing, URL deduplication,
DNS filtering, ffprobe checks, channel matching, host location and publishing.
`data/` contains resumable state/results and remains gitignored.

## Data invariants

- The catalog is the source of truth and `publish.write_addon` writes every file
  derived from it. Never write genre slices, `meta/tv/` or `stream/tv/` by hand,
  or they drift apart again. Inspect the actual files for counts.
- A stream's description carries the country it broadcasts from before its source
  tag, as in `US · HV:CONTENT`. Evidence order is the stream's own metadata, then
  single-country providers, then the serving address, ignoring CDN edges.
- Streams from outside the US are dropped only when the channel keeps another
  stream; otherwise they stay, labelled, so the channel remains playable.
- Match normalized channel names exactly or at a word boundary; preserve the
  non-US exclusions and the preference for a more-specific catalog channel.
- Stream quality comes from probe results. Excess ffprobe concurrency can create
  false failures; do not increase it without measuring on the test host.
- `manifest.json` identifies the addon; `public/` holds its images.

## Deployment

This fork publishes from `scampari/usa-tv-next`; upstream is
`yowmamasita/usa-tv-next`.
Pushing catalog/meta/stream changes publishes the files Stremio clients fetch.
`.github/workflows/daily-update.yml` runs harvest, test, inject, prune, clean and
check every day and commits the result, so avoid pushing while a run is active or
its own push fails.
Validate changed JSON and exercise affected streams before pushing.
Documentation-only changes do not alter addon data.
