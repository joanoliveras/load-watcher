
from __future__ import annotations

from typing import Dict, Iterable, List, Tuple, Optional

import pandas as pd

from app.config import (
    FEATURE_RANGES,
    VALID_NODE_IDS,
    get_feature_order,
)


def _metric_value_from_list(metrics: List[Dict], metric_name: str) -> float:
    for entry in metrics:
        if entry.get("name") == metric_name:
            return float(entry.get("value", 0.0))
    return 0.0


def _extract_app_metrics(node_metrics_map: Dict, current_host_name: str) -> Dict[str, float]:
    """
    Prefer extracting torchserve app metrics from the current host's node bucket.
    Fallback to the empty key bucket "" if present.
    """
    # Try node-specific bucket first
    node_bucket = node_metrics_map.get(current_host_name, {}) or {}
    node_metrics_list = node_bucket.get("metrics", []) or []
    node_vals = {
        "torchserve_app_cpu_src": _metric_value_from_list(node_metrics_list, "kepler:container_torchserve_cpu_rate:1m"),
        "torchserve_app_power_src": _metric_value_from_list(node_metrics_list, "kepler:container_torchserve_watt:1m"),
        "torchserve_app_energy_src": _metric_value_from_list(node_metrics_list, "kepler:container_torchserve_joules:1m"),
        "torchserve_app_latency_src": _metric_value_from_list(node_metrics_list, "ts:latency:1m:ms"),
        "torchserve_app_qps_src": _metric_value_from_list(node_metrics_list, "ts:throughput:1m:rps"),
        "torchserve_app_user": _metric_value_from_list(node_metrics_list, "locust_current_users"),
    }
    # If node bucket didn't contain any TS-specific metrics, fallback to app-level bucket
    has_any_ts = any([
        node_vals["torchserve_app_cpu_src"],
        node_vals["torchserve_app_power_src"],
        node_vals["torchserve_app_energy_src"],
        node_vals["torchserve_app_latency_src"],
        node_vals["torchserve_app_qps_src"],
        node_vals["torchserve_app_user"],
    ])
    if has_any_ts:
        return node_vals

    app_bucket = node_metrics_map.get("", {}) or {}
    metrics_list = app_bucket.get("metrics", []) or []
    return {
        "torchserve_app_cpu_src": _metric_value_from_list(metrics_list, "kepler:container_torchserve_cpu_rate:1m"),
        "torchserve_app_power_src": _metric_value_from_list(metrics_list, "kepler:container_torchserve_watt:1m"),
        "torchserve_app_energy_src": _metric_value_from_list(metrics_list, "kepler:container_torchserve_joules:1m"),
        "torchserve_app_latency_src": _metric_value_from_list(metrics_list, "ts:latency:1m:ms"),
        "torchserve_app_qps_src": _metric_value_from_list(metrics_list, "ts:throughput:1m:rps"),
        "torchserve_app_user": _metric_value_from_list(metrics_list, "locust_current_users"),
    }


def _extract_node_metrics_for(node_metrics_map: Dict, node_name: str) -> Dict[str, float]:
    node_bucket = node_metrics_map.get(node_name, {}) or {}
    metrics_list = node_bucket.get("metrics", []) or []
    return {
        "torchserve_node_cpu_src": _metric_value_from_list(metrics_list, "kepler:cpu_rate:1m:by_node"),
        "torchserve_node_power_src": _metric_value_from_list(metrics_list, "kepler:node_platform_watt:1m:by_node"),
        "torchserve_node_energy_src": _metric_value_from_list(metrics_list, "kepler:node_platform_joules:1m:by_node"),
    }


def _minmax_scale_features(raw_features: Dict[str, float]) -> Dict[str, float]:
    scaled: Dict[str, float] = {}
    for name, value in raw_features.items():
        scaler = FEATURE_RANGES.get(name)
        if scaler is None:
            # Unknown feature: pass-through without scaling
            scaled[name] = float(value)
            continue
        scaled[name] = scaler.scale(float(value))
    return scaled


def _one_hot(prefix: str, hot_index: int) -> Dict[str, int]:
    ohe: Dict[str, int] = {}
    for node_id in VALID_NODE_IDS:
        key = f"{prefix}_{node_id}"
        ohe[key] = 1 if node_id == hot_index else 0
    return ohe


def detect_current_host_with_app_metrics(node_metrics_map: Dict) -> Optional[str]:
    """
    Infer the current host by finding the node bucket that contains torchserve metrics.
    Returns the node name, or None if not found.
    """
    torchserve_metric_names = {
        "kepler:container_torchserve_cpu_rate:1m",
        "kepler:container_torchserve_watt:1m",
        "kepler:container_torchserve_joules:1m",
        "ts:latency:1m:ms",
        "ts:throughput:1m:rps",
    }
    for node_name, bucket in node_metrics_map.items():
        if node_name == "":
            continue
        metrics_list = (bucket or {}).get("metrics", []) or []
        names_in_bucket = {m.get("name") for m in metrics_list if isinstance(m, dict)}
        if torchserve_metric_names & names_in_bucket:
            return node_name
    return None


def build_feature_rows_from_payload(
    payload: Dict,
    current_host_name: Optional[str],
    node_name_to_id: Dict[str, int],
    target_node_ids: Iterable[int] | None = None,
) -> pd.DataFrame:
    """
    Convert a Load Watcher payload into a feature matrix with one row per target node.
    """
    node_metrics_map = payload.get("data", {}).get("NodeMetricsMap", {}) or {}

    # Determine current host if not provided
    host_name = current_host_name or detect_current_host_with_app_metrics(node_metrics_map)
    if not host_name:
        raise ValueError("Unable to determine current_host from payload; please provide it explicitly.")

    # Base features from app-level metrics and the selected source node
    base_app = _extract_app_metrics(node_metrics_map, host_name)
    base_node = _extract_node_metrics_for(node_metrics_map, host_name)
    raw_base = {**base_app, **base_node}
    scaled_base = _minmax_scale_features(raw_base)

    # One-hot of source id
    src_id = node_name_to_id.get(host_name)
    if src_id is None:
        raise ValueError(f"Unknown current_host_name '{host_name}' for provided node_name_to_id mapping")
    src_ohe = _one_hot("node_id_src", src_id)

    # Build one row per target candidate
    rows: List[Dict[str, float]] = []
    for tgt_id in (target_node_ids or VALID_NODE_IDS):
        tgt_ohe = _one_hot("node_id_tgt", int(tgt_id))
        row = {**scaled_base, **src_ohe, **tgt_ohe}
        rows.append(row)

    df = pd.DataFrame(rows)
    # Reorder columns to match model training
    feature_order = get_feature_order()
    # Ensure any missing columns are added as zeros (defensive)
    for col in feature_order:
        if col not in df.columns:
            df[col] = 0
    df = df[feature_order]
    return df
