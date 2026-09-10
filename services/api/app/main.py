from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.routes.analyze import router as analyze_router
from app.api.routes.forecast import router as forecast_router
from app.api.routes.health import router as health_router

app = FastAPI(
    title="Trading Intelligence API",
    version="0.1.0",
)

# The popup's Origin changes every time the unpacked build is reloaded — a
# 32-char id on Chrome, a UUID on Firefox — so it has to be a pattern.
#
# A PACKAGED TAURI APP IS NOT localhost. Under `tauri dev` the webview loads
# `devUrl` and the Origin is `http://localhost:1420`, which the localhost branch
# already covers — so the S7 route works in dev and would have failed in the
# built app, where the frontend is served over Tauri's custom protocol:
# `tauri://localhost` on macOS and Linux, `http://tauri.localhost` on Windows.
# Neither matches `localhost:\d+`, which requires a port. Added here rather than
# discovered after a bundle.
app.add_middleware(
    CORSMiddleware,
    allow_origin_regex=(
        r"^(chrome-extension://[a-p]{32}"
        r"|moz-extension://[0-9a-f]{8}(-[0-9a-f]{4}){3}-[0-9a-f]{12}"
        r"|tauri://localhost"
        r"|http://tauri\.localhost"
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
app.include_router(forecast_router, prefix="/api/v1")
