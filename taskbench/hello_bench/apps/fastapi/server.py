"""FastAPI hello-world."""
from fastapi import FastAPI
from fastapi.responses import PlainTextResponse

app = FastAPI()


@app.get("/hello", response_class=PlainTextResponse)
async def hello() -> str:
    return "Hello, World!"
