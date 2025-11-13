"""
API for the ml-agent.
Exposes the API for the ml-agent to Prometheus and K8s.

/metrics: The Prometheus server scrapes this HTTP endpoint to collect your agent’s metrics (e.g., predicted_). api.py just exposes the Prometheus client’s registry over HTTP.
/healthz: Kubernetes liveness/readiness probes hit this endpoint to decide if the pod is healthy and ready (e.g., you can return 200 only if the last collect→forecast succeeded recently).
"""