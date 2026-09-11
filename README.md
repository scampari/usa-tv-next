# USA TV Next

Live US TV channels across 10 genres: Sports, Entertainment, News, Premium, Kids, Lifestyle, Documentaries, Local, Music, Latino.

Static Stremio addon hosted entirely on GitHub using raw URLs, with no server required.

## Daily updates

A GitHub Actions workflow (`.github/workflows/daily-update.yml`) runs every day at 09:17 UTC.
It finds new streams, tests them with ffprobe, adds the working ones and removes dead ones.
It only publishes when `python -m harvester.check` passes: all data files must agree, and working channels must not drop more than 15% from the previous commit.
Run it by hand from the Actions tab with "Run workflow".

## Install

```
stremio://raw.githubusercontent.com/scampari/usa-tv-next/main/manifest.json
```

[Install via Stremio Web](https://web.stremio.com/#/addons?addon=https%3A%2F%2Fraw.githubusercontent.com%2Fscampari%2Fusa-tv-next%2Fmain%2Fmanifest.json)

## Routes

| Stremio Resource | URL Path |
|---|---|
| Manifest | `/manifest.json` |
| Catalog | `/catalog/tv/all.json` |
| Catalog (genre) | `/catalog/tv/all/genre={Genre}.json` |
| Meta | `/meta/tv/{id}.json` |
| Stream | `/stream/tv/{id}.json` |

## Structure

```
manifest.json
catalog/tv/all.json
catalog/tv/all/genre={Genre}.json
meta/tv/ustv-{uuid}.json
stream/tv/ustv-{uuid}.json
public/logo.png
public/background.jpg
public/logos/usa/{channel}.png
public/posters/usa/{channel}.png
```
