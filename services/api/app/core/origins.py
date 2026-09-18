"""Which browser origins this API trusts.

Used twice: by the CORS middleware, and by `/auth/refresh` as its CSRF check
-- that route is authenticated by a cookie, so the browser will attach the
cookie to a request any site can trigger, and the `Origin` header is what
says which site did.
"""

import re

from app.config import settings

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
ORIGIN_REGEX = (
    r"^(chrome-extension://[a-p]{32}"
    r"|moz-extension://[0-9a-f]{8}(-[0-9a-f]{4}){3}-[0-9a-f]{12}"
    r"|tauri://localhost"
    r"|http://tauri\.localhost"
    r"|http://localhost:\d+"
    r"|http://127\.0\.0\.1:\d+)$"
)

_pattern = re.compile(ORIGIN_REGEX)


def origin_allowed(origin: str | None) -> bool:
    """`None` -- no header -- is allowed: a non-browser client has no cookie
    jar for CSRF to abuse, and every browser sends Origin on a cross-site POST."""
    if origin is None:
        return True
    return origin in settings.cors_origins or bool(_pattern.match(origin))
