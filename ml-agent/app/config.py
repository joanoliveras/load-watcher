from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Dict, List, Tuple


@dataclass(frozen=True)
class FeatureScaleRange:
    minimum: float
    maximum: float

    def scale(self, value: float) -> float:
        # Guard against degenerate ranges
        denom = self.maximum - self.minimum
        if denom == 0:
            return 0.0
        scaled = (value - self.minimum) / denom
        # Clamp to [0, 1]
        if scaled < 0.0:
            return 0.0
        if scaled > 1.0:
            return 1.0
        return scaled


# Min/Max values provided for the scaler
FEATURE_RANGES: Dict[str, FeatureScaleRange] = {
    "torchserve_app_user": FeatureScaleRange(1.0, 55.0),
    "torchserve_node_cpu_src": FeatureScaleRange(74.66666666666667, 9726.333333333334),
    "torchserve_node_energy_src": FeatureScaleRange(1263.1578947368396, 15599.999999999967),
    "torchserve_node_power_src": FeatureScaleRange(20.999999999998423, 419.0000000000015),
    "torchserve_app_cpu_src": FeatureScaleRange(52.0, 9552.333333333334),
    "torchserve_app_energy_src": FeatureScaleRange(18.947368421052648, 7411.578947368422),
    "torchserve_app_power_src": FeatureScaleRange(1.0000000000000009, 145.99999999999991),
    "torchserve_app_latency_src": FeatureScaleRange(55.27002162500006, 917.3476638071452),
    "torchserve_app_qps_src": FeatureScaleRange(1.6666666666666667, 98.66666666666669),
}


# Node identity configuration: map Kubernetes node names to stable 1..4 IDs
# Default ordering follows the previously used list in the project.
HOSTNAME_LIST_DEFAULT: List[str] = [
    "cloudskin-k8s-edge-worker-1.novalocal",
    "cloudskin-k8s-control-plane-0.novalocal",
    "cloudskin-k8s-edge-worker-0.novalocal",
    "cloudskin-k8s-edge-worker-2.novalocal",
]
NODE_NAME_TO_ID_DEFAULT: Dict[str, int] = {
    name: i + 1 for i, name in enumerate(HOSTNAME_LIST_DEFAULT[:4])
}
VALID_NODE_IDS: List[int] = [1, 2, 3, 4]


def get_model_path() -> str:
    return os.environ.get(
        "ML_AGENT_MODEL_PATH",
        "/app/app/models/A1/MLP/mlp_multioutput_scoredpairs_scaled_onehotencoded.pkl",
    )


def get_feature_order() -> List[str]:
    """
    The exact input column order expected by the MLP model.
    """
    base_features = [
        "torchserve_app_user",
        "torchserve_node_cpu_src",
        "torchserve_node_energy_src",
        "torchserve_node_power_src",
        "torchserve_app_cpu_src",
        "torchserve_app_energy_src",
        "torchserve_app_power_src",
        "torchserve_app_latency_src",
        "torchserve_app_qps_src",
    ]
    src_ohe = [f"node_id_src_{i}" for i in VALID_NODE_IDS]
    tgt_ohe = [f"node_id_tgt_{i}" for i in VALID_NODE_IDS]
    return base_features + src_ohe + tgt_ohe


def get_node_name_to_id_override() -> Dict[str, int]:
    """
    Optionally override node mapping via env vars:
      ML_AGENT_NODE_MAP=name1:1,name2:2,name3:3,name4:4
    """
    raw = os.environ.get("ML_AGENT_NODE_MAP")
    if not raw:
        return NODE_NAME_TO_ID_DEFAULT
    mapping: Dict[str, int] = {}
    for token in raw.split(","):
        if ":" not in token:
            continue
        name, id_str = token.split(":", 1)
        try:
            node_id = int(id_str)
        except ValueError:
            continue
        if node_id in VALID_NODE_IDS and name:
            mapping[name] = node_id
    # Fallback to defaults if parsing failed
    return mapping or NODE_NAME_TO_ID_DEFAULT
