from __future__ import annotations
from typing import Callable, TYPE_CHECKING

if TYPE_CHECKING:
    from ..request import Request
    from ..response import Response


class BearerAuthMiddleware:
    """BEFORE_ENDPOINT hook that validates Bearer token auth."""

    def __init__(
        self,
        verify_fn: Callable[[str], bool | dict],
        exclude_paths: list[str] | None = None,
    ) -> None:
        self._verify = verify_fn
        self._exclude = set(exclude_paths or [])

    async def __call__(self, request: "Request") -> "Response | None":
        from ..response import JSONResponse

        if request.path in self._exclude:
            return None

        auth = request.headers.get_str("authorization", "")
        if not auth or not auth.startswith("Bearer "):
            return JSONResponse({"error": "unauthorized"}, status_code=401)

        token = auth[7:].strip()
        result = self._verify(token)
        if result is False:
            return JSONResponse({"error": "forbidden"}, status_code=403)
        if isinstance(result, dict):
            request.context["auth"] = result
        return None


class APIKeyMiddleware:
    """BEFORE_ENDPOINT hook that validates API key via X-API-Key or Authorization header."""

    def __init__(
        self,
        valid_keys: set[str] | Callable[[str], bool],
        header: str = "x-api-key",
        exclude_paths: list[str] | None = None,
    ) -> None:
        self._keys = valid_keys
        self._header = header.lower()
        self._exclude = set(exclude_paths or [])

    async def __call__(self, request: "Request") -> "Response | None":
        from ..response import JSONResponse

        if request.path in self._exclude:
            return None

        key = request.headers.get_str(self._header, "")
        if not key:
            return JSONResponse({"error": "api_key_required"}, status_code=401)

        if callable(self._keys):
            valid = self._keys(key)
        else:
            valid = key in self._keys

        if not valid:
            return JSONResponse({"error": "invalid_api_key"}, status_code=403)

        request.context["api_key"] = key
        return None
