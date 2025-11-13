# ML-Agent

This agent will contain the models and inference pipeleline (preprocessing + inference) for the project.

Two main agent types, chose by config file:
- A1: Node translation.
    Translates current metrics from Node A to Node B.
- A2: App status prediction:
    - A2': app future state prediction with timeseries.
    - A2'': impact of that app state into node metrics.

Each agent type will be deployed in a different place - A1 at node level, A2 might follow app-. 