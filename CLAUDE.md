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
uv run python -m harvester.inject
```

`run` performs harvest, test and report; injection is separate and modifies the
published catalog. `sources.yaml` defines upstreams. `harvester/` owns parsing,
URL deduplication, DNS filtering, ffprobe checks and channel matching.
`data/` contains resumable state/results and remains gitignored.

## Data invariants

- Keep `catalog/tv/all.json`, genre slices, `meta/tv/` and `stream/tv/` consistent
  when adding channels or injecting streams. Inspect the actual files for counts.
- Match normalized channel names exactly or at a word boundary; preserve the
  non-US exclusions and the preference for a more-specific catalog channel.
- Stream quality comes from probe results. Excess ffprobe concurrency can create
  false failures; do not increase it without measuring on the test host.
- `manifest.json` identifies the addon; `public/` holds its images.

## Deployment

Pushing catalog/meta/stream changes to `yowmamasita/usa-tv-next` publishes the
files Stremio clients fetch. Validate changed JSON and exercise affected streams
before pushing. Documentation-only changes do not alter addon data.
