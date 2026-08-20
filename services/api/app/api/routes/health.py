from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.api.dependencies import get_db

router = APIRouter()


@router.get("/health/db")
def database_health(db: Session = Depends(get_db)):
    try:
        db.execute(text("SELECT 1"))
    except SQLAlchemyError as exc:
        # A health check reports "down" as a status, not a 500 traceback.
        raise HTTPException(
            status_code=503,
            detail={"status": "error", "database": "unreachable", "error": str(exc.__cause__ or exc)},
        ) from exc

    return {
        "status": "ok",
        "database": "ok",
    }
