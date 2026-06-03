import backend.app as app_module


def test_all_campuses_are_present_in_the_index(client):
    # Ensure the synthetic index still covers Seattle, Bothell, and Tacoma.
    payload = client.get("/status").json()
    assert payload["index_ready"] is True
    assert payload["doc_count"] == 6

    results = client.get("/search", params={"q": "campus", "k": 6}).json()["results"]
    campuses = {item.get("campus") for item in results if item.get("campus")}
    assert {"Seattle", "Bothell", "Tacoma"}.issubset(campuses)


def test_event_campus_tags_match_source_urls(client):
    # Verify event campus labels stay aligned with the source URLs represented in the fixture.
    results = client.get("/search", params={"q": "campus", "k": 6}).json()["results"]
    by_title = {item["title"]: item for item in results}

    assert by_title["Seattle Event"]["campus"] == "Seattle"
    assert by_title["Bothell Event"]["campus"] == "Bothell"
    assert by_title["Tacoma Event"]["campus"] == "Tacoma"


def test_building_site_codes_cover_all_campuses(client):
    # Confirm building site codes are present for all campuses so campus badges can come from explicit metadata.
    buildings = {doc["title"]: doc for doc in app_module.docs if doc.get("domain") == "building"}

    assert buildings["Seattle Hall"]["site"] == "SEA_MN"
    assert buildings["Bothell Center"]["site"] == "BOTHELL"
    assert buildings["Tacoma Center"]["site"] == "TACOMA"
