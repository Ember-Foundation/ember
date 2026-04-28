from __future__ import annotations
from typing import TYPE_CHECKING

from ...response import JSONResponse

if TYPE_CHECKING:
    from ...request import Request
    from .token_bucket import GlobalTokenBucket


class RateLimitMiddleware:
    """BEFORE_ENDPOINT hook that enforces token-per-minute limits.

    Performs a cheap token estimate from request body size before the
    model is even called. Actual token usage is reconciled in the
    AFTER_ENDPOINT hook via TokenStreamResponse.tokens_sent.
    """

    __slots__ = ("global_bucket", "per_api_key", "estimate_from_body", "_key_buckets")

    def __init__(
        self,
        global_bucket: "GlobalTokenBucket",
        per_api_key: bool = False,
        estimate_from_body: bool = True,
    ) -> None:
        self.global_bucket = global_bucket
        self.per_api_key = per_api_key
        self.estimate_from_body = estimate_from_body
        self._key_buckets: dict = {}

    async def __call__(self, request: "Request") -> JSONResponse | None:
        estimated = 0
        if self.estimate_from_body and request._body_cache:
            estimated = request.estimate_tokens()

        consumed = await self.global_bucket.consume_async(max(1, estimated))
        if not consumed:
            retry_after = self.global_bucket.tokens_until_available(max(1, estimated))
            return JSONResponse(
                {"error": "rate_limit_exceeded", "retry_after": round(retry_after, 2)},
                status_code=429,
                headers={"retry-after": str(int(retry_after) + 1)},
            )

        if self.per_api_key:
            api_key = request.headers.get_str("authorization", "")
            if api_key:
                bucket = self._key_buckets.get(api_key)
                if bucket and not bucket.consume(max(1, estimated)):
                    retry_after = bucket.tokens_until_available(max(1, estimated))
                    return JSONResponse(
                        {"error": "rate_limit_exceeded", "retry_after": round(retry_after, 2)},
                        status_code=429,
                        headers={"retry-after": str(int(retry_after) + 1)},
                    )

        return None
