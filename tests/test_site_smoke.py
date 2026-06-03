import os
from urllib.parse import urljoin

import requests

BASE_URL = os.environ.get("BASE_URL", "http://127.0.0.1:8000").rstrip("/")


def fetch(path: str) -> requests.Response:
    # Wrap requests so any network failure is converted into a clear CI error.
    url = urljoin(BASE_URL + "/", path.lstrip("/"))
    try:
        response = requests.get(url, timeout=15)
    except requests.RequestException as exc:
        raise AssertionError(f"Website unavailable at {BASE_URL}: {exc}") from exc
    return response


def test_homepage_and_status_are_available():
    # Smoke-test the running site and fail fast if the web app is unavailable.
    homepage = fetch("/")
    assert homepage.status_code == 200, f"Homepage unavailable at {BASE_URL}/: {homepage.status_code}"

    status = fetch("/status")
    assert status.status_code == 200, f"Status endpoint unavailable at {BASE_URL}/status: {status.status_code}"

    payload = status.json()
    assert payload.get("index_ready") is True, f"Index is not ready: {payload}"
    assert payload.get("doc_count", 0) > 0, f"Expected indexed documents, got: {payload}"

    html = homepage.text
    for campus in ("Seattle", "Bothell", "Tacoma"):
        # The homepage should expose the campus filter labels the UI depends on.
        assert campus in html, f"Expected campus filter '{campus}' in homepage HTML"
