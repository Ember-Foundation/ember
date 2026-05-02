"""Ember AI inference server — POST /predict → sentiment label + score.

Inference runs on a dedicated worker-thread pool via asyncio.to_thread so the
event loop is never blocked. Same offload pattern as FastAPI's default handler
threadpool, for a fair comparison.
"""
import asyncio
import sys

sys.path.insert(0, "/home/ismail/ember")

from ember import Ember, Request, JSONResponse
from _model import predict

app = Ember()


@app.get("/health")
async def health(request: Request) -> JSONResponse:
    return JSONResponse({"status": "ok"})


@app.post("/predict")
async def predict_route(request: Request) -> JSONResponse:
    try:
        body = await request.json()
    except Exception:
        return JSONResponse({"error": "Invalid JSON"}, status_code=400)
    text = body.get("text", "")
    if not text:
        return JSONResponse({"error": "missing 'text'"}, status_code=400)
    result = await asyncio.to_thread(predict, text)
    return JSONResponse(result)


@app.handle(Exception)
async def err(exc: Exception) -> JSONResponse:
    return JSONResponse({"error": str(exc)}, status_code=500)


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=9101, workers=1, debug=False, startup_message=False)
