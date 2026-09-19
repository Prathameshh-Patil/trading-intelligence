import asyncio
from collections.abc import AsyncIterator, Awaitable, Callable
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request, Response
from fastapi.middleware.cors import CORSMiddleware

from app.api.routes.admin import router as admin_router
from app.api.routes.alerts import admin_router as admin_alerts_router
from app.api.routes.alerts import router as alerts_router
from app.api.routes.analyze import router as analyze_router
from app.api.routes.auth import router as auth_router
from app.api.routes.events import router as events_router
from app.api.routes.forecast import router as forecast_router
from app.api.routes.health import router as health_router
from app.api.routes.keys import router as keys_router
from app.api.routes.payments import router as payments_router
from app.api.routes.site import router as site_router
from app.api.routes.tickets import router as tickets_router
from app.api.routes.waitlist import router as waitlist_router
from app.api.routes.wellknown import router as wellknown_router
from app.api.routes.ws import router as ws_router
from app.config import settings
from app.core.origins import ORIGIN_REGEX
from app.db.session import SessionLocal
from app.services.bootstrap import promote_bootstrap_admin
from app.services.events import broadcaster


@asynccontextmanager
async def lifespan(_: FastAPI) -> AsyncIterator[None]:
    # Route handlers are sync and run in a threadpool; the SSE queues live on
    # this loop. The broadcaster needs to know which loop to hand events to.
    broadcaster.bind(asyncio.get_running_loop())
    if settings.bootstrap_admin_email:
        with SessionLocal() as db:
            promote_bootstrap_admin(db, settings.bootstrap_admin_email)
    yield


app = FastAPI(
    title="Vision Hub API",
    version="0.2.0",
    lifespan=lifespan,
)

# `ORIGIN_REGEX` covers the extension, Tauri and localhost; `cors_origins`
# is the deployed customer site and admin portal. Credentials are on because
# `/auth/refresh` is a cookie route -- every other route is bearer-only.
#
# The regex admits ANY extension id and ANY localhost port, in production
# too, and that is not the control. In production the API is not on
# localhost, so a page there is cross-site and the `SameSite=Lax` refresh
# cookie is never sent with its POST; an extension page has no cookie jar
# for this host at all. The regex decides who may READ a response, and every
# response worth reading needs a bearer token the page does not have.
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_origin_regex=ORIGIN_REGEX,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PATCH", "DELETE"],
    allow_headers=["Content-Type", "Authorization", "X-API-Key", "Last-Event-ID"],
    expose_headers=["Retry-After"],
)


@app.middleware("http")
async def security_headers(
    request: Request, call_next: Callable[[Request], Awaitable[Response]]
) -> Response:
    response = await call_next(request)
    response.headers.setdefault("X-Content-Type-Options", "nosniff")
    response.headers.setdefault("Referrer-Policy", "no-referrer")
    response.headers.setdefault("X-Frame-Options", "DENY")
    return response


@app.get("/health")
async def health():
    return {
        "status": "ok",
        "service": "api",
        "version": "0.2.0",
    }


app.include_router(wellknown_router)
app.include_router(health_router, prefix="/api/v1")
app.include_router(analyze_router, prefix="/api/v1")
app.include_router(forecast_router, prefix="/api/v1")
app.include_router(auth_router, prefix="/api/v1")
app.include_router(site_router, prefix="/api/v1")
app.include_router(keys_router, prefix="/api/v1")
app.include_router(payments_router, prefix="/api/v1")
app.include_router(tickets_router, prefix="/api/v1")
app.include_router(waitlist_router, prefix="/api/v1")
app.include_router(events_router, prefix="/api/v1")
app.include_router(admin_router, prefix="/api/v1")
app.include_router(alerts_router, prefix="/api/v1")
app.include_router(admin_alerts_router, prefix="/api/v1")
app.include_router(ws_router, prefix="/api/v1")
