from __future__ import annotations

import time
from typing import Dict, List, Sequence

from prometheus_client import Counter, Gauge, start_http_server

PREDICTED_GAUGE = Gauge(
    "loadwatcher_predicted_value",
    "Predicted metric produced by ml-agent.",
    labelnames=("metric", "source_host"),
)

CYCLE_FAILURES = Counter(
    "orchestrator_cycle_failures_total",
    "Number of orchestrator cycles that ended in failure.",
)

LAST_SUCCESS = Gauge(
    "orchestrator_last_success_timestamp_seconds",
    "Unix epoch timestamp for the most recent successful cycle.",
)


def start_metrics_server(bind_address: str, port: int) -> None:
    start_http_server(port, addr=bind_address)


def record_cycle_success() -> None:
    LAST_SUCCESS.set(time.time())


def record_cycle_failure() -> None:
    CYCLE_FAILURES.inc()


def publish_predictions(
    *,
    source_host: str,
    target_map: Dict[int, str],
    columns: Sequence[str],
    predictions: Dict[int, List[float]],
) -> None:
    for target_id, values in predictions.items():
        column_count = len(columns)
        target_host = target_map.get(int(target_id), str(target_id))
        for idx, value in enumerate(values):
            column_name = columns[idx] if idx < column_count else f"y_{idx}"
            metric_label = f"{target_host}:{column_name}"
            PREDICTED_GAUGE.labels(metric=metric_label, source_host=source_host).set(value)

