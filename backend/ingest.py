import argparse
import calendar as calendar_module
import json
import os
import re
import time
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional

import feedparser
import requests
from dotenv import load_dotenv


def _required_url(
    arg_value: Optional[str], env_names: Iterable[str], arg_label: str
) -> str:
    """
    Get a required URL from argument or environment variables.
    Args:
        arg_value: Optional URL passed as command-line argument.
        env_names: Iterable of environment variable names to check in order.
        arg_label: Label for the command-line argument (used in error messages).
    Returns:
        The URL from argument or first matching environment variable.
    Raises:
        SystemExit: If URL is not provided and not found in any environment variable.
    """
    if arg_value:
        return arg_value
    for env_name in env_names:
        url = os.getenv(env_name)
        if url:
            return url
    names = ", ".join(env_names)
    raise SystemExit(f"Missing URL. Set {names} or pass --{arg_label}.")


def _strip_html(value: str) -> str:
    """
    Remove HTML tags from text.
    Args:
        value: Text potentially containing HTML tags.
    Returns:
        Text with HTML tags removed and stripped of whitespace.
    """
    if not value:
        return ""
    return re.sub(r"<[^>]+>", " ", value).strip()


def _normalize_key(value: str) -> str:
    """
    Normalize string to lowercase alphanumeric with spaces.
    Args:
        value: String to normalize.
    Returns:
        Lowercase string with only alphanumeric characters and spaces.
    """
    return re.sub(r"[^a-z0-9]+", " ", value.lower()).strip()


def _parse_datetime(value: Optional[Any]) -> Optional[datetime]:
    """
    Parse various datetime formats to a UTC datetime object.
    Handles datetime objects, date objects, time.struct_time, and ISO format strings.
    Args:
        value: Datetime value in various formats (datetime, date, struct_time, str, or None).
    Returns:
        Parsed datetime with UTC timezone, or None if parsing fails or input is None.
    """
    if value is None:
        return None
    if isinstance(value, datetime):
        if value.tzinfo is None:
            return value.replace(tzinfo=timezone.utc)
        return value
    if isinstance(value, date):
        return datetime.combine(value, datetime.min.time(), tzinfo=timezone.utc)
    if isinstance(value, time.struct_time):
        return datetime.fromtimestamp(calendar_module.timegm(value), tz=timezone.utc)
    if isinstance(value, str):
        cleaned = value.strip()
        if not cleaned:
            return None
        if cleaned.endswith("Z"):
            cleaned = f"{cleaned[:-1]}+00:00"
        try:
            return datetime.fromisoformat(cleaned)
        except ValueError:
            return None
    return None


def _flatten_properties(props: Dict[str, Any]) -> List[str]:
    """
    Flatten dictionary properties into formatted string list.
    Args:
        props: Dictionary with key-value pairs to flatten.
    Returns:
        List of strings formatted as "key: value" for non-None scalar values.
    """
    parts: List[str] = []
    for key, value in props.items():
        if value is None:
            continue
        if isinstance(value, (str, int, float)):
            parts.append(f"{key}: {value}")
    return parts


def _entry_value(entry: Dict[str, Any], keys: Iterable[str]) -> Optional[Any]:
    """
    Get the first non-empty value from entry using a list of keys.
    Args:
        entry: Dictionary to search.
        keys: Iterable of keys to check in order.
    Returns:
        First non-empty value found, or None if no keys have values.
    """
    for key in keys:
        value = entry.get(key)
        if value:
            return value
    return None


def _extract_from_description(description: str, label: str) -> str:
    """
    Extract value from Trumba HTML description.
    Looks for patterns like '<b>Location</b>: value<br/>' or 'Campus location: value<br/>'.
    Args:
        description: HTML description text from Trumba events.
        label: Field label to extract (e.g., 'Location', 'Campus room').
    Returns:
        Extracted value with HTML stripped, or empty string if not found.
    """
    if not description:
        return ""
    patterns = [
        rf"<b>{re.escape(label)}</b>:&nbsp;([^<]+)",
        rf"{re.escape(label)}:&nbsp;([^<]+)",
        rf"{re.escape(label)}: ([^<]+)",
    ]
    for pattern in patterns:
        match = re.search(pattern, description, re.IGNORECASE)
        if match:
            return _strip_html(match.group(1)).strip()
    return ""


def fetch_events_rss(url: str, now: datetime) -> List[Dict[str, Any]]:
    """
    Fetch events from an RSS feed and parse into document format.
    Parses event details from RSS entries including title, description, location,
    and start/end times. Filters out past events based on the provided 'now' datetime.
    Attempts to extract location from Trumba HTML descriptions.
    Args:
        url: URL of the RSS feed.
        now: Current datetime to filter out past events.
    Returns:
        List of event documents with fields: id, domain, title, summary, text,
        source_url, start, end, location.
    Raises:
        SystemExit: If RSS feed fails to parse.
    """
    feed = feedparser.parse(url)
    if getattr(feed, "bozo", False) and not feed.entries:
        error = getattr(feed, "bozo_exception", "Unknown RSS parse error")
        raise SystemExit(f"Failed to parse RSS feed: {error}")

    docs: List[Dict[str, Any]] = []

    for index, entry in enumerate(feed.entries):
        raw_description = str(entry.get("description", "")).strip()
        summary = _strip_html(str(entry.get("summary", "")).strip())
        description = _strip_html(raw_description)
        title = str(entry.get("title", "Untitled event")).strip()
        
        # Try direct location fields first, then extract from Trumba HTML description
        location = str(
            _entry_value(
                entry,
                [
                    "location",
                    "where",
                    "x_trumba_location",
                    "trumba_location",
                ],
            )
            or _extract_from_description(raw_description, "Campus location")
            or _extract_from_description(raw_description, "Campus room")
            or ""
        ).strip()

        start_dt = _parse_datetime(
            _entry_value(
                entry,
                [
                    "start",
                    "dtstart",
                    "start_date",
                    "trumba_startdate",
                    "trumba_starttime",
                    "published_parsed",
                    "updated_parsed",
                ],
            )
        )
        end_dt = _parse_datetime(
            _entry_value(
                entry,
                [
                    "end",
                    "dtend",
                    "end_date",
                    "trumba_enddate",
                    "trumba_endtime",
                ],
            )
        )

        if end_dt and end_dt < now:
            continue

        source_url = str(entry.get("link", "")).strip()
        uid = (
            str(entry.get("id", "")).strip()
            or str(entry.get("guid", "")).strip()
            or source_url
            or f"event-{index + 1}"
        )

        text_parts = [title]
        if summary:
            text_parts.append(summary)
        if description and description != summary:
            text_parts.append(description)
        if location:
            text_parts.append(f"Location: {location}")

        docs.append(
            {
                "id": f"event:{uid}",
                "domain": "event",
                "title": title,
                "summary": summary or description,
                "text": "\n".join(text_parts),
                "source_url": source_url,
                "start": start_dt.isoformat() if start_dt else None,
                "end": end_dt.isoformat() if end_dt else None,
                "location": location,
            }
        )

    return docs


def _get_property(props: Dict[str, Any], keys: Iterable[str]) -> str:
    """
    Get first non-empty property from dictionary using list of keys.
    Args:
        props: Dictionary with properties.
        keys: Iterable of keys to check in order.
    Returns:
        First non-empty property value as string, or empty string if none found.
    """
    for key in keys:
        value = props.get(key)
        if value not in (None, ""):
            return str(value).strip()
    return ""


def fetch_buildings_arcgis(base_url: str) -> List[Dict[str, Any]]:
    """
    Fetch building data from ArcGIS REST API with pagination support.
    Queries an ArcGIS feature service endpoint with pagination to retrieve
    all building records. Extracts building metadata like name, abbreviation,
    code, address, and site information.
    Args:
        base_url: Base URL of the ArcGIS feature service (without /query suffix).
    Returns:
        List of building documents with fields: id, domain, title, summary, text,
        source_url, location, abbrev, code, global_id, site, start, end.
    Raises:
        SystemExit: If API request fails or returns an error.
    """
    query_url = base_url.rstrip("/") + "/query"
    docs: List[Dict[str, Any]] = []

    offset = 0
    page_size = 1000

    while True:
        params = {
            "f": "json",
            "where": "1=1",
            "outFields": "*",
            "returnGeometry": "false",
            "resultOffset": offset,
            "resultRecordCount": page_size,
        }
        response = requests.get(query_url, params=params, timeout=30)
        response.raise_for_status()

        payload = response.json()
        if "error" in payload:
            raise SystemExit(f"ArcGIS error: {payload['error']}")

        features = payload.get("features", [])
        for index, feature in enumerate(features):
            props = feature.get("attributes", {}) or feature.get("properties", {})

            title = _get_property(
                props,
                [
                    "FacName",
                    "FACNAME",
                    "BldgName",
                    "BLDG_NAME",
                    "name",
                    "Name",
                    "title",
                    "Title",
                ],
            ) or "Unnamed building"
            abbrev = _get_property(
                props,
                [
                    "FacCode",
                    "FACCODE",
                    "BldgAbbrev",
                    "BLDG_ABRV",
                    "abbrev",
                    "Abbrev",
                    "short_name",
                    "code",
                ],
            )
            code = _get_property(
                props,
                [
                    "FacCode",
                    "FACCODE",
                    "BLDG_CODE",
                    "BldgCode",
                    "code",
                    "Code",
                ],
            )
            address = _get_property(
                props,
                [
                    "Address",
                    "ADDRESS",
                    "StreetAddr",
                    "STREET_ADDR",
                    "address",
                ],
            )
            global_id = _get_property(props, ["GlobalID", "GLOBALID", "globalid"])
            source_url = _get_property(props, ["url", "link", "URL"])

            identifier = global_id or abbrev or code or f"building-{offset + index + 1}"

            text_parts = [title]
            if abbrev:
                text_parts.append(f"Abbrev: {abbrev}")
            if code and code != abbrev:
                text_parts.append(f"Code: {code}")
            if address:
                text_parts.append(f"Address: {address}")
            site = _get_property(props, ["Site", "SITE"])
            if site:
                text_parts.append(f"Site: {site}")
            text_parts.extend(_flatten_properties(props))

            docs.append(
                {
                    "id": f"building:{identifier}",
                    "domain": "building",
                    "title": title,
                    "summary": address,
                    "text": "\n".join(text_parts),
                    "source_url": source_url,
                    "start": None,
                    "end": None,
                    "location": address,
                    "abbrev": abbrev,
                    "code": code,
                    "global_id": global_id,
                    "site": site,
                }
            )

        docs_count = len(features)
        offset += docs_count

        if not payload.get("exceededTransferLimit") or docs_count == 0:
            break

    return docs


def resolve_event_locations(
    events: List[Dict[str, Any]], buildings: List[Dict[str, Any]]
) -> None:
    """
    Resolve event location strings to building IDs and enrich event text.
    Matches event location names against building titles, abbreviations, codes,
    and sites. Creates an index for efficient matching. Modifies events in-place
    by adding resolved_building_id and resolved_building_name fields.
    Args:
        events: List of event documents to update (modified in-place).
        buildings: List of building documents to match against.
    """
    index: Dict[str, Dict[str, Any]] = {}
    for building in buildings:
        for key in (
            building.get("title"),
            building.get("abbrev"),
            building.get("code"),
            building.get("site"),
        ):
            if not key:
                continue
            normalized = _normalize_key(str(key))
            if normalized:
                index[normalized] = building

    keys_by_length = sorted(index.keys(), key=len, reverse=True)

    for event in events:
        location = event.get("location", "")
        if not location:
            continue
        normalized_location = _normalize_key(location)
        if not normalized_location:
            continue

        for key in keys_by_length:
            if key in normalized_location:
                building = index[key]
                event["resolved_building_id"] = building.get("id")
                event["resolved_building_name"] = building.get("title")
                event["text"] = f"{event.get('text', '')}\nBuilding: {building.get('title')}"
                break


def write_snapshot(docs: List[Dict[str, Any]], out_dir: Path) -> Path:
    """
    Write documents to timestamped and 'latest' snapshot JSON files.
    Creates both a dated snapshot file (e.g., snapshot_20260514.json) and
    a 'latest.json' symlink. Also writes metadata including document counts
    by domain (events, buildings).
    Args:
        docs: List of documents to write.
        out_dir: Directory where snapshot files will be written.
    Returns:
        Path to the dated snapshot file.
    """
    out_dir.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%d")
    dated_path = out_dir / f"snapshot_{timestamp}.json"
    latest_path = out_dir / "latest.json"

    for path in (dated_path, latest_path):
        with path.open("w", encoding="utf-8") as handle:
            json.dump(docs, handle, ensure_ascii=True, indent=2)

    meta = {
        "created_at": datetime.now(timezone.utc).isoformat(),
        "total_docs": len(docs),
        "events": len([doc for doc in docs if doc.get("domain") == "event"]),
        "buildings": len([doc for doc in docs if doc.get("domain") == "building"]),
        "snapshot": str(dated_path),
    }

    with (out_dir / "latest_meta.json").open("w", encoding="utf-8") as handle:
        json.dump(meta, handle, ensure_ascii=True, indent=2)

    return dated_path


def main() -> None:
    """Fetch UW events and buildings data from external sources.
    Fetches events from an RSS feed and building data from an ArcGIS API,
    resolves event locations to buildings, and writes the combined dataset
    to a snapshot file.
    Command-line arguments:
        --uw_events_rss_url: Override UW_EVENTS_RSS_URL environment variable
        --uw_buildings_arcgis_url: Override UW_BUILDINGS_ARCGIS_URL environment variable
        --out-dir: Output directory for snapshots (default: data/snapshots)
    Environment variables:
        UW_EVENTS_RSS_URL: URL of the events RSS feed (required)
        UW_BUILDINGS_ARCGIS_URL: URL of the buildings ArcGIS API (required)
    """
    load_dotenv()
    parser = argparse.ArgumentParser(description="Fetch UW events and buildings.")
    parser.add_argument(
        "--uw_events_rss_url",
        dest="events_url",
        default=None,
        help="Override UW_EVENTS_RSS_URL",
    )
    parser.add_argument(
        "--uw_buildings_arcgis_url",
        dest="buildings_url",
        default=None,
        help="Override UW_BUILDINGS_ARCGIS_URL",
    )
    parser.add_argument(
        "--out-dir",
        default="data/snapshots",
        help="Output directory for snapshot files",
    )
    args = parser.parse_args()

    events_url = _required_url(
        args.events_url, ["UW_EVENTS_RSS_URL"], "uw_events_rss_url"
    )
    buildings_url = _required_url(
        args.buildings_url, ["UW_BUILDINGS_ARCGIS_URL"], "uw_buildings_arcgis_url"
    )

    now = datetime.now(timezone.utc)
    events = fetch_events_rss(events_url, now)
    buildings = fetch_buildings_arcgis(buildings_url)
    resolve_event_locations(events, buildings)

    docs = events + buildings
    snapshot_path = write_snapshot(docs, Path(args.out_dir))

    print(f"Wrote snapshot: {snapshot_path}")
    print(f"Total docs: {len(docs)}")


if __name__ == "__main__":
    main()
