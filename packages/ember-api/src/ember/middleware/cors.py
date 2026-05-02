from __future__ import annotations
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from ..request import Request
    from ..response import Response


class CORSMiddleware:
    """BEFORE_ENDPOINT hook that handles CORS preflight and injects headers."""

    def __init__(
        self,
        allow_origins: list[str] | str = "*",
        allow_methods: list[str] | None = None,
        allow_headers: list[str] | None = None,
        allow_credentials: bool = False,
        max_age: int = 86400,
    ) -> None:
        if isinstance(allow_origins, str):
            allow_origins = [allow_origins]
        self.allow_origins = allow_origins
        self.allow_methods = allow_methods or ["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"]
        self.allow_headers = allow_headers or ["content-type", "authorization", "x-request-id"]
        self.allow_credentials = allow_credentials
        self.max_age = max_age

    def _cors_headers(self, origin: str) -> dict[str, str]:
        if "*" in self.allow_origins or origin in self.allow_origins:
            allowed_origin = origin if self.allow_credentials else "*"
        else:
            return {}
        headers = {
            "access-control-allow-origin": allowed_origin,
            "access-control-allow-methods": ", ".join(self.allow_methods),
            "access-control-allow-headers": ", ".join(self.allow_headers),
            "access-control-max-age": str(self.max_age),
        }
        if self.allow_credentials:
            headers["access-control-allow-credentials"] = "true"
        return headers

    async def __call__(self, request: "Request") -> "Response | None":
        from ..response import Response

        origin = request.headers.get_str("origin", "")
        if not origin:
            return None

        cors_headers = self._cors_headers(origin)
        if not cors_headers:
            return None

        # Handle preflight OPTIONS
        if request.method == b"OPTIONS":
            return Response(b"", status_code=204, headers=cors_headers)

        # For non-preflight, we attach headers — returned as None to continue
        # but the response will have CORS headers added in AFTER_ENDPOINT
        request.context["_cors_headers"] = cors_headers
        return None
