"""Shared model loader for the AI inference bench.

We use distilbert-base-uncased-finetuned-sst-2-english — a real, downloadable
SST-2 sentiment classifier (~270 MB, ~67M params). On a single CPU thread it
takes ~8 ms per request at steady state, fast enough that framework overhead
shows up clearly (a 1-3 ms framework cost is 12-37% of the per-request budget).

`torch.set_num_threads(1)` is critical for fair benchmarking: without it,
torch's intra-op parallelism conflicts with the asyncio threadpool's inter-op
parallelism and you measure thread contention, not the framework.
"""
import torch
from transformers import AutoTokenizer, AutoModelForSequenceClassification

MODEL_NAME = "distilbert-base-uncased-finetuned-sst-2-english"

torch.set_num_threads(1)
torch.set_num_interop_threads(1)

_tokenizer = AutoTokenizer.from_pretrained(MODEL_NAME)
_model = AutoModelForSequenceClassification.from_pretrained(MODEL_NAME)
_model.eval()
_LABELS = ("NEGATIVE", "POSITIVE")


def predict(text: str) -> dict:
    """Run sentiment classification. Blocking; call from a worker thread."""
    with torch.inference_mode():
        inp = _tokenizer(text, return_tensors="pt", truncation=True, max_length=64)
        logits = _model(**inp).logits[0]
        probs = logits.softmax(-1).tolist()
        idx = 0 if probs[0] > probs[1] else 1
        return {"label": _LABELS[idx], "score": probs[idx]}
