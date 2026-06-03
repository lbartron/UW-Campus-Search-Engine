import json
from pathlib import Path

DOCS_PATH = Path(__file__).resolve().parents[1] / "data" / "index" / "docs.json"


def infer_event_campus(source_url: str) -> str:
    # Events encode campus in the source URL, so the test can verify the
    # stored campus tag matches the feed that produced the document.
    url = (source_url or "").lower()
    if "tacoma" in url or "tac_" in url:
        return "Tacoma"
    if "uwb.edu" in url or "bothell" in url or "bot_campus" in url or "bot_" in url:
        return "Bothell"
    return "Seattle"


def infer_building_campus(site: str):
    # Building records expose campus through their site codes, which should
    # map cleanly to the three UW campuses used by the UI.
    normalized = (site or "").upper()
    if normalized.startswith("BOT") or "BOTHELL" in normalized:
        return "Bothell"
    if normalized.startswith("TAC") or "TACOMA" in normalized:
        return "Tacoma"
    if normalized.startswith("SEA") or "SEATTLE" in normalized:
        return "Seattle"
    return None


def load_docs():
    # The indexed docs file is the source of truth for the search API tests.
    return json.loads(DOCS_PATH.read_text(encoding="utf-8"))


def test_all_campuses_are_present_in_the_index():
    # Ensure the index contains campus tags for Seattle, Bothell, and Tacoma.
    docs = load_docs()
    campuses = {doc.get("campus") for doc in docs if doc.get("campus")}
    assert {"Seattle", "Bothell", "Tacoma"}.issubset(campuses), (
        f"Expected Seattle, Bothell, and Tacoma campus tags in the index, found {sorted(campuses)}"
    )


def test_event_campus_tags_match_source_urls():
    # Catch cases where event campus labels drift away from the source feed.
    docs = load_docs()
    mismatches = []

    for doc in docs:
        if doc.get("domain") != "event" or not doc.get("campus"):
            continue

        expected = infer_event_campus(doc.get("source_url", ""))
        if doc.get("campus") != expected:
            mismatches.append(
                {
                    "title": doc.get("title"),
                    "campus": doc.get("campus"),
                    "expected": expected,
                    "source_url": doc.get("source_url"),
                }
            )

    assert not mismatches, f"Event campus tags do not match source URLs: {mismatches[:5]}"


def test_building_site_codes_cover_all_campuses():
    # Confirm building site codes are present for all campuses so badges can
    # be derived from explicit metadata instead of guesswork.
    docs = load_docs()
    seen = set()

    for doc in docs:
        if doc.get("domain") != "building":
            continue

        campus = infer_building_campus(doc.get("site", ""))
        if campus:
            seen.add(campus)

    assert {"Seattle", "Bothell", "Tacoma"}.issubset(seen), (
        f"Expected explicit building site codes for Seattle, Bothell, and Tacoma, found {sorted(seen)}"
    )
