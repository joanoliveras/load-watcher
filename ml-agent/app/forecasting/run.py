from __future__ import annotations

from typing import Dict, Iterable, List, Union

import joblib
import numpy as np
import pandas as pd

from app.config import get_model_path, get_node_name_to_id_override, VALID_NODE_IDS
from app.preprocessing.transforms import (
    build_feature_rows_from_payload,
    detect_current_host_with_app_metrics,
)


class ModelPredictor:
    def __init__(self, model_path: str | None = None):
        self.model_path = model_path or get_model_path()
        self.model = joblib.load(self.model_path)
        self.node_name_to_id = get_node_name_to_id_override()

    def predict_for_all_targets(
        self,
        load_watcher_payload: Dict,
        target_node_ids: Iterable[int] | None = None,
    ) -> Dict[int, List[float]]:
        """
        Build features for the specified target node IDs and run model prediction.
        Returns a mapping: target_node_id -> list of outputs (as floats).
        """
        # Determine current source host and ID
        node_metrics_map = (load_watcher_payload or {}).get("data", {}).get("NodeMetricsMap", {}) or {}
        host_name = detect_current_host_with_app_metrics(node_metrics_map)
        if not host_name:
            raise ValueError("Unable to determine current_host from payload.")
        src_id = self.node_name_to_id.get(host_name)
        if src_id is None:
            raise ValueError(f"Unknown current_host_name '{host_name}' for provided node_name_to_id mapping")

        # Final target set: provided list or all valid ids, excluding the current src
        target_ids_all = list(target_node_ids) if target_node_ids is not None else VALID_NODE_IDS
        target_ids = [int(tid) for tid in target_ids_all if int(tid) != int(src_id)]

        features: pd.DataFrame = build_feature_rows_from_payload(
            payload=load_watcher_payload,
            node_name_to_id=self.node_name_to_id,
            target_node_ids=target_ids,
        )
        y_pred: Union[np.ndarray, List[List[float]]] = self.model.predict(features)  # type: ignore[attr-defined]
        y_array: np.ndarray = np.asarray(y_pred)
        # Ensure 2D shape: (rows, outputs)
        if y_array.ndim == 1:
            y_array = y_array.reshape(-1, 1)
        results: Dict[int, List[float]] = {
            int(tgt): [float(x) for x in y_array[idx].tolist()]
            for idx, tgt in enumerate(target_ids)
        }
        return results
