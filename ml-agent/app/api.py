from __future__ import annotations

from typing import Any, Dict

from fastapi import FastAPI, HTTPException, Request
from pydantic import BaseModel

from app.forecasting.run import ModelPredictor


class PredictResponse(BaseModel):
    predictions: Dict[int, list[float]]


app = FastAPI(title="ml-agent", version="0.1.0")
predictor = ModelPredictor()


@app.get("/healthz")
def healthz() -> Dict[str, str]:
    return {"status": "ok"}


@app.post("/predict", response_model=PredictResponse)
async def predict(request: Request) -> PredictResponse:
    """
    Accepts a Load Watcher JSON payload in the request body.
    The agent infers the current host by finding which node bucket contains torchserve metrics.
    """
    try:
        payload: Dict[str, Any] = await request.json()
    except Exception as exc:
        raise HTTPException(status_code=400, detail=f"Invalid JSON payload: {exc}") from exc

    if not isinstance(payload, dict):
        raise HTTPException(status_code=400, detail="Payload must be a JSON object")

    try:
        result = predictor.predict_for_all_targets(
            load_watcher_payload=payload,
            current_host_name=None,
        )
    except Exception as exc:
        raise HTTPException(status_code=400, detail=f"Inference failed: {exc}") from exc

    return PredictResponse(predictions=result)
