from fastapi import APIRouter
from pydantic import BaseModel


router = APIRouter()


class AnalyzeRequest(BaseModel):
    text: str
    url: str | None = None
    title: str | None = None


class AnalyzeResponse(BaseModel):
    sentiment: str
    confidence: float
    summary: str
    signals: list[str]


@router.post("/analyze", response_model=AnalyzeResponse)
def analyze(request: AnalyzeRequest):
    # Temporary response.
    # Replace with the actual model/service later.

    return AnalyzeResponse(
        sentiment="Bullish",
        confidence=87.0,
        summary=(
            "The selected text contains potentially positive market signals. "
            "Further validation with live market data is recommended."
        ),
        signals=[
            "Positive language detected",
            "Potentially favorable market catalyst",
            "Requires confirmation with price and volume data",
        ],
    )
