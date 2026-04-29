"""Ember hello-world (workers from EMBER_WORKERS env, default 1)."""
import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "..", "..")))

from ember import Ember, Request, Response

app = Ember()
_HELLO = b"Hello, World!"


@app.get("/hello")
async def hello(request: Request) -> Response:
    return Response(_HELLO, content_type=b"text/plain; charset=utf-8")


if __name__ == "__main__":
    workers = int(os.environ.get("EMBER_WORKERS", "1"))
    port = int(os.environ.get("PORT", "9010"))
    app.run(host="0.0.0.0", port=port, workers=workers, debug=False, startup_message=True)
