## UW Campus Search Engine

A local MVP that ingests UW events and buildings, builds an embedding index, and serves a search UI via FastAPI.

### Quick Start

**1. Clone the repository**
```powershell
git clone https://github.com/lbartron/UW-Campus-Search-Engine.git
cd UW-Campus-Search-Engine
```

**2. Create and activate virtual environment**
```powershell
python -m venv venv
venv\Scripts\Activate.ps1
```

**3. Install dependencies**
```powershell
pip install -r requirements.txt
```

**4. Configure environment variables** (create `.env` in repo root)
```text
UW_EVENTS_RSS_URL="<UW events RSS feed URL>"
UW_BUILDINGS_ARCGIS_URL="https://gis.maps.uw.edu/federated/rest/services/PublicData/PublicData/FeatureServer/12"
LOCAL_EMBED_MODEL="all-MiniLM-L6-v2"
```

**5. Build the index**
```powershell
python backend/ingest.py
python backend/build_index.py
```

**6. Run the server**
```powershell
uvicorn backend.app:app --reload
```

Open http://localhost:8000 in your browser.

For detailed architecture and implementation information, see [DOCUMENTATION.md](DOCUMENTATION.md).
