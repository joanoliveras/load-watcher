from __future__ import annotations

from typing import Any, Dict, List

from fastapi import FastAPI, HTTPException, Request
from pydantic import BaseModel

from app.forecasting.run import ModelPredictor
from app.config import get_output_names
from app.preprocessing.transforms import detect_current_host_with_app_metrics, build_feature_rows_from_payload


class PredictResponse(BaseModel):
    columns: List[str]
    source_host: str
    source_id: int
    target_map: Dict[int, str]
    input_features: Dict[int, Dict[str, float]]
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

    # Detect source host and id for clarity in response
    node_metrics_map = (payload or {}).get("data", {}).get("NodeMetricsMap", {}) or {}
    host_name = detect_current_host_with_app_metrics(node_metrics_map)
    if not host_name:
        raise HTTPException(status_code=400, detail="Unable to determine current_host from payload.")
    src_id = predictor.node_name_to_id.get(host_name)
    if src_id is None:
        raise HTTPException(status_code=400, detail=f"Unknown current_host_name '{host_name}' in node map.")

    # Build a target id->hostname map for only the returned predictions
    id_to_name = {v: k for k, v in predictor.node_name_to_id.items()}
    target_map: Dict[int, str] = {int(tid): id_to_name.get(int(tid), "") for tid in result.keys()}

    # Reconstruct the exact input feature rows used by the model for transparency
    target_ids_in_order = [int(tid) for tid in result.keys()]
    features_df = build_feature_rows_from_payload(
        payload=payload,
        node_name_to_id=predictor.node_name_to_id,
        target_node_ids=target_ids_in_order,
    )
    input_features: Dict[int, Dict[str, float]] = {}
    for idx, tid in enumerate(target_ids_in_order):
        row_series = features_df.iloc[idx]
        input_features[int(tid)] = {str(col): float(row_series[col]) for col in features_df.columns}

    return PredictResponse(
        columns=columns,
        source_host=host_name,
        source_id=int(src_id),
        target_map=target_map,
        input_features=input_features,
        predictions=result,
    )
