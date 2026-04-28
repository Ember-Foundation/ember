class ServerLimits:
    __slots__ = (
        "worker_timeout", "keep_alive_timeout",
        "max_headers_size", "write_buffer",
    )

    def __init__(
        self,
        worker_timeout: int = 60,
        keep_alive_timeout: int = 30,
        max_headers_size: int = 16 * 1024,
        write_buffer: int = 419_430,
    ) -> None:
        self.worker_timeout = worker_timeout
        self.keep_alive_timeout = keep_alive_timeout
        self.max_headers_size = max_headers_size
        self.write_buffer = write_buffer


class RouteLimits:
    __slots__ = ("timeout", "max_body_size", "in_memory_threshold")

    def __init__(
        self,
        max_body_size: int = 4 * 1024 * 1024,
        timeout: int = 300,
        in_memory_threshold: int = 1 * 1024 * 1024,
    ) -> None:
        self.max_body_size = max_body_size
        self.timeout = timeout
        self.in_memory_threshold = in_memory_threshold


class TokenLimits:
    __slots__ = (
        "tokens_per_minute", "tokens_per_day",
        "max_prompt_tokens", "max_completion_tokens",
    )

    def __init__(
        self,
        tokens_per_minute: int = 100_000,
        tokens_per_day: int | None = None,
        max_prompt_tokens: int = 32_768,
        max_completion_tokens: int = 4_096,
    ) -> None:
        self.tokens_per_minute = tokens_per_minute
        self.tokens_per_day = tokens_per_day
        self.max_prompt_tokens = max_prompt_tokens
        self.max_completion_tokens = max_completion_tokens
