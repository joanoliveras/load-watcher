## Architecture

### Overview
GreenAnalyse Agent is a modular system:
- load-watcher collects metrics and exposes them via HTTP and Prometheus.
- ml-agent performs forecasting based on metrics and model configuration.
- orchestrator applies decisions based on observed and forecasted signals.

### Components
1) load-watcher (Go)
- Providers: Prometheus, Kubernetes Metrics Server, SignalFx, Datadog
- Periodic collection windows: 15m (primary), 10m, 5m cache fallback
- HTTP API:
  - `GET /watcher` → latest snapshot
  - `GET /watcher?host=<node>` → host-scoped metrics
  - `GET /watcher/health` → provider health
- Prometheus Exporter:
  - `/metrics` exposes gauges by labels: host, name, type, operator, window

2) ml-agent (Python)
- Ingests metrics (direct API call or exporter scraping)
- Preprocessing and transforms (see `ml-agent/app/preprocessing/`)
- Model execution (e.g., A1/MLP multi-output)
- Export predictions (Prometheus or other targets)

3) orchestrator (Python)
- Subscribes to predictions + metrics
- Applies rules/policies to influence schedulers, autoscalers, or external systems

### Data Contracts
- load-watcher response (simplified):
```
{
  "timestamp": 1730000000,
  "window": { "duration": "15m", "start": 1729999100, "end": 1730000000 },
  "source": "Prometheus",
  "data": {
    "node-1": {
      "metrics": [
        { "name": "instance:node_cpu:ratio", "type": "CPU", "operator": "AVG", "rollup": "15m", "value": 0.23 }
      ]
    }
  }
}
```

### Deployment
- Each component ships its own `Dockerfile` and `manifests/`.
- Typical flow:
  - Deploy load-watcher first (ensuring provider connectivity and `/watcher` is healthy).
  - Deploy ml-agent and orchestrator next.

### Extensibility
- Add a new load-watcher provider: implement `MetricsProviderClient` (see `load-watcher/pkg/watcher/internal/metricsprovider/`).
- Extend ml-agent models: add to `ml-agent/app/models/` and wire in `forecasting/run.py`.
- Orchestrator: add new policies or actions in `orchestrator/app/`.


