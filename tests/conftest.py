import json
from pathlib import Path

import numpy as np
import pytest
from fastapi.testclient import TestClient

import backend.app as app_module


def _build_docs():
    return [
        {
            "id": "building:seattle-hall",
            "domain": "building",
            "title": "Seattle Hall",
            "summary": "Seattle campus building",
            "text": "Seattle Hall\nSite: SEA_MN\nCampus: Seattle",
            "source_url": "https://www.washington.edu/seattle-hall",
            "start": None,
            "end": None,
            "location": "Seattle Hall",
            "site": "SEA_MN",
        },
        {
            "id": "building:bothell-center",
            "domain": "building",
            "title": "Bothell Center",
            "summary": "Bothell campus building",
            "text": "Bothell Center\nSite: BOTHELL\nCampus: Bothell",
            "source_url": "https://www.uwb.edu/bothell-center",
            "start": None,
            "end": None,
            "location": "Bothell Center",
            "site": "BOTHELL",
        },
        {
            "id": "building:tacoma-center",
            "domain": "building",
            "title": "Tacoma Center",
            "summary": "Tacoma campus building",
            "text": "Tacoma Center\nSite: TACOMA\nCampus: Tacoma",
            "source_url": "https://www.tacoma.uw.edu/tacoma-center",
            "start": None,
            "end": None,
            "location": "Tacoma Center",
            "site": "TACOMA",
        },
        {
            "id": "event:seattle-event",
            "domain": "event",
            "title": "Seattle Event",
            "summary": "Seattle campus event",
            "text": "Seattle Event\nCampus: Seattle\nLocation: Seattle Hall",
            "source_url": "https://www.washington.edu/calendar/seattle-event",
            "start": None,
            "end": None,
            "location": "Seattle Hall",
            "campus": "Seattle",
            "resolved_building_id": "building:seattle-hall",
            "resolved_building_name": "Seattle Hall",
        },
        {
            "id": "event:bothell-event",
            "domain": "event",
            "title": "Bothell Event",
            "summary": "Bothell campus event",
            "text": "Bothell Event\nCampus: Bothell\nLocation: Bothell Center",
            "source_url": "https://www.uwb.edu/calendar/bothell-event",
            "start": None,
            "end": None,
            "location": "Bothell Center",
            "campus": "Bothell",
            "resolved_building_id": "building:bothell-center",
            "resolved_building_name": "Bothell Center",
        },
        {
            "id": "event:tacoma-event",
            "domain": "event",
            "title": "Tacoma Event",
            "summary": "Tacoma campus event",
            "text": "Tacoma Event\nCampus: Tacoma\nLocation: Tacoma Center",
            "source_url": "https://www.tacoma.uw.edu/calendar/tacoma-event",
            "start": None,
            "end": None,
            "location": "Tacoma Center",
            "campus": "Tacoma",
            "resolved_building_id": "building:tacoma-center",
            "resolved_building_name": "Tacoma Center",
        },
    ]


def _build_embeddings(doc_count: int) -> np.ndarray:
    embeddings = np.zeros((doc_count, 384), dtype=np.float32)
    for index in range(doc_count):
        embeddings[index, index % embeddings.shape[1]] = 1.0
    return embeddings


@pytest.fixture()
def client(monkeypatch, tmp_path):
    docs = _build_docs()
    index_dir = tmp_path / "index"
    index_dir.mkdir(parents=True, exist_ok=True)

    docs_file = index_dir / "docs.json"
    emb_file = index_dir / "embeddings.npz"
    meta_file = index_dir / "index_meta.json"

    docs_file.write_text(json.dumps(docs, indent=2), encoding="utf-8")
    np.savez_compressed(emb_file, embeddings=_build_embeddings(len(docs)))
    meta_file.write_text(
        json.dumps({"model": "all-MiniLM-L6-v2", "doc_count": len(docs)}, indent=2),
        encoding="utf-8",
    )

    monkeypatch.setenv("CI_LIGHTWEIGHT_MODEL", "1")
    monkeypatch.setattr(app_module, "DOCS_FILE", docs_file)
    monkeypatch.setattr(app_module, "EMB_FILE", emb_file)
    monkeypatch.setattr(app_module, "META_FILE", meta_file)
    monkeypatch.setattr(app_module, "docs", [])
    monkeypatch.setattr(app_module, "embeddings", None)
    monkeypatch.setattr(app_module, "index_meta", {})
    monkeypatch.setattr(app_module, "index_error", None)
    monkeypatch.setattr(app_module, "doc_by_id", {})
    monkeypatch.setattr(app_module, "model", None)

    with TestClient(app_module.app) as test_client:
        yield test_client