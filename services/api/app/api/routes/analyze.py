from typing import Annotated, Literal

from fastapi import APIRouter
from pydantic import BaseModel, Field, StringConstraints

from app.analysis import analyze as run_analysis

router = APIRouter()

# Whitespace is stripped first, so a blank or whitespace-only selection is a 422
# rather than an analysis of nothing.
SelectedText = Annotated[
    str,
    StringConstraints(strip_whitespace=True, min_length=1, max_length=20_000),
]


class AnalyzeRequest(BaseModel):
    text: SelectedText
    url: str | None = Field(default=None, max_length=2_048)
    title: str | None = Field(default=None, max_length=512)


class AnalyzeResponse(BaseModel):
    sentiment: Literal["bullish", "bearish", "neutral"]
    confidence: float = Field(ge=0, le=100)
    summary: str
    signals: list[str]


@router.post("/analyze", response_model=AnalyzeResponse)
def analyze(request: AnalyzeRequest) -> dict:
    return run_analysis(request.text)
