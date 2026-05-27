<div align="right">

[**中文**](SDK_GUIDE_CN.md) | **English**

</div>

# Algorithm SDK Guide

## What is the Algorithm SDK

The Algorithm SDK is the Python interface layer for the OpenTraffic traffic signal control engine. It provides a unified API to invoke adaptive signal control algorithms with just a few lines of code.

---

## Installation

```bash
pip install .
```

Requirements: Python >= 3.8, Linux x86_64.

---

## Quick Start

```python
from algorithms_sdk import AlgorithmSDK

# 1. Create SDK (simulation mode)
sdk = AlgorithmSDK(
    mode="cityflow",
    config_path="config/test_cityflow.json",
    algo_version="v1"
)

# 2. Prepare vehicle data
state = {
    "XML_CNL": {
        "XML_CNL_N_0": ["v1", "v2"],
        "XML_CNL_W_1": ["v3"]
    }
}
sdk._adapter.set_vehicles({
    "v1": {"speed": 5.0, "running": "1"},
    "v2": {"speed": 3.0, "running": "1"},
    "v3": {"speed": 0.0, "running": "0"}
})

# 3. Prepare signal controller state
env_state = {
    "phases": [1, 2],
    "currentPhase": 1,
    "phaseTime": 30,
    "currentPlan": "1",
    "timestamp": 1700000000
}

# 4. Get phase decision
result = sdk.step(state, env_state)
print(f"Phase: {result.action.phase}, Latency: {result.inference_time_ms:.2f}ms")

# 5. Clean up
sdk.close()
```

---

## API Reference

### Constructor

```python
sdk = AlgorithmSDK(
    mode="cityflow",            # "cityflow" | "production"
    config_path=None,           # Intersection config file
    mq_config_path=None,        # Redis config (production only)
    algo_version="v1",          # Algorithm version
    logger=None,                # Custom log function
)
```

### step() — Execute one decision

```python
result = sdk.step(state, env_state)
# result.action.phase          → "phase1"
# result.action.phase_index     → 0
# result.inference_time_ms      → 12.5
# result.timestamp              → 1700000000.0
```

### get_metrics() — Performance metrics

```python
m = sdk.get_metrics()
m.total_decisions          # Total decisions
m.successful_decisions     # Successful decisions
m.failed_decisions         # Failed decisions
m.avg_inference_time_ms   # Average inference time (ms)
```

### get_health_status() — Health check

```python
h = sdk.get_health_status()
h.is_healthy              # Is healthy
h.memory_usage_mb         # Memory usage (MB)
h.error_count             # Error count
```

### reset() / close()

```python
sdk.reset()   # Reset statistics
sdk.close()   # Release resources
```

---

## Data Formats

### Input: state (vehicle data)

CityFlow format (simulation mode):

```python
state = {
    "intersection_id": {
        "lane_id": ["vehicle_id1", "vehicle_id2"],
    }
}
```

### Input: env_state (signal controller state)

```python
env_state = {
    "phases": [1, 2],          # Available phases
    "currentPhase": 1,          # Current phase
    "phaseTime": 30,            # Elapsed time (seconds)
    "currentPlan": "1",         # Current plan
    "timestamp": 1700000000
}
```

### Return: DecisionResult

```python
@dataclass
class DecisionResult:
    action: PhaseAction          # Decision action (phase, phase_index, confidence)
    timestamp: float            # Timestamp
    inference_time_ms: float    # Inference time (ms)
    algorithm_version: str       # Algorithm version
```

---

## Production Mode

Connect to Redis middleware to work with real signal controllers:

```python
sdk = AlgorithmSDK(
    mode="production",
    mq_config_path="config/mq_config.json",
    config_path="config/test_net.json"
)
sdk.start_auto_run()  # Auto-listen to Redis and output decisions
```

---

## FAQ

**Q: "No module named 'algorithms'" error**

Run scripts from the project root directory, and make sure `pip install .` has been executed.

**Q: step() returns None**

A safety rule rejected the current decision. Check that your input data format is correct.

**Q: How to switch algorithm versions**

Change the `algo_version` field in the config file.

**Q: License verification failed**

Verify system time is correct, or contact the developer.
