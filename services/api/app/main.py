from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.routes.analyze import router as analyze_router
from app.api.routes.health import router as health_router

app = FastAPI(
    title="Trading Intelligence API",
    version="0.1.0",
)

# The extension's popup sends Origin: chrome-extension://<32-char id>, which
# changes every time the unpacked build is reloaded, so it has to be a pattern.
app.add_middleware(
    CORSMiddleware,
    allow_origin_regex=(
        r"^(chrome-extension://[a-p]{32}"
        r"|http://localhost:\d+"
        r"|http://127\.0\.0\.1:\d+)$"
    ),
    allow_methods=["GET", "POST"],
    allow_headers=["Content-Type"],
)


@app.get("/health")
async def health():
    return {
        "status": "ok",
        "service": "api",
        "version": "0.1.0",
    }


app.include_router(health_router, prefix="/api/v1")
app.include_router(analyze_router, prefix="/api/v1")
