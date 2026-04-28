"""Ember hello-world — no DB, raw framework throughput."""
import sys
sys.path.insert(0, "/home/ismail/ember")

from ember import Ember, Request, Response

app = Ember()

_BODY = b"Hello, World!"
_RESPONSE = Response(_BODY, status_code=200, content_type=b"text/plain; charset=utf-8")

@app.get("/hello")
async def hello(request: Request) -> Response:
    return _RESPONSE

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=9010, workers=1, debug=False, startup_message=True)
