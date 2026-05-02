class EmberException(Exception):
    pass


class RouteNotFound(EmberException):
    status_code = 404


class MethodNotAllowed(EmberException):
    status_code = 405


class RequestTimeout(EmberException):
    status_code = 408


class PayloadTooLarge(EmberException):
    status_code = 413


class UnsupportedMediaType(EmberException):
    status_code = 415


class RateLimitExceeded(EmberException):
    status_code = 429

    def __init__(self, retry_after: float = 1.0):
        self.retry_after = retry_after
        super().__init__(f"Rate limit exceeded. Retry after {retry_after:.2f}s")


class TokenLimitExceeded(RateLimitExceeded):
    def __init__(self, tokens_requested: int, tokens_available: float, retry_after: float = 1.0):
        self.tokens_requested = tokens_requested
        self.tokens_available = tokens_available
        super().__init__(retry_after)


class InternalServerError(EmberException):
    status_code = 500


class ServiceUnavailable(EmberException):
    status_code = 503


class ModelUnavailable(ServiceUnavailable):
    def __init__(self, model_name: str):
        self.model_name = model_name
        super().__init__(f"Model '{model_name}' is currently unavailable")


class InvalidRequestBody(EmberException):
    status_code = 400

    def __init__(self, message: str = "Invalid request body"):
        super().__init__(message)


class MissingTemplateVar(EmberException):
    def __init__(self, var_name: str):
        self.var_name = var_name
        super().__init__(f"Missing required template variable: '{var_name}'")


class ToolNotFound(EmberException):
    def __init__(self, tool_name: str):
        self.tool_name = tool_name
        super().__init__(f"Tool '{tool_name}' not registered")


class ToolExecutionError(EmberException):
    def __init__(self, tool_name: str, error: Exception):
        self.tool_name = tool_name
        self.original_error = error
        super().__init__(f"Tool '{tool_name}' execution failed: {error}")
