"""HTTP-boundary tests. Requires services/api/.env; the DB test needs Postgres up.

Analysis calls Claude, so the boundary tests stub it out: they check the contract
the extension depends on (status, shape, validation, CORS, upstream failure),
which is what can break silently. Asserting a stub returns what the stub was
given proves nothing, so the claim that the *model* reads sentiment correctly is
left to the live tests at the bottom — real calls, run on request:

    LIVE_API_TESTS=1 uv run pytest

Without that variable they skip, and nothing here spends API credit.
"""

import json
import os

import anthropic
import httpx
import httpx2
import pytest
from fastapi.testclient import TestClient

# Bound directly: `from app.main import app` below rebinds the name `app` to the
# FastAPI instance, so `app.analysis` would not resolve to the module.
from app import analysis
from app.main import app

client = TestClient(app)

STUB = {
    "sentiment": "bullish",
    "confidence": 82.0,
    "summary": "Stubbed analysis.",
    "signals": ["Stubbed signal", "Confirm against price and volume before acting"],
}

live_only = pytest.mark.skipif(
    not os.getenv("LIVE_API_TESTS"),
    reason="hits the real Claude API; set LIVE_API_TESTS=1 to run",
)


@pytest.fixture
def stub_analysis(monkeypatch):
    """Replace the Claude call with a canned result. Returns a list the test can
    read to assert what text actually reached the analyser."""
    seen = []

    def fake(text):
        seen.append(text)
        return dict(STUB)

    monkeypatch.setattr("app.api.routes.analyze.run_analysis", fake)
    return seen


REPLY = {
    "sentiment": "bearish",
    "confidence": 78,
    "summary": "Guidance was cut and the stock fell.",
    "signals": ["Guidance cut", "Shares fell on the news", "Confirm the magnitude"],
}


@pytest.fixture
def upstream(monkeypatch):
    """Swap the Anthropic transport, not `analyze` itself, so the real request
    building and response decoding in app/analysis.py are exercised.

    Call the returned function with the JSON body the model should "reply";
    read `.request` afterwards to assert what went over the wire.
    """
    box = {}

    def set_reply(payload, stop_reason="end_turn"):
        def handler(request):
            box["request"] = json.loads(request.content)
            return httpx2.Response(
                200,
                json={
                    "id": "msg_01",
                    "type": "message",
                    "role": "assistant",
                    "model": "claude-haiku-4-5",
                    "stop_reason": stop_reason,
                    "stop_sequence": None,
                    "content": [{"type": "text", "text": payload}],
                    "usage": {"input_tokens": 120, "output_tokens": 60},
                },
            )

        monkeypatch.setattr(
            analysis,
            "client",
            anthropic.Anthropic(
                api_key="test",
                http_client=httpx2.Client(transport=httpx2.MockTransport(handler)),
            ),
        )
        return box

    return set_reply


def post(text, **extra):
    return client.post("/api/v1/analyze", json={"text": text, **extra})


def test_health():
    assert client.get("/health").json()["status"] == "ok"


def test_database_health():
    assert client.get("/api/v1/health/db").json() == {"status": "ok", "database": "ok"}


def test_response_shape_is_stable(stub_analysis):
    body = post("Shares surged on strong growth.").json()
    assert set(body) == {"sentiment", "confidence", "summary", "signals"}
    assert body["sentiment"] in {"bullish", "bearish", "neutral"}
    assert isinstance(body["confidence"], float)
    assert all(isinstance(s, str) for s in body["signals"])


def test_text_reaches_the_analyser_stripped(stub_analysis):
    post("  Shares surged.  ")
    assert stub_analysis == ["Shares surged."]


def test_optional_fields_accepted(stub_analysis):
    r = post("Shares surged.", url="https://example.com/news", title="Markets")
    assert r.status_code == 200


def test_upstream_failure_is_503(monkeypatch):
    def boom(text):
        raise anthropic.APIConnectionError(request=httpx.Request("POST", "https://api.anthropic.com"))

    monkeypatch.setattr("app.api.routes.analyze.run_analysis", boom)
    r = post("Shares surged.")
    assert r.status_code == 503
    assert r.json()["detail"]["analysis"] == "unavailable"


def test_upstream_request_matches_the_contract(upstream):
    box = upstream(json.dumps(REPLY))
    post("Company X cut guidance; shares fell 8%.")

    sent = box["request"]
    assert sent["model"] == "claude-haiku-4-5"
    assert sent["system"]
    assert sent["messages"] == [
        {"role": "user", "content": "Company X cut guidance; shares fell 8%."}
    ]
    schema = sent["output_config"]["format"]["schema"]
    assert schema["required"] == ["sentiment", "confidence", "summary", "signals"]
    assert schema["properties"]["sentiment"]["enum"] == ["bullish", "bearish", "neutral"]


def test_well_formed_reply_is_decoded(upstream):
    upstream(json.dumps(REPLY))
    body = post("Company X cut guidance.").json()
    assert body["sentiment"] == "bearish"
    assert body["confidence"] == 78.0
    assert body["signals"] == REPLY["signals"]


def test_drift_outside_prompt_style_still_succeeds(upstream):
    """The prompt asks for confidence 50-95 and 1-4 signals, but the API does not
    enforce either — those bounds are stripped from the JSON schema and survive
    only as a description hint. A model that misses them has still produced a
    usable answer, so it must not become a 503."""
    upstream(json.dumps({**REPLY, "confidence": 97, "signals": [f"s{i}" for i in range(6)]}))
    body = post("Company X cut guidance.").json()
    assert body["confidence"] == 97.0
    assert len(body["signals"]) == 6


def test_unusable_reply_is_503(upstream):
    # Ran out of output tokens mid-object: nothing to hand the popup.
    upstream('{"sentiment":"bear', stop_reason="max_tokens")
    r = post("Company X cut guidance.")
    assert r.status_code == 503
    assert r.json()["detail"]["analysis"] == "unavailable"


def test_empty_text_rejected():
    assert post("").status_code == 422
    assert post("   ").status_code == 422


def test_oversized_text_rejected():
    assert post("surge " * 5_000).status_code == 422


def test_missing_text_rejected():
    assert client.post("/api/v1/analyze", json={"url": "https://example.com"}).status_code == 422


@pytest.mark.parametrize(
    "origin",
    [
        "chrome-extension://" + "a" * 32,
        "moz-extension://a1b2c3d4-1234-5678-9abc-def012345678",
        "http://localhost:4173",
    ],
)
def test_cors_allows_extension_origins(stub_analysis, origin):
    r = client.post(
        "/api/v1/analyze",
        json={"text": "Shares surged."},
        headers={"Origin": origin},
    )
    assert r.headers["access-control-allow-origin"] == origin


def test_cors_rejects_foreign_origin():
    r = client.options(
        "/api/v1/analyze",
        headers={
            "Origin": "https://evil.example.com",
            "Access-Control-Request-Method": "POST",
        },
    )
    assert "access-control-allow-origin" not in r.headers


@live_only
def test_live_bullish_text():
    body = post("Apple beat estimates with record profit and raised guidance.").json()
    assert body["sentiment"] == "bullish"
    assert body["confidence"] > 50


@live_only
def test_live_bearish_text():
    body = post("The stock plunged after a downgrade, weak sales and layoffs.").json()
    assert body["sentiment"] == "bearish"
    assert body["confidence"] > 50


@live_only
def test_live_neutral_text():
    body = post("The company will hold its annual meeting on Tuesday.").json()
    assert body["sentiment"] == "neutral"


@live_only
def test_live_negation_flips_sentiment():
    # The case the lexicon needed a hand-written negation window for.
    assert post("Revenue did not beat expectations.").json()["sentiment"] == "bearish"


@live_only
def test_live_confidence_stays_in_contract():
    body = post("Shares surged on strong growth and a raised outlook.").json()
    assert 50 <= body["confidence"] <= 95
    assert 1 <= len(body["signals"]) <= 4
