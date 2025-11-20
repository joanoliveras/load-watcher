from __future__ import annotations

from typing import Any, Dict, List

from fastapi import FastAPI, HTTPException, Request
from pydantic import BaseModel

from app.forecasting.run import ModelPredictor
from app.config import get_output_names


class PredictResponse(BaseModel):
    columns: List[str]
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
    The agent infers the current host in where the app is running by finding which node bucket contains torchserve metrics.
    """
    try:
        payload: Dict[str, Any] = await request.json()
    except Exception as exc:
        raise HTTPException(status_code=400, detail=f"Invalid JSON payload: {exc}") from exc
    try:
        result = predictor.predict_for_all_targets(
            load_watcher_payload=payload
        )
    except Exception as exc:
        raise HTTPException(status_code=400, detail=f"Inference failed: {exc}") from exc

    # Derive column names, honoring configured overrides and result width
    any_row = next(iter(result.values()), [])
    num_outputs = len(any_row)
    configured = get_output_names()
    if len(configured) >= num_outputs:
        columns = configured[:num_outputs]
    else:
        # Fallback to generic names if configured list is shorter
        columns = [f"y_{i}" for i in range(num_outputs)]

    return PredictResponse(columns=columns, predictions=result)
