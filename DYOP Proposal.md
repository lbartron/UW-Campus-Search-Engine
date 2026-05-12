**Group Members: Joseph Walter, Leo Barton, Kylie Chang** 

**UW Campus Search Engine — Project Proposal & Technical Specification**

**1\. UW Community Impact Statement**

UW students and staff regularly struggle to find campus information scattered across dozens of disconnected websites — the events calendar, building maps, and department pages all live in separate places with no unified search. This project builds a natural language search engine that lets users ask plain-English questions and get direct, sourced answers in one place.

The scope is deliberately narrow: UW events and buildings only. This keeps the product polished and completable within 4 weeks. The directory and departmental pages are explicitly out of scope for v1 and documented as a future extension.

---

**2\. Scoped Data Sources**

To prevent scope creep and ensure a stable data pipeline, the MVP covers exactly two domains:

| Domain | Source | Method | Freshness |
| ----- | ----- | ----- | ----- |
| UW Events | calendar.uw.edu iCal/RSS feed | API pull — structured, official | Daily re-index |
| UW Buildings | UW campus map public GeoJSON \+ static building pages | One-time scrape \+ manual curation | Weekly refresh |

Directory and departmental pages are explicitly out of scope for v1, documented as a named future extension in the repository README.

---

**3\. Data Pipeline & Legal Plan**

Events — calendar.uw.edu exposes a public iCal/RSS feed. This is a stable, structured, officially supported format requiring no scraping.

Buildings — UW's campus map uses a public GeoJSON endpoint. Supplementary building detail pages will be scraped once at project start, manually reviewed, and stored as static documents. No runtime scraping dependency.

Fallback — If a data source becomes unavailable, the last indexed snapshot continues serving results with a visible staleness warning in the UI.

Public Records Request — If richer data is needed (e.g., building hours), a UW public records request will be filed in Week 1 to respect the project spec's timing guidance.

The live application has zero runtime scraping dependencies — all data is pre-indexed into the vector store before deployment.

---

**4\. AI Integration Strategy**

The AI is the search engine itself, operating in three embedded layers:

Layer 1 — Embedding & Indexing: All documents (events, buildings) are embedded at ingest time using OpenAI text-embedding-3-small and stored in Pinecone (hosted vector DB — see deployment section). Documents are chunked with metadata tags for domain, date, and location type.

Layer 2 — Semantic Retrieval: User queries are embedded at runtime and matched via cosine similarity. No keyword matching. This allows queries like "somewhere quiet to study near the Ave" to match relevant building records naturally.

Layer 3 — RAG Answer Generation & Query Rewriting: Top-k retrieved chunks are passed to the Claude API to generate a concise, sourced answer with links. The LLM also rewrites ambiguous queries before retrieval — e.g., "somewhere outside to hang out" → "outdoor seating areas campus" — improving precision without extra user effort.

---

**5\. Evaluation Plan**

**Automated benchmark.** A hand-curated benchmark query set of 25 test questions will be written in Week 1, before any model tuning, and committed to the repository. Each query includes an expected top result and a pass/fail retrieval criterion (correct document in top 3?). The benchmark is re-run at each milestone to track improvement and catch regressions.

| Query | Expected Result |
| ----- | ----- |
| "When is the next comedy show on campus?" | UW events tagged comedy/performance |
| "Where is Kane Hall?" | Kane Hall building document |
| "Outdoor events this weekend" | Events filtered by date \+ outdoor location |

**Answer quality rubric.** Each generated answer is rated 1–3 by two team members independently using the following fixed criteria:

* 3 — Answer is correct, directly addresses the query, and includes a working source link.  
* 2 — Answer is partially correct or addresses the query but omits a relevant detail or source.  
* 1 — Answer is incorrect, off-topic, or fails to cite a source.

Ratings are averaged; any disagreement of more than 1 point is discussed and resolved before recording. This ensures consistent scoring across all three benchmark runs.

**Peer user testing.** As UW students, all three team members have direct access to peers who are the target users. In Week 3, after RAG integration is live, we will recruit 5 UW students (outside the team) to complete a short 15-minute test session. Participants will be asked to find answers to 5 realistic tasks (e.g., "find a free event happening this week," "figure out where your lecture in Kane Hall is") using only the search interface. We will observe where queries fail or produce confusing results and log any query phrasings not covered by the benchmark set. Findings will be used to add up to 5 new benchmark queries and inform any UI copy changes before the Week 4 final deployment.

---

**6\. Tech Stack**

| Layer | Tech |
| ----- | ----- |
| Frontend | React \+ Tailwind CSS |
| Backend | FastAPI (Python) |
| Embeddings | OpenAI text-embedding-3-small |
| Vector DB | Pinecone (hosted — replaces ChromaDB, see below) |
| LLM (RAG) | Claude API (Anthropic) |
| Deployment | Vercel (frontend) \+ Render (backend) |

---

**7\. Deployment & Cost Controls**

Pinecone replaces ChromaDB — Render's free tier uses ephemeral filesystems, meaning a locally hosted ChromaDB index gets wiped on restart. Pinecone is a hosted vector DB with a free tier that persists independently of the backend server, eliminating this risk entirely.

API cost controls — Three measures are in place to prevent runaway spend on the live public deployment:

* Query embedding cache — Repeated or near-identical queries return cached embeddings rather than calling OpenAI again. Implemented with a simple in-memory LRU cache in FastAPI.  
* Daily spend cap — A hard daily limit is set in the OpenAI and Anthropic dashboards. If the cap is hit, the app falls back to returning raw retrieval results without RAG generation.  
* Rate limiting — The FastAPI backend enforces a per-IP rate limit of 20 requests/minute using slowapi, preventing stress-testing from running up costs.

---

**8\. Revised 4-Week Milestone Roadmap**

| Week | Focus | Deliverables | Owners | Evaluation Checkpoint |
| ----- | ----- | ----- | ----- | ----- |
| Week 1 | Setup \+ Data | Repo live, Pinecone configured, iCal \+ GeoJSON pipeline ingesting data, benchmark query set (25 queries) \+ answer quality rubric written and committed | Leo: repo \+ Pinecone setup; Kylie: iCal \+ GeoJSON pipeline; Joseph: benchmark query set | Data pipeline verified; benchmark v1 \+ rubric in repo |
| Week 2 | Core Search | FastAPI semantic search endpoint working; basic React UI (search box \+ results list) deployed to public URL | Joseph: FastAPI search endpoint; Leo: React UI \+ Vercel deploy; Kylie: data quality review \+ re-indexing | Benchmark run \#1 — baseline retrieval score recorded |
| Week 3 | RAG \+ Polish \+ User Testing | Claude API RAG integration; query rewriting; cost controls \+ rate limiting live; UI polish; 5-person peer user test session completed | Kylie: RAG integration \+ query rewriting; Joseph: cost controls \+ rate limiting; Leo: UI polish \+ user test facilitation | Benchmark run \#2 — improvement over baseline shown; user test findings logged; up to 5 new benchmark queries added |
| Week 4 | Finalize | Project website live with architecture diagram \+ user guide; final deployment stable; in-class presentation | All: presentation prep; Joseph: project website \+ architecture diagram; Leo: user guide; Kylie: final deployment stability | Benchmark run \#3 — final quality score; full rubric self-check |

---

**9\. Repository Structure**

/  
├── backend/          \# FastAPI app, embedding pipeline, RAG logic  
├── frontend/         \# React \+ Tailwind UI  
├── data/             \# Ingestion scripts for iCal \+ GeoJSON  
├── benchmark/        \# 25-query test set \+ scoring scripts \+ rubric  
├── docs/             \# Architecture diagram, user guide  
└── README.md         \# Setup instructions \+ credentials if password-protected

Claude Evaluation  
5 / 5Overall grade  
Scope

5/5  
Tech stack

5/5  
Evaluation

5/5  
Feasibility

5/5  
Risk mgmt

5/5  
3 strengths  
Rigorous, well-defined evaluation framework

The combination of a pre-committed 25-query benchmark, a fixed 1–3 rubric with explicit inter-rater consistency protocol, and three scheduled re-runs is genuinely robust. Writing criteria before tuning eliminates hindsight bias — this is the right order of operations.  
Real user testing with a credible feedback loop

The peer testing plan is specific and actionable: 5 participants, 15 minutes, 5 structured tasks, scheduled in Week 3 with findings feeding directly into new benchmark queries and UI changes before final deployment. Grounding the "plain English" promise in actual user behavior is the right call.  
Named ownership across every milestone deliverable

Every task in the roadmap now has a name attached to it. This removes ambiguity during the high-pressure integration weeks and gives the team — and any evaluator — a clear accountability structure from day one.  
3 minor areas to watch  
User test sample is small

5 participants is fine for a course project, but the proposal would be stronger if it briefly acknowledged this limitation and noted that findings are directional rather than statistically conclusive. A single line would preempt the obvious critique.  
Query rewriting has no evaluation of its own

The proposal describes query rewriting as a feature but doesn't mention how its impact will be measured. Comparing benchmark retrieval scores with and without rewriting enabled — even informally — would substantiate the claim that it improves precision.  
No mention of iCal feed staleness handling

The fallback plan covers source unavailability well, but doesn't address events that have already passed appearing in results. A simple date-filter at query time — or a note that expired events are pruned on re-index — would close this gap cleanly.

The revised proposal earns a clean 5/5 — all three original weaknesses are fully resolved. The remaining notes are genuinely minor; no grader would deduct points for them, but they're worth knowing about as you actually build the thing. The stale events issue in particular is something you'll likely hit in Week 2 when real data starts flowing through.

