# UW Campus Search Engine — Technical Documentation

A local MVP for semantic search across UW events and buildings using Sentence-Transformers embeddings.

## Data Sources

- **Events:** Fetched from RSS/iCal feed via `feedparser`; normalized text extracted from entries
- **Buildings:** Pre-indexed from GeoJSON/static snapshots

## Pipeline

**Ingest** (`backend/ingest.py`):
- Fetches events via RSS with fallback to last snapshot if feed unavailable
- Parses event metadata (title, description, start/end times, location, link)
- Handles Trumba HTML format for location extraction
- Normalizes text and creates `data/snapshots/latest.json`
- Document fields: `id`, `title`, `domain` (event/building), `text`, `summary`, `start`, `end`, `location`, `source_url`

**Index** (`backend/build_index.py`):
- Loads snapshot, encodes all documents using SentenceTransformer (`all-MiniLM-L6-v2` default)
- Saves to: `docs.json`, `embeddings.npz`, `index_meta.json`
- Embeddings are L2-normalized for cosine similarity

## Search & Ranking

**Query Endpoint** (`GET /search?q=<query>&k=5`):
1. Encodes query using same model as index
2. Computes cosine similarity against all document embeddings
3. Applies adaptive scoring:
   - **Topic matching:** +0.25 boost if document matches detected query topics (from `query_hints.json`)
   - **Recency boost:** For "soon" queries, filters events > 14 days out and boosts by proximity to now
4. Returns top-k results with title, snippet, domain, score, source URL, date range (for events)

**Query Hints** (`backend/query_hints.json`):
- Detects intent: `"soon"` terms trigger recency filtering; topic keywords boost matching documents
- Example: "next event" → filters events starting within 14 days, boosts relevance

**Status Endpoint** (`GET /status`):
- Returns index readiness, document count, index metadata

## Tech Stack

| Component | Tech |
|-----------|------|
| Backend | FastAPI + Sentence-Transformers + NumPy |
| Ingestion | feedparser + requests |
| Embeddings | SentenceTransformer (all-MiniLM-L6-v2, 384-dim, L2-normalized) |
| Config | python-dotenv |
| Frontend | HTML + CSS + Vanilla JS |

## Setup

```bash
# 1. Clone and create venv
git clone <repo> && cd UW-Campus-Search-Engine
python -m venv venv && venv\Scripts\Activate.ps1

# 2. Install dependencies
pip install -r requirements.txt

# 3. Create .env with URLs
UW_EVENTS_RSS_URL="<url>"
UW_BUILDINGS_ARCGIS_URL="<url>"
LOCAL_EMBED_MODEL="all-MiniLM-L6-v2"

# 4. Build index
python backend/ingest.py
python backend/build_index.py

# 5. Run server
uvicorn backend.app:app --reload
```

## Directory Structure

```
├── backend/
│   ├── app.py              # FastAPI server + /search endpoint
│   ├── ingest.py           # Data fetching + snapshot creation
│   ├── build_index.py      # Embedding generation
│   └── query_hints.json    # Topic/time keywords for adaptive scoring
├── frontend/
│   ├── index.html          # Single-page search UI
│   └── styles.css
└── data/
    ├── snapshots/latest.json      # Ingested documents
    └── index/
        ├── docs.json              # Document metadata
        ├── embeddings.npz         # Embedding vectors
        └── index_meta.json        # Index metadata
```

## Key Features

- **Local-only:** No external APIs needed for search; all embeddings precomputed
- **Fast inference:** Model loads at startup; queries complete in ~50–100ms
- **Adaptive ranking:** Topic and recency boosting for intent-aware results
- **Snapshot-based:** Reproducible runs; fallback to last valid snapshot if sources unavailable
- **Configurable model:** Switch embedding models via `LOCAL_EMBED_MODEL` env var

## API Endpoints

- `GET /search?q=<query>&k=5` → Search results with adaptive ranking
- `GET /status` → Index health and metadata
- `GET /` → Serve frontend

## Query Response Format

```json
{
  "query": "where is kane hall?",
  "results": [
    {
      "id": "doc_123",
      "title": "Kane Hall",
      "domain": "building",
      "snippet": "Kane Hall is...",
      "source_url": "https://...",
      "score": 0.92
    }
  ],
  "count": 1
}
```

For events, response includes `start` and `end` ISO datetime strings.

## Deployment

- **Local:** Model loads on first startup (~10–15 seconds); queries complete in 50–100ms
- **Backend:** Can deploy to Render, Railway, or similar Python platforms
- **Frontend:** Static files can be deployed to CDN (Vercel, Netlify)
- **Production scaling:** Consider Pinecone for vector DB if moving beyond local storage

**Last Updated:** May 2026
