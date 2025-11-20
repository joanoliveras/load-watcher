from __future__ import annotations

import logging
import json
import time
from typing import Dict, List, Tuple

import httpx

from app import metrics
from app.config import Settings

LOGGER = logging.getLogger(__name__)


def fetch_snapshot(client: httpx.Client, url: str) -> Dict[str, object]:
    response = client.get(url)
    response.raise_for_status()
    data: Dict[str, object] = response.json()
    return data


def request_predictions(client: httpx.Client, url: str, payload: Dict[str, object]) -> Dict[str, object]:
    response = client.post(url, json=payload)
    response.raise_for_status()
    data: Dict[str, object] = response.json()
    return data


def parse_predictions(
    response: Dict[str, object]
) -> Tuple[List[str], Dict[int, str], Dict[int, List[float]], str]:
    columns = [str(col) for col in response.get("columns", [])]  # type: ignore[arg-type]
    target_map_raw = response.get("target_map", {}) or {}
    target_map: Dict[int, str] = {int(k): str(v) for k, v in target_map_raw.items()}
    predictions_raw = response.get("predictions", {}) or {}
    predictions: Dict[int, List[float]] = {
        int(k): [float(x) for x in v] for k, v in predictions_raw.items()
    }
    source_host = str(response.get("source_host", ""))
    return columns, target_map, predictions, source_host


def run(settings: Settings) -> None:
    LOGGER.info("Starting orchestrator with %ss interval.", settings.poll_interval_seconds)
    metrics.start_metrics_server(
        bind_address=settings.metrics_bind_address,
        port=settings.metrics_port,
    )

    with httpx.Client(timeout=settings.request_timeout_seconds) as client:
        while True:
            cycle_start = time.perf_counter()
            try:
                snapshot = fetch_snapshot(client, settings.load_watcher_url)
                _log_snapshot(snapshot)
                # TODO: Persist snapshots to shared storage once long-term retention is required.

                prediction_response = request_predictions(client, settings.ml_agent_url, snapshot)
                columns, target_map, predictions, source_host = parse_predictions(prediction_response)
                metrics.publish_predictions(
                    source_host=source_host,
                    target_map=target_map,
                    columns=columns,
                    predictions=predictions,
                )
                metrics.record_cycle_success()
                LOGGER.info(
                    "Published %d predictions (source_host=%s).",
                    len(predictions),
                    source_host or "unknown",
                )
            except Exception:
                metrics.record_cycle_failure()
                LOGGER.exception("Cycle failed.")

            sleep_for = max(0.0, settings.poll_interval_seconds - (time.perf_counter() - cycle_start))
            if sleep_for > 0:
                time.sleep(sleep_for)


def _log_snapshot(snapshot: Dict[str, object], limit: int = 2048) -> None:
    serialized = json.dumps(snapshot, sort_keys=True)
    if len(serialized) > limit:
        serialized = f"{serialized[:limit]}... (truncated {len(serialized) - limit} chars)"
    LOGGER.debug(
        "Snapshot captured bytes=%s payload=%s",
        len(serialized.encode("utf-8")),
        serialized,
    )

