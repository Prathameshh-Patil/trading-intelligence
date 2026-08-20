"""Lexicon sentiment for financial text.

Deterministic and dependency-free on purpose. This is the honest Day 1 baseline
the extension integrates against; swapping in a model later only has to keep
`analyze` returning the same four keys.
"""

import re

BULLISH = {
    "beat", "beats", "bullish", "breakout", "buyback", "dividend", "exceeded",
    "expansion", "gain", "gains", "grew", "growth", "momentum", "optimistic",
    "outperform", "profit", "profits", "raised", "rally", "rallied", "rebound",
    "record", "strong", "stronger", "surge", "surged", "upgrade", "upgraded",
}

BEARISH = {
    "bankruptcy", "bearish", "cut", "decline", "declined", "default",
    "downgrade", "downgraded", "fell", "layoffs", "loss", "losses", "miss",
    "missed", "misses", "plunge", "plunged", "probe", "recession", "selloff",
    "slump", "slumped", "underperform", "volatility", "warning", "weak",
    "weaker",
}

# A negator within this many words flips the term it applies to, so
# "did not beat expectations" is not read as bullish.
NEGATORS = {"fail", "failed", "fails", "never", "no", "not", "t", "without"}
NEGATION_WINDOW = 3

WORD = re.compile(r"[a-z']+")


def _hits(text: str) -> tuple[list[str], list[str]]:
    words = WORD.findall(text.lower())
    up: list[str] = []
    down: list[str] = []

    for i, word in enumerate(words):
        if word in BULLISH:
            polarity = up
            flipped = down
        elif word in BEARISH:
            polarity = down
            flipped = up
        else:
            continue

        if any(w in NEGATORS for w in words[max(0, i - NEGATION_WINDOW) : i]):
            flipped.append(f"not {word}")
        else:
            polarity.append(word)

    return up, down


def analyze(text: str) -> dict:
    """Score `text` and return sentiment, confidence (0-100), summary, signals."""
    up, down = _hits(text)
    total = len(up) + len(down)

    if total == 0:
        return {
            "sentiment": "neutral",
            "confidence": 50.0,
            "summary": "No recognised financial sentiment terms in the selected text.",
            "signals": ["No bullish or bearish language detected"],
        }

    margin = (len(up) - len(down)) / total
    # Confidence never reaches 100: it grows with how lopsided the hits are
    # (margin) and how many there are to begin with (evidence).
    evidence = min(1.0, total / 5)
    confidence = round(50 + 45 * abs(margin) * evidence, 1)

    if margin > 0.15:
        sentiment = "bullish"
    elif margin < -0.15:
        sentiment = "bearish"
    else:
        sentiment = "neutral"
        confidence = 50.0

    signals = []
    if up:
        signals.append(f"Bullish language: {', '.join(sorted(set(up))[:5])}")
    if down:
        signals.append(f"Bearish language: {', '.join(sorted(set(down))[:5])}")
    if total < 3:
        signals.append("Thin evidence — few sentiment terms in the selection")
    signals.append("Confirm against price and volume before acting")

    return {
        "sentiment": sentiment,
        "confidence": confidence,
        "summary": (
            f"{len(up)} bullish and {len(down)} bearish terms across "
            f"{len(text.split())} words. Lexicon baseline, not a market forecast."
        ),
        "signals": signals,
    }
