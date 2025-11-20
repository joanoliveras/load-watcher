# Orchestrator

The orchestrator is the glue between `load-watcher` (observed metrics) and `ml-agent` (predicted metrics). It runs inside the same pod as the other containers and performs the following loop:

1. Fetch the latest snapshot from `load-watcher`’s `/watcher` endpoint.
2. Log the full snapshot payload (future work may persist it for retraining).
3. Send the payload to `ml-agent`’s `/predict` endpoint.
4. Export the returned predictions as Prometheus gauges (one time series per
   `target-host:feature`), plus a couple of basic health metrics.

The service is intentionally stateless for now; once long-term retention is required we can plug in a snapshot sink.

## Configuration

Environment variables (all prefixed with `ORCH_`):

| Variable | Default | Description |
| --- | --- | --- |
| `LOAD_WATCHER_URL` | `http://load-watcher:2020/watcher` | URL used to fetch observed metrics. |
| `ML_AGENT_URL` | `http://ml-agent:8080/predict` | Inference endpoint. |
| `POLL_INTERVAL_SECONDS` | `60` | How often to run the pipeline. |
| `REQUEST_TIMEOUT_SECONDS` | `15` | HTTP timeout for both clients. |
| `METRICS_PORT` | `9105` | Port used by the embedded Prometheus HTTP server. |
| `METRICS_BIND_ADDRESS` | `0.0.0.0` | Bind address for the metrics exporter. |

## Local development

```bash
cd orchestrator
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python -m app.main
```

## Container image

```bash
docker build -t orchestrator:latest -f orchestrator/Dockerfile orchestrator
```

The resulting image listens on the configured `METRICS_PORT`. When deployed inside the A1 Agent pod, create a shared volume for `SNAPSHOT_DIR` if you want the files persisted across restarts (otherwise an `emptyDir` works for short-term retention).

