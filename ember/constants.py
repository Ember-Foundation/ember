from enum import IntEnum

# HTTP Status Codes
HTTP_100 = b"100 Continue"
HTTP_101 = b"101 Switching Protocols"
HTTP_200 = b"200 OK"
HTTP_201 = b"201 Created"
HTTP_204 = b"204 No Content"
HTTP_206 = b"206 Partial Content"
HTTP_301 = b"301 Moved Permanently"
HTTP_302 = b"302 Found"
HTTP_304 = b"304 Not Modified"
HTTP_400 = b"400 Bad Request"
HTTP_401 = b"401 Unauthorized"
HTTP_403 = b"403 Forbidden"
HTTP_404 = b"404 Not Found"
HTTP_405 = b"405 Method Not Allowed"
HTTP_408 = b"408 Request Timeout"
HTTP_413 = b"413 Payload Too Large"
HTTP_415 = b"415 Unsupported Media Type"
HTTP_422 = b"422 Unprocessable Entity"
HTTP_429 = b"429 Too Many Requests"
HTTP_500 = b"500 Internal Server Error"
HTTP_502 = b"502 Bad Gateway"
HTTP_503 = b"503 Service Unavailable"

STATUS_CODES = {
    100: HTTP_100, 101: HTTP_101,
    200: HTTP_200, 201: HTTP_201, 204: HTTP_204, 206: HTTP_206,
    301: HTTP_301, 302: HTTP_302, 304: HTTP_304,
    400: HTTP_400, 401: HTTP_401, 403: HTTP_403, 404: HTTP_404,
    405: HTTP_405, 408: HTTP_408, 413: HTTP_413, 415: HTTP_415,
    422: HTTP_422, 429: HTTP_429,
    500: HTTP_500, 502: HTTP_502, 503: HTTP_503,
}

# HTTP Methods
GET = b"GET"
POST = b"POST"
PUT = b"PUT"
PATCH = b"PATCH"
DELETE = b"DELETE"
HEAD = b"HEAD"
OPTIONS = b"OPTIONS"

ALL_METHODS = (GET, POST, PUT, PATCH, DELETE, HEAD, OPTIONS)

# Content Types
CONTENT_TYPE_JSON = b"application/json; charset=utf-8"
CONTENT_TYPE_TEXT = b"text/plain; charset=utf-8"
CONTENT_TYPE_HTML = b"text/html; charset=utf-8"
CONTENT_TYPE_SSE = b"text/event-stream; charset=utf-8"
CONTENT_TYPE_STREAM = b"application/octet-stream"
CONTENT_TYPE_FORM = b"application/x-www-form-urlencoded"
CONTENT_TYPE_MULTIPART = b"multipart/form-data"

# Common Headers
HEADER_CONTENT_TYPE = b"content-type"
HEADER_CONTENT_LENGTH = b"content-length"
HEADER_ACCEPT = b"accept"
HEADER_AUTHORIZATION = b"authorization"
HEADER_CACHE_CONTROL = b"cache-control"
HEADER_CONNECTION = b"connection"
HEADER_TRANSFER_ENCODING = b"transfer-encoding"
HEADER_X_REQUEST_ID = b"x-request-id"

# HTTP/1.1 Prefixes
HTTP_PREFIX = b"HTTP/1.1 "
CRLF = b"\r\n"
HEADER_SEP = b": "
CHUNK_END = b"0\r\n\r\n"

# Worker defaults
DEFAULT_KEEP_ALIVE_TIMEOUT = 30
DEFAULT_WORKER_TIMEOUT = 60
DEFAULT_BACKLOG = 4096
DEFAULT_WRITE_BUFFER = 65_536   # 64 KB high-watermark per connection


class Events(IntEnum):
    BEFORE_SERVER_START = 1
    AFTER_SERVER_START = 2
    BEFORE_ENDPOINT = 3
    AFTER_ENDPOINT = 4
    AFTER_RESPONSE_SENT = 5
    BEFORE_SERVER_STOP = 6
