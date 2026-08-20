from fastapi import FastAPI

from app.api.routes.health import router as health_router


app = FastAPI(
    title="Trading Intelligence API",
    version="0.1.0",
)


@app.get("/health")
async def health():
    return {
        "status": "ok",
        "service": "api",
        "version": "0.1.0",
    }


app.include_router(health_router)
