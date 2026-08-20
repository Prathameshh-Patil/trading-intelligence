"""HTTP-boundary tests. Requires services/api/.env; the DB test needs Postgres up."""

from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def post(text, **extra):
    return client.post("/api/v1/analyze", json={"text": text, **extra})


def test_health():
    assert client.get("/health").json()["status"] == "ok"


def test_database_health():
    assert client.get("/api/v1/health/db").json() == {"status": "ok", "database": "ok"}


def test_bullish_text():
    body = post("Apple beat estimates with record profit and raised guidance.").json()
    assert body["sentiment"] == "bullish"
    assert body["confidence"] > 50
    assert body["signals"]


def test_bearish_text():
    body = post("The stock plunged after a downgrade, weak sales and layoffs.").json()
    assert body["sentiment"] == "bearish"
    assert body["confidence"] > 50


def test_neutral_text():
    body = post("The company will hold its annual meeting on Tuesday.").json()
    assert body["sentiment"] == "neutral"
    assert body["confidence"] == 50.0


def test_negation_flips_sentiment():
    assert post("Revenue did not beat expectations.").json()["sentiment"] == "bearish"


def test_response_shape_is_stable():
    body = post("Shares surged on strong growth.").json()
    assert set(body) == {"sentiment", "confidence", "summary", "signals"}
    assert isinstance(body["confidence"], float)
    assert all(isinstance(s, str) for s in body["signals"])


def test_optional_fields_accepted():
    r = post("Shares surged.", url="https://example.com/news", title="Markets")
    assert r.status_code == 200


def test_empty_text_rejected():
    assert post("").status_code == 422
    assert post("   ").status_code == 422


def test_oversized_text_rejected():
    assert post("surge " * 5_000).status_code == 422


def test_missing_text_rejected():
    assert client.post("/api/v1/analyze", json={"url": "https://example.com"}).status_code == 422


def test_cors_allows_extension_origin():
    origin = "chrome-extension://" + "a" * 32
    r = client.post(
        "/api/v1/analyze",
        json={"text": "Shares surged."},
        headers={"Origin": origin},
    )
    assert r.headers["access-control-allow-origin"] == origin
