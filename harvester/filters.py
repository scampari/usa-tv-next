"""Decide which streams belong in a US TV addon, and label where each one
broadcasts from.

Three independent signals say a stream is not the US channel it claims to be,
and each catches cases the others miss:

* the harvested record names a country, as in ``ABCTV.au@NSW`` or group
  ``Australia``;
* the host belongs to a provider that only serves another country, which is how
  Australian ABC radio arrived under the US ABC with no country in its record;
* the address sits in another country on a network that is not a CDN. A CDN
  edge says where the viewer is, so it is never treated as evidence.
"""
from __future__ import annotations

import re

from harvester.geo import host_of, is_cdn

HOME_COUNTRY = "US"
AUDIO_ONLY = "audio only"

# Providers that only carry another country's channels.
FOREIGN_PROVIDERS = {
    "mjh.nz": "AU",
    "aynaott.com": "BD",
    "iptvbd.live": "BD",
    "arcapuglia.it": "IT",
}

# Country names as they appear in playlist group titles.
_GROUP_COUNTRIES = {
    "albania": "AL", "argentina": "AR", "australia": "AU", "austria": "AT",
    "bangladesh": "BD", "belgium": "BE", "brasil": "BR", "brazil": "BR",
    "canada": "CA", "chile": "CL", "china": "CN", "colombia": "CO",
    "czech": "CZ", "denmark": "DK", "ecuador": "EC", "egypt": "EG",
    "espana": "ES", "españa": "ES", "finland": "FI", "france": "FR",
    "germany": "DE", "greece": "GR", "guatemala": "GT", "honduras": "HN",
    "hungary": "HU", "india": "IN", "indonesia": "ID", "iran": "IR",
    "iraq": "IQ", "ireland": "IE", "israel": "IL", "italia": "IT",
    "italy": "IT", "japan": "JP", "korea": "KR", "latvia": "LV",
    "lithuania": "LT", "malaysia": "MY", "mexico": "MX", "morocco": "MA",
    "netherlands": "NL", "new zealand": "NZ", "norway": "NO", "pakistan": "PK",
    "paraguay": "PY", "peru": "PE", "philippines": "PH", "poland": "PL",
    "portugal": "PT", "romania": "RO", "russia": "RU", "saudi": "SA",
    "serbia": "RS", "singapore": "SG", "spain": "ES", "sweden": "SE",
    "switzerland": "CH", "thailand": "TH", "turkey": "TR", "turkiye": "TR",
    "ukraine": "UA", "united kingdom": "GB", "uruguay": "UY", "uzbekistan": "UZ",
    "venezuela": "VE", "vietnam": "VN",
}

_TVG_COUNTRY = re.compile(r"\.([a-z]{2})(?:@|$)")

# Country codes used in tvg-id that are not ISO two-letter codes.
_TVG_ALIASES = {"uk": "GB"}


def record_country(record: dict | None) -> str:
    """Country named by a harvested stream's own metadata, or an empty string."""
    if not record:
        return ""
    match = _TVG_COUNTRY.search((record.get("tvg_id") or "").lower())
    if match:
        code = match.group(1)
        return _TVG_ALIASES.get(code, code.upper())
    group = (record.get("group") or "").lower()
    for name, code in _GROUP_COUNTRIES.items():
        if name in group:
            return code
    return ""


def provider_country(url: str) -> str:
    """Country of a provider that only serves one country, or an empty string."""
    host = host_of(url).lower()
    for domain, country in FOREIGN_PROVIDERS.items():
        if host == domain or host.endswith("." + domain):
            return country
    return ""


def server_country(url: str, host_geo: dict[str, dict]) -> str:
    """Country of the serving address, ignoring CDN edges, or an empty string."""
    details = host_geo.get(host_of(url)) or {}
    if is_cdn(details.get("network")):
        return ""
    return details.get("country", "")


def broadcast_country(url: str, record: dict | None, host_geo: dict[str, dict]) -> str:
    """Best evidence of where a stream broadcasts from, or an empty string.

    The stream's own metadata wins, then a single-country provider, then the
    serving address.
    """
    return record_country(record) or provider_country(url) or server_country(url, host_geo)


def _source_tag(description: str) -> str:
    """Keep the source tag from a description, dropping any country already on it."""
    text = (description or "").strip()
    if "·" in text:
        text = text.split("·", 1)[1].strip()
    return text


def describe(description: str, country: str) -> str:
    """Stream description showing where it broadcasts from, then its source."""
    tag = _source_tag(description)
    if not country:
        return tag
    return f"{country} · {tag}" if tag else country


def last_resort(dropped: list[tuple[dict, str]]) -> list[dict]:
    """Streams worth keeping when a channel would otherwise have nothing.

    Broadcasting from elsewhere is a reason to prefer another stream, not a
    reason to leave a channel unplayable, so those survive as a last resort and
    keep their country label. Audio-only streams are never worth keeping.
    """
    return [stream for stream, reason in dropped if reason != AUDIO_ONLY]


def rejection(url: str, record: dict | None, host_geo: dict[str, dict], audio_only: bool) -> str:
    """Why this stream does not belong in the addon, or an empty string to keep it."""
    if audio_only:
        return AUDIO_ONLY
    country = record_country(record)
    if country and country != HOME_COUNTRY:
        return f"record says {country}"
    country = provider_country(url)
    if country and country != HOME_COUNTRY:
        return f"{host_of(url)} only serves {country}"
    country = server_country(url, host_geo)
    if country and country != HOME_COUNTRY:
        return f"served from {country}"
    return ""
