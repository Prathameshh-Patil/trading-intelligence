"""Financial sentiment via Claude.

Replaces the Day 1 lexicon. `analyze` returns the same four keys it always has —
the contract in README.md is frozen and the extension parses it directly, so the
shape is load-bearing across a boundary no type checker spans.

Structured outputs do the enforcing: `Analysis` is sent as a JSON schema and the
response is decoded against it, so a malformed or half-written answer is a
`ValidationError` here rather than a wrong-shaped 200 the popup renders as junk.

Worth knowing what that does and does not cover. Field names, types, the required
set and the `sentiment` enum go into the schema and are enforced. Numeric bounds
and list maximums do not — they are stripped out and survive only as a description
hint, so on those the model is asked, not constrained. `Analysis` is therefore
written to the contract rather than to the prompt's style; see its docstring.
"""

from typing import Literal

import anthropic
from pydantic import BaseModel, Field

from app.config import settings

MODEL = "claude-haiku-4-5"

SYSTEM = """You analyse financial and market text and return a sentiment read.

sentiment: "bullish" if the text implies upward price pressure on the asset or
company discussed, "bearish" if downward, "neutral" if the text is procedural,
balanced, or carries no market-relevant signal. Judge the substance, not the
tone of the writing — a calmly worded bankruptcy filing is bearish.

confidence: 50-95. Use exactly 50 when the text carries no usable market signal.
Above 90 only when the direction is explicit and unambiguous. Never above 95 —
this is a reading of language, not a forecast.

summary: one sentence, plain English, describing what the text says about the
asset. No preamble, no hedging boilerplate.

signals: 1-4 short phrases naming the concrete things driving the read — the
specific numbers, events, or language you keyed on. The last one must be a
caution: what would change this read, or what to confirm before acting.

Report only what the text supports. If it is thin, say it is thin and score it
low rather than inventing a direction."""


class Analysis(BaseModel):
    """What the extension needs to render a result, and nothing more.

    Deliberately looser than the system prompt. The prompt asks for confidence
    50-95 and 1-4 signals; those are style, and the API does not enforce them —
    numeric and max-length bounds are dropped from the JSON schema and survive
    only as a description hint, so the model can miss them. Validating style
    here would turn a usable answer with `confidence: 97` into a failed request.
    These bounds are the contract instead: what the popup cannot render without.
    """

    sentiment: Literal["bullish", "bearish", "neutral"]
    confidence: float = Field(ge=0, le=100)
    summary: str
    signals: list[str] = Field(min_length=1)


client = anthropic.Anthropic(api_key=settings.anthropic_api_key)


def analyze(text: str) -> dict:
    """Score `text` and return sentiment, confidence (0-100), summary, signals.

    Raises `anthropic.APIError` if the call fails and `ValueError` if it returns
    nothing usable. The route turns both into a 503 — from the extension's side
    they are the same answer, "analysis unavailable".
    """
    response = client.messages.parse(
        model=MODEL,
        max_tokens=1024,
        system=SYSTEM,
        messages=[{"role": "user", "content": text}],
        output_format=Analysis,
    )
    if response.parsed_output is None:
        # No structured answer: the model refused, or ran out of output tokens
        # mid-object. Either way there is nothing to hand the popup.
        raise ValueError(f"no analysis returned (stop_reason={response.stop_reason})")
    return response.parsed_output.model_dump()
