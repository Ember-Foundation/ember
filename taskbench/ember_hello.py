"""Ember hello-world server — pure framework throughput, no DB."""
import sys
sys.path.insert(0, "/home/ismail/ember")

from ember import Ember, Request, Response

app = Ember()

_HELLO = b"Hello, World!"

@app.get("/hello")
async def hello(request: Request) -> Response:
    return Response(_HELLO, content_type=b"text/plain; charset=utf-8")

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=9010, workers=1, debug=False, startup_message=True)
