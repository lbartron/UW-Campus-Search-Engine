def test_homepage_and_status_are_available(client):
    # Smoke-test the app routes and fail fast if homepage or status behavior regresses.
    homepage = client.get("/")
    assert homepage.status_code == 200

    status = client.get("/status")
    assert status.status_code == 200

    payload = status.json()
    assert payload["index_ready"] is True
    assert payload["doc_count"] == 6

    html = homepage.text
    for campus in ("Seattle", "Bothell", "Tacoma"):
        # The homepage should still render the campus filter labels used by the UI.
        assert campus in html
