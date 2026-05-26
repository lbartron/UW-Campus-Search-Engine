import json
import re
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional
from html import unescape

import numpy as np
from fastapi import FastAPI, HTTPException
from fastapi.staticfiles import StaticFiles
from sentence_transformers import SentenceTransformer

BASE_DIR = Path(__file__).resolve().parents[1]
INDEX_DIR = BASE_DIR / "data" / "index"
DOCS_FILE = INDEX_DIR / "docs.json"
EMB_FILE = INDEX_DIR / "embeddings.npz"
META_FILE = INDEX_DIR / "index_meta.json"
FRONTEND_DIR = BASE_DIR / "frontend"
QUERY_HINTS_FILE = BASE_DIR / "backend" / "query_hints.json"

app = FastAPI()

model: Optional[SentenceTransformer] = None
embeddings: Optional[np.ndarray] = None
docs: List[Dict[str, Any]] = []
index_meta: Dict[str, Any] = {}
index_error: Optional[str] = None
query_hints: Dict[str, Any] = {"time": {}, "topics": {}}
# Added a quick lookup map from doc id -> doc so the search endpoint
# can resolve a building's metadata (notably the `site` field) when
# returning event results. This allows the frontend to display a
# campus badge (Seattle/Bothell/Tacoma) without an extra API call.
doc_by_id: Dict[str, Dict[str, Any]] = {}


def _clean_text(value: str) -> str:
    """
    Remove HTML tags and normalize whitespace in text.
    Args:
        value: The text to clean, may contain HTML tags and entities.
    Returns:
        Cleaned text with HTML removed and whitespace normalized.
    """
    value = re.sub(r"<[^>]+>", " ", value or "")
    value = re.sub(r"\s+", " ", value)
    return unescape(value).strip()                  # Special character fix.


def _load_query_hints() -> Dict[str, Any]:
    """
    Load query hint keywords from JSON configuration file.
    Query hints are used to enhance search results by recognizing topic
    keywords and temporal keywords (e.g. 'soon').
    Returns:
        Dictionary with 'time' and 'topics' keys containing hint keywords.
        Returns empty structure if file doesn't exist.
    """
    if not QUERY_HINTS_FILE.exists():
        return {"time": {}, "topics": {}}
    with QUERY_HINTS_FILE.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def _is_soon_query(query: str) -> bool:
    """
    Check if query contains temporal keywords indicating 'soon' events.
    Args:
        query: The user's search query.
    Returns:
        True if query contains 'soon' temporal hints, False otherwise.
    """
    normalized = query.lower()
    soon_terms = query_hints.get("time", {}).get("soon", [])
    return any(hint in normalized for hint in soon_terms)


def _query_topics(query: str) -> List[str]:
    """
    Extract topic keywords matched in the user's search query.
    Args:
        query: The user's search query.
    Returns:
        List of topic names found in the query. Empty list if no topics matched.
    """
    normalized = query.lower()
    topics = query_hints.get("topics", {})
    matched = []
    for topic_name, hints in topics.items():
        if any(hint in normalized for hint in hints):
            matched.append(topic_name)
    return matched


def _document_matches_topic(doc: Dict[str, Any], topic_name: str) -> bool:
    """
    Check if a document's content matches a specific topic.
    Args:
        doc: Document dictionary containing title, summary, text, and location.
        topic_name: Name of the topic to match against.
    Returns:
        True if document contains topic keywords, False otherwise.
    """
    haystack = " ".join(
        str(doc.get(field, "")) for field in ("title", "summary", "text", "location")
    ).lower()
    hints = query_hints.get("topics", {}).get(topic_name, [])
    return any(hint in haystack for hint in hints)


def _parse_dt(value: Optional[str]) -> Optional[datetime]:
    """
    Parse ISO format datetime string with UTC timezone handling.
    Args:
        value: ISO format datetime string or None.
    Returns:
        Parsed datetime with UTC timezone, or None if parsing fails or input is None.
    """
    if not value:
        return None
    try:
        parsed = datetime.fromisoformat(value)
    except ValueError:
        return None
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=timezone.utc)
    return parsed


def load_index() -> None:
    """
    Load the search index from disk into global variables.
    Loads embedding vectors, documents, metadata, and query hints.
    Sets index_error if files are missing. Initializes the SentenceTransformer
    model for encoding queries at runtime.
    """
    global model, embeddings, docs, index_meta, index_error, query_hints

    if not DOCS_FILE.exists() or not EMB_FILE.exists():
        index_error = "Index not found. Run backend/ingest.py and backend/build_index.py."
        return

    with DOCS_FILE.open("r", encoding="utf-8") as handle:
        docs = json.load(handle)
    # Build quick lookup by doc id for later use in search.
    # This mapping was added so we can find the building document
    # referenced by an event's `resolved_building_id` and expose the
    # building's `site` value in the search results. Frontend code
    # prefers that explicit `site` value to decide campus badges.
    global doc_by_id
    doc_by_id = {doc.get("id"): doc for doc in docs}

    emb_data = np.load(EMB_FILE)
    embeddings = emb_data["embeddings"].astype(np.float32)

    if META_FILE.exists():
        with META_FILE.open("r", encoding="utf-8") as handle:
            index_meta = json.load(handle)

    query_hints = _load_query_hints()

    model_name = index_meta.get("model", "all-MiniLM-L6-v2")
    model = SentenceTransformer(model_name)
    index_error = None


@app.on_event("startup")
def startup_event() -> None:
    """FastAPI startup event handler to initialize the search index."""
    load_index()


@app.get("/search")
def search(q: str, k: int = 5) -> Dict[str, Any]:
    """
    Perform semantic search across indexed documents.
    Ranks documents using semantic similarity and applies boost scoring for
    topic matches and temporal relevance ('soon' queries).
    Args:
        q: Search query string.
        k: Number of top results to return (default 5, min 1).
    Returns:
        Dictionary with 'query', 'results' (list of documents), and 'count'.
        Each result includes id, title, domain, snippet, source_url, and score.
    Raises:
        HTTPException: 503 if index is not loaded or files are missing.
    """
    if index_error:
        raise HTTPException(status_code=503, detail=index_error)
    if embeddings is None or model is None:
        raise HTTPException(status_code=503, detail="Index not loaded.")

    query = q.strip()
    if not query:
        return {"query": q, "results": [], "count": 0}

    matched_topics = _query_topics(query)
    want_soon = _is_soon_query(query)
    soon_cutoff = datetime.now(timezone.utc) + timedelta(days=14) if want_soon else None

    query_vec = model.encode([query], normalize_embeddings=True)[0]
    scores = embeddings @ query_vec

    ranked = []
    for idx, score in enumerate(scores):
        doc = docs[idx]
        if want_soon and doc.get("domain") == "event":
            start_dt = _parse_dt(doc.get("start"))
            if start_dt and start_dt > soon_cutoff:
                continue

        adjusted_score = float(score)
        for topic_name in matched_topics:
            if _document_matches_topic(doc, topic_name):
                adjusted_score += 0.25

        if want_soon and doc.get("domain") == "event" and doc.get("start"):
            start_dt = _parse_dt(doc.get("start"))
            if start_dt:
                adjusted_score += max(0.0, 0.1 - (start_dt - datetime.now(timezone.utc)).days * 0.01)

        ranked.append((adjusted_score, idx))

    ranked.sort(key=lambda item: item[0], reverse=True)
    top_indices = [idx for _, idx in ranked[: max(1, min(k, len(ranked)))]]

    results = []
    for idx in top_indices:
        doc = docs[idx]
        snippet = _clean_text(doc.get("summary") or doc.get("text", ""))
        if doc.get("domain") == "event":
            start_dt = _parse_dt(doc.get("start"))
            if start_dt:
                snippet = f"{start_dt.strftime('%A, %b %d, %Y')} - {snippet}"
        # Try to include resolved building/site info to help the frontend.
        # Rationale: events may reference a building id (resolved_building_id)
        # but the event document itself doesn't include the building's
        # `site` code. Looking up the building doc here lets us return a
        # `site` value (e.g. "SEA_MN", "BOTHELL", "TACOMA") so the
        # frontend can display an accurate campus badge without extra
        # round-trips.
        resolved_building_id = doc.get("resolved_building_id")
        resolved_site = None
        if resolved_building_id:
            building_doc = doc_by_id.get(resolved_building_id)
            if building_doc:
                resolved_site = building_doc.get("site")

        results.append(
            {
                "id": doc.get("id"),
                "title": doc.get("title"),
                "domain": doc.get("domain"),
                "snippet": snippet,
                "source_url": doc.get("source_url"),
                "start": doc.get("start"),
                "end": doc.get("end"),
                "score": float(scores[idx]),
                # Preserve the campus label already stored in ingest output
                # so the frontend can badge event results accurately without
                # guessing from text when the source data is explicit.
                "campus": doc.get("campus"),
                "location": doc.get("location"),
                "resolved_building_name": doc.get("resolved_building_name"),
                "resolved_building_id": resolved_building_id,
                "site": resolved_site,
            }
        )

    return {"query": q, "results": results, "count": len(results)}


@app.get("/status")
def status() -> Dict[str, Any]:
    """
    Get the current status of the search index.
    Returns:
        Dictionary with index_ready (bool), index_error (str or None),
        doc_count (int), and index_meta (dict with index metadata).
    """
    return {
        "index_ready": index_error is None,
        "index_error": index_error,
        "doc_count": len(docs),
        "index_meta": index_meta,
    }


app.mount("/", StaticFiles(directory=FRONTEND_DIR, html=True), name="static")
