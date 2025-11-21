## GreenAnalyse Agent Platform

GreenAnalyse Agent is composed of three cooperating services:
- load-watcher (Go): collects node- and app-level runtime metrics from providers (Prometheus, Kubernetes Metrics Server, SignalFx, Datadog) and exposes them via HTTP and Prometheus.
- ml-agent (Python): consumes metrics, performs preprocessing and forecasting using configured ML models, and exports predictions.
- orchestrator (Python): consumes current metrics and predictions to drive scheduling or control-plane decisions.

### Repository layout
- `load-watcher/` — Go module providing metrics collection and the Watcher HTTP service
- `ml-agent/` — Python service for ML-based forecasting
- `orchestrator/` — Python service coordinating actions based on metrics and forecasts
- `CHANGELOG.md`, `LICENSE`, `CODEOWNERS` — repository meta
- `docs/` — design and architecture documentation

### Data flow and interfaces
- Metrics ingestion (load-watcher):
  - Providers: Prometheus, K8s Metrics Server, SignalFx, Datadog
  - HTTP API: `GET /watcher` returns the latest snapshot of aggregated metrics (15m window by default)
  - Health: `GET /watcher/health`
  - Prometheus: `/metrics` endpoint publishes gauges per host/metric/operator/window
- Predictions (ml-agent):
  - Reads metrics (directly or via exporters)
  - Runs preprocessing/transforms and forecasting (e.g., A1 ML model)
  - Exports predictions (e.g., to Prometheus or files/endpoints, depending on config)
- Orchestration:
  - Reads predictions and current state
  - Applies policies to affect schedulers, auto-scaling or other control loops

See `docs/ARCHITECTURE.md` for diagrams, data contracts, and example payloads.

### Getting started
1) load-watcher
- Build and run
  - cd `load-watcher/`
  - `docker build -t load-watcher:local .`
  - Configure env vars (examples):
    - `METRICS_PROVIDER_NAME` in {KubernetesMetricsServer, Prometheus, SignalFx, Datadog}
    - `METRICS_PROVIDER_ADDRESS`, `METRICS_PROVIDER_TOKEN` (as required)
    - Optional: `WATCH_POD_REGEX`, `WATCH_GREENANALYSE`, `WATCH_INCLUDE_TS`, `WATCH_INCLUDE_USERS`
  - Deploy: `kubectl apply -f load-watcher/manifests/load-watcher-deployment.yaml`

2) ml-agent
- See `ml-agent/README.md` for local run, configuration, and deployment details

3) orchestrator
- See `orchestrator/README.md` for configuration and deployment

### Development
- Go (load-watcher)
  - Module lives in `load-watcher/`
  - Run unit tests with `go test ./...` from within `load-watcher/`
- Python (ml-agent and orchestrator)
  - Use `python -m venv .venv && source .venv/bin/activate`
  - Install requirements from corresponding `requirements.txt`
  - Run unit tests via `pytest`

### Contributing
Please read `CONTRIBUTING.md` and `CODE_OF_CONDUCT.md` before opening PRs. Security disclosures: see `SECURITY.md`.


