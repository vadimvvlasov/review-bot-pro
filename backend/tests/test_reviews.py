"""Review queue CRUD: list/create/update/delete + error paths."""

REVIEW = {
    "author_name": "Ann Lee",
    "review_text": "Great espresso but service was a bit slow today.",
    "rating": 4,
    "source": "manual",
}


def test_list_reviews_seeded_newest_first(client):
    res = client.get("/api/reviews")
    assert res.status_code == 200
    reviews = res.json()
    assert len(reviews) == 4
    assert [r["author_name"] for r in reviews] == [
        "Maria Petrova",
        "Tom Ridley",
        "Aiko Tanaka",
        "Daniel Okafor",
    ]


def test_create_review_defaults_to_draft_with_empty_ai_fields(client):
    res = client.post("/api/reviews", json=REVIEW)
    assert res.status_code == 201, res.text
    body = res.json()
    assert body["status"] == "draft"
    assert body["reply_text"] is None
    assert body["detected_sentiment"] is None
    assert body["detected_tags"] == []
    assert body["id"]


def test_create_review_duplicate_conflict_case_insensitive(client):
    assert client.post("/api/reviews", json=REVIEW).status_code == 201
    dup = {**REVIEW, "author_name": "  ann lee ", "review_text": REVIEW["review_text"].upper()}
    res = client.post("/api/reviews", json=dup)
    assert res.status_code == 409
    assert res.json() == {"message": "This review already exists in your queue"}


def test_create_review_validation_errors(client):
    assert client.post("/api/reviews", json={**REVIEW, "rating": 6}).status_code == 422
    assert client.post("/api/reviews", json={**REVIEW, "rating": 0}).status_code == 422
    assert client.post("/api/reviews", json={**REVIEW, "review_text": "ok"}).status_code == 422
    assert client.post("/api/reviews", json={**REVIEW, "author_name": ""}).status_code == 422


def test_update_review_approve_flow(client):
    created = client.post("/api/reviews", json=REVIEW).json()
    res = client.patch(
        f"/api/reviews/{created['id']}",
        json={"reply_text": "Thanks Ann, we are on it!", "status": "approved"},
    )
    assert res.status_code == 200
    assert res.json()["status"] == "approved"
    assert res.json()["reply_text"] == "Thanks Ann, we are on it!"
    listed = {r["id"]: r for r in client.get("/api/reviews").json()}
    assert listed[created["id"]]["status"] == "approved"


def test_update_review_too_long_reply(client):
    created = client.post("/api/reviews", json=REVIEW).json()
    res = client.patch(f"/api/reviews/{created['id']}", json={"reply_text": "x" * 501})
    assert res.status_code == 422


def test_update_unknown_review_404(client):
    res = client.patch(
        "/api/reviews/00000000-0000-0000-0000-000000000000", json={"status": "approved"}
    )
    assert res.status_code == 404
    assert res.json() == {"message": "Review not found"}


def test_delete_review(client):
    created = client.post("/api/reviews", json=REVIEW).json()
    res = client.delete(f"/api/reviews/{created['id']}")
    assert res.status_code == 204
    assert res.content == b""
    ids = [r["id"] for r in client.get("/api/reviews").json()]
    assert created["id"] not in ids


def test_delete_unknown_review_404(client):
    res = client.delete("/api/reviews/00000000-0000-0000-0000-000000000000")
    assert res.status_code == 404
