# PISAN-Suggest.md

*Produced by Claude.AI on 2026-05-29*

## Project Overview

UW Campus Search Engine is a semantic search MVP that ingests UW events (from Trumba RSS feeds for Seattle, Bothell, and Tacoma) and building data (from a UW ArcGIS FeatureServer), embeds the documents locally with `sentence-transformers` (`all-MiniLM-L6-v2`), and serves a FastAPI search endpoint behind a single-page vanilla-JS UI. The intended audience is UW students and staff who currently have to bounce between disconnected calendars and map pages to answer simple campus questions.

## Evaluation Against Assignment Specification

Evaluation based only on what is visible in the GitHub repository.

### UW Community Impact (10 pts)

The target user (UW students/staff looking for events or buildings) is clear and the tri-campus scope is a real strength: `backend/ingest.py` and `backend/query_hints.json` both treat Seattle, Bothell, and Tacoma as first-class (`UW_EVENTS_RSS_URL`, `UWB_EVENTS_RSS_URL`, `UWT_EVENTS_RSS_URL`, plus `bothell`/`tacoma`/`seattle` hint groups), and the frontend renders explicit campus badges via `determineCampus()` in `frontend/index.html`. The README/DOCUMENTATION focuses on developer setup rather than an end-user value statement, and there is no link to a live deployment or screenshots, which weakens the visible community pitch.

Score guidance: roughly **7-8/10**. The product idea clearly serves UW; presentation as a community-facing tool is thin.

### AI Integration (15 pts)

This is the biggest gap between the proposal and the shipped repo. The DYOP Proposal commits to a three-layer AI stack (OpenAI `text-embedding-3-small`, Pinecone, Claude RAG with query rewriting). The actual code uses only local `SentenceTransformer` embeddings plus cosine similarity (`backend/app.py` lines 215-244), with a hand-written keyword booster (`+0.25` for topic match, `+1.0` for temporal match in `query_hints.json`). There is no LLM call, no Claude/OpenAI/Anthropic/Pinecone import anywhere in the tree, and no RAG answer generation. A `grep` across `*.py`/`*.md`/`*.html` finds no `openai`, `anthropic`, `claude`, `langchain`, or `llm` references in code.

Embeddings-only semantic search is still AI, and it is the load-bearing feature here (no keyword fallback), so this is genuinely "embedded" rather than a sidecar chatbot, which is what the rubric cares about. But it is materially less ambitious than the proposal promised and the adaptive scoring is hand-tuned heuristics, not learned.

Score guidance: roughly **9-11/15**. AI is central, but reduced in scope vs. the proposal and there is no generative layer.

### Technical Execution (25 pts)

What works well, from the code:

- Clean separation of `ingest.py` -> snapshot -> `build_index.py` -> `embeddings.npz` + `docs.json` + `index_meta.json`, with a snapshot fallback story per `DOCUMENTATION.md`.
- Sensible runtime shape in `backend/app.py`: model loaded once at startup, L2-normalized embeddings, vectorized scoring (`embeddings @ query_vec`), `/status` endpoint exposing index readiness.
- Multi-campus ingest with site classification, surfacing `campus` and a resolved `site` field that flows through to the UI badges (`doc_by_id` lookup at lines 159-167 / 262-287).
- All functions have docstrings; types are annotated; reasonably well-commented (`8d10236 added comments on all backend changes`).

Concerns visible in the repo:

- No tests anywhere. The proposal commits to a 25-query benchmark with three scheduled re-runs; there is no `benchmark/` directory, no test files, no scoring script.
- `backend/app.py` mounts `StaticFiles` at `/` which silently shadows future API routes; minor risk as the API grows.
- The temporal boost adds a flat `+1.0` for any matching weekday hint (line 240) regardless of whether the document's `start` actually falls on that day, which will mis-rank.
- `setup_guide` is PowerShell-only; macOS/Linux contributors need to translate.
- No `.github/workflows/` directory: no CI, no lint, no automated index rebuild.
- `requirements.txt` is unpinned (`fastapi`, `sentence-transformers`, etc.), so reproducible builds are not guaranteed.

Score guidance: roughly **16-19/25**. Code is clean and the pipeline is real, but no tests, no CI, no benchmark, and a couple of correctness rough edges.

### Project Web Presence (15 pts)

This is the weakest visible area. No live URL is referenced in `README.md` or `DOCUMENTATION.md`; the closing line of `DOCUMENTATION.md` only says "Backend: Can deploy to Render, Railway, or similar" as future work. A `netlify-host` branch exists but its diff against `main` mostly strips `PISAN-Suggest.md`, `query_hints.json` content, `app.py` features, and chunks of `frontend/index.html`/`styles.css` (`git diff main origin/netlify-host --stat` shows the netlify branch is missing 416 lines that are on main). So either the deployed Netlify build is significantly behind `main`, or Netlify hosting was abandoned. There is also no separate project website, no architecture diagram, no user guide, and no screenshots in either MD file.

Score guidance: roughly **5-8/15**. A live link plus a one-page site would lift this significantly.

### Milestones & Planning (20 pts)

The `DYOP Proposal.md` is genuinely strong: named owners per week, an evaluation rubric, a 25-query benchmark plan, a peer testing plan, and a cost-control plan. The git history reflects an actual collaboration: commits from Joseph Walter, Leo Bartron, Kylie Chang, plus `angelwing888` (badge-feature), plus a merged `working-model` -> `design-features` -> `campus-badges` flow with real PRs (#1, #3, #4, #6, #7, #8, #9). Branch hygiene is decent.

Two gaps lower the score: (1) the proposal's Week 1 commitment to a benchmark set in the repo is unmet (no `benchmark/` directory exists); (2) there is no `MILESTONES.md` or weekly status note showing rubric-style progress checks against the proposal.

Score guidance: roughly **13-16/20**.

### Peer Review (15 pts) - Not evaluable from repository alone

No peer-review artifacts (review notes, peer comments, retrospective) are committed to the repo. If those exist on Canvas or a private doc, they are not visible here.

## Suggested Improvements & New Features

### UI / UX

- The "Filter badges" panel exposes four taxonomies (Domain, Campus, Event type, Building type) but the event/building type labels come from `inferLabel()` keyword matching in `frontend/index.html` lines 308-344, so filters can disagree with reality. Move that classification server-side once during ingest, store it on the doc, and have the UI just read `doc.event_type` / `doc.building_type`.
- Add a visible "freshness" line driven by `/status` -> `index_meta.created_at` so users know when the index was last rebuilt; `formatLastUpdated()` already exists, wire it into the header instead of just printing to a debug area.
- Show the actual building campus badge for an event whose location resolved to a building - the data is already on the response (`resolved_building_name`, `site`), but new users won't notice; render a small "in <Building>, <Campus>" line under each event card.
- Make the search box and submit/filter buttons stack on narrow screens; today the `.row` flex layout in `styles.css` will squeeze the input on mobile.
- Add empty-state and zero-results copy: e.g. "No events in the next 14 days match - try removing the 'soon' filter or expanding campus" rather than a blank results panel.

### New Features

- Implement the proposal's promised LLM layer as an opt-in feature flag: take top-k retrieved docs and call Claude (or any chat model) to produce a 1-2 sentence sourced answer above the result cards. This closes the gap between proposal and product and lifts the AI Integration score with very little code.
- Add the 25-query benchmark in `benchmark/queries.json` plus a `python -m benchmark.run` script that prints top-3 hit rate. Commit baseline, then improvements; reference the result table in the README.
- Add a `/suggest?q=` endpoint that returns 3-5 query completions based on doc titles, and wire it to a `<datalist>` on the input - very low cost, big UX lift.
- Add date-range and "this weekend" filters that actually consult `doc.start`, replacing the current flat `+1.0` weekday boost which doesn't check `start`.
- Add a building-detail page or modal: clicking a building result shows its full text/location/site instead of the truncated snippet.
- Prune past events at ingest time so the index doesn't carry yesterday's lectures. The proposal's "user feedback" notes called this out and it is still not handled in `ingest.py`.

### Code Quality / Technical

- Pin dependencies in `requirements.txt` (`fastapi==0.115.*`, `sentence-transformers==3.*`, etc.) so deploys and grading are reproducible.
- Add a `.github/workflows/ci.yml` that runs `ruff`/`flake8`, `mypy`, and a smoke test that loads the index and queries `/search?q=kane%20hall`. Even one job protects future PRs.
- Move the static mount off `/` (e.g. `app.mount("/static", StaticFiles(...))` and serve `index.html` from an explicit route) so API routes added later are not shadowed.
- Fix the temporal scoring bug in `backend/app.py` lines 236-240: a query that says "monday" boosts every document by `+1.0` regardless of whether the event's `start` is on Monday. Compare `start_dt.weekday()` to the matched day.
- Add unit tests for `_clean_text`, `_parse_dt`, `_query_topics`, and `_document_matches_topic`; these are pure functions and trivially testable, and they protect the scoring contract.
- Reconcile the `netlify-host` branch with `main` - right now it strips ~400 lines of code that main has, including badge logic and query hints. Either rebase it or delete it and add a Netlify config (or Render `render.yaml`) on `main` so deploy lives where the code lives.
- Replace the in-memory single-process index load with a startup lifespan that surfaces a clear error if `data/index/` is empty - the current `@app.on_event("startup")` is deprecated in newer FastAPI; use `lifespan=`.
- Cache query embeddings (the proposal's LRU cache) - one line with `functools.lru_cache` around an `_encode(query)` helper - this is meaningful when the same queries are repeated.
- The `_load_query_hints()` function is called both in `load_index()` and used as a module-level default; consolidate so hints can be hot-reloaded without an app restart, useful while tuning.
