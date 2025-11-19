# ML-Agent

This agent will contain the models and inference pipeleline (preprocessing + inference) for the project.

Two main agent types, chose by config file:
- A1: Node translation.
    Translates current metrics from Node A to Node B.
- A2: App status prediction:
    - A2': app future state prediction with timeseries.
    - A2'': impact of that app state into node metrics.

Each agent type will be deployed in a different place - A1 at node level, A2 might follow app-. 

## Local test

1) Install dependencies:

```bash
pip install -r /home/rocky/k8s_resources/load-watcher/ml-agent/requirements.txt
```

2) Run the API:

```bash
python -m app.main
```

3) Send a request with a Load Watcher JSON payload. The agent infers the current host by checking which node bucket contains torchserve metrics:

```bash
curl -X POST "http://localhost:8080/predict" \
  -H "Content-Type: application/json" \
  --data-binary @payload.json
```

Response:

```json
{
  "predictions": {
    "1": [ ... ],
    "2": [ ... ],
    "3": [ ... ],
    "4": [ ... ]
  }
}
```

Environment overrides:
- `ML_AGENT_MODEL_PATH`: path to the sklearn model `.pkl`. Defaults to the packaged model under `app/models/A1/MLP/`.
- `ML_AGENT_NODE_MAP`: override node-name→id mapping, e.g. `name1:1,name2:2,name3:3,name4:4`.
- `ML_AGENT_PORT`: default 8080.

## Container image

Build the image:

```bash
docker build -t ml-agent:latest -f /home/rocky/k8s_resources/load-watcher/ml-agent/Dockerfile /home/rocky/k8s_resources/load-watcher/ml-agent
```

Run locally:

```bash
docker run --rm -p 8080:8080 ml-agent:latest
```

## Kubernetes deployment

1) Push the image to a registry your cluster can pull from (replace image name in the manifest).
2) Apply the manifest:

```bash
kubectl apply -f /home/rocky/k8s_resources/load-watcher/ml-agent/manifests/ml-agent-deployment.yaml
```

This deploys:
- Deployment `ml-agent` (1 replica) exposing port 8080
- Service `ml-agent` (ClusterIP) on port 8080
- Liveness/readiness probes at `/healthz`

You can port-forward to test:

```bash
kubectl -n default port-forward svc/ml-agent 8080:8080
```

Then call `/predict` as in the local steps.