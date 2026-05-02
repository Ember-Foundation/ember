"""FastAPI AI inference server — POST /predict → sentiment label + score.

Same offload pattern as the Ember app: inference runs on a worker thread so
the event loop is never blocked.
"""
import asyncio
import uvicorn
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

from _model import predict

app = FastAPI()


class PredictIn(BaseModel):
    text: str


class PredictOut(BaseModel):
    label: str
    score: float


@app.get("/health")
async def health():
    return {"status": "ok"}


@app.post("/predict", response_model=PredictOut)
async def predict_route(body: PredictIn):
    if not body.text:
        raise HTTPException(400, "missing 'text'")
    return await asyncio.to_thread(predict, body.text)


if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=9102, log_level="warning", loop="uvloop")
