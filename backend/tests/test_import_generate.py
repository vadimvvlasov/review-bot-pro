"""CSV import (AC-04..AC-06) and on-demand generation (AC-09..AC-15)."""

from pathlib import Path

HEADER = "author_name,review_text,rating"

FIXTURE_CSV = Path(__file__).parent / "data" / "test_reviews.csv"


def test_import_fixture_csv_all_rows_valid(client):
    res = client.post(
        "/api/reviews/import",
        files={"file": ("test_reviews.csv", FIXTURE_CSV.read_bytes(), "text/csv")},
    )
    assert res.status_code == 201, res.text
    assert res.json() == {"status": "success", "imported": 20, "skipped": 0, "errors": []}
    assert len(client.get("/api/reviews").json()) == 4 + 20


def _csv(rows: list[str]) -> str:
    return "\n".join([HEADER, *rows])


def test_import_valid_csv(client):
    text = _csv(["Ann,Great espresso and fast service,5", "Bob,Nice spot for work,4"])
    res = client.post("/api/reviews/import", files={"file": ("r.csv", text, "text/csv")})
    assert res.status_code == 201, res.text
    body = res.json()
    assert body == {"status": "success", "imported": 2, "skipped": 0, "errors": []}
    assert len(client.get("/api/reviews").json()) == 6


def test_import_partial_skips_invalid_and_reports_rows(client):
    text = _csv(
        [
            "Ann,Great espresso and fast service,5",
            ",Empty author name here,4",
            "Bob,Nice spot for work,9",
            "Cara,Lovely pastries every morning,4",
        ]
    )
    res = client.post("/api/reviews/import", files={"file": ("r.csv", text, "text/csv")})
    assert res.status_code == 201
    body = res.json()
    assert body["imported"] == 2
    assert body["skipped"] == 2
    assert body["errors"] == [
        {"row": 3, "error": "Author name cannot be empty"},
        {"row": 4, "error": "Rating must be between 1 and 5"},
    ]


def test_import_skips_duplicates(client):
    text = _csv(["Zed,Truly unique review text here,5", "Zed,Truly unique review text here,5"])
    res = client.post("/api/reviews/import", files={"file": ("r.csv", text, "text/csv")})
    assert res.status_code == 201
    body = res.json()
    assert body["imported"] == 1
    assert body["skipped"] == 1
    assert body["errors"][0]["error"] == "Duplicate review skipped"


def test_import_missing_headers_400(client):
    res = client.post(
        "/api/reviews/import", files={"file": ("r.csv", "name,text,stars\nAnn,Nice,5", "text/csv")}
    )
    assert res.status_code == 400
    assert "missing required column" in res.json()["message"]


def test_import_empty_file_400(client):
    res = client.post("/api/reviews/import", files={"file": ("r.csv", "", "text/csv")})
    assert res.status_code == 400


def test_import_too_many_rows_400(client):
    rows = [f"User {i},Solid coffee here number {i},5" for i in range(101)]
    res = client.post(
        "/api/reviews/import", files={"file": ("r.csv", _csv(rows), "text/csv")}
    )
    assert res.status_code == 400
    assert "100" in res.json()["message"]


def test_import_oversize_file_400(client):
    big_text = _csv([f"Ann,{'a' * (1024 * 1024)},5"])
    res = client.post(
        "/api/reviews/import", files={"file": ("big.csv", big_text, "text/csv")}
    )
    assert res.status_code == 400
    assert "1 MB" in res.json()["message"]


def test_generate_reply_success_bounds(client):
    review_id = client.get("/api/reviews").json()[1]["id"]  # Tom Ridley, rating 2
    res = client.post(f"/api/reviews/{review_id}/generate")
    assert res.status_code == 200, res.text
    body = res.json()
    assert 10 <= len(body["reply_text"]) <= 500
    assert body["detected_sentiment"] == "negative"
    assert 1 <= len(body["detected_tags"]) <= 3


def test_generate_reply_positive(client):
    review_id = client.get("/api/reviews").json()[0]["id"]  # Maria Petrova, rating 5
    body = client.post(f"/api/reviews/{review_id}/generate").json()
    assert body["detected_sentiment"] == "positive"


def test_generate_reply_regenerate_overwrites_with_instructions(client):
    review_id = client.get("/api/reviews").json()[0]["id"]
    first = client.post(f"/api/reviews/{review_id}/generate").json()["reply_text"]
    second = client.post(
        f"/api/reviews/{review_id}/generate", json={"instructions": "offer a free cookie"}
    ).json()["reply_text"]
    assert second != first
    assert "free cookie" in second
    assert len(client.get("/api/reviews").json()) == 4  # no new rows (AC-15)


def test_generate_without_settings_400(empty_client):
    created = empty_client.post(
        "/api/reviews",
        json={"author_name": "Ann", "review_text": "Great place overall.", "rating": 5},
    ).json()
    res = empty_client.post(f"/api/reviews/{created['id']}/generate")
    assert res.status_code == 400


def test_generate_unknown_review_404(client):
    res = client.post("/api/reviews/00000000-0000-0000-0000-000000000000/generate")
    assert res.status_code == 404
