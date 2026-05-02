from __future__ import annotations
from typing import AsyncGenerator, TYPE_CHECKING

from ...response import SSEResponse, TokenStreamResponse

if TYPE_CHECKING:
    from ..ratelimit.token_bucket import TokenBucket


def sse_stream(
    llm_stream: AsyncGenerator[str, None],
    token_bucket: "TokenBucket | None" = None,
    event_type: str = "message",
    include_done_sentinel: bool = True,
) -> SSEResponse:
    """Wrap any async token generator in an SSEResponse.

    If token_bucket is provided, each token is gated against the bucket
    before being sent — providing back-pressure on rate-limited streams.
    """
    if token_bucket is not None:
        return TokenStreamResponse(
            stream=llm_stream,
            bucket=token_bucket,
            event_type=event_type,
            include_done_sentinel=include_done_sentinel,
        )
    return SSEResponse(
        stream=llm_stream,
        event_type=event_type,
        include_done_sentinel=include_done_sentinel,
    )
