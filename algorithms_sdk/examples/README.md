<div align="right">

[**中文**](README_CN.md) | **English**

</div>

# Algorithm SDK Examples

Complete usage examples for the Algorithm SDK.

## Example List

| File | Description | Mode |
|------|------|------|
| `quick_demo.py` | Quick start: dynamic vehicle simulation + real-time phase decisions | Simulation |
| `simulation_demo.py` | Batch simulation with statistics and analysis | Simulation |
| `production_demo.py` | Production environment configuration and connection | Production |
| `real_algo_runner.py` | Long-running simulation runner | Simulation |

## Quick Start

```bash
# Getting started — dynamic vehicle simulation
python algorithms_sdk/examples/quick_demo.py

# Basics — batch simulation
python algorithms_sdk/examples/simulation_demo.py

# Production environment check
python algorithms_sdk/examples/production_demo.py --check
```

## Examples in Detail

### quick_demo.py

Dynamic vehicle simulation, ~90 seconds real-time runtime. Covers:

- SDK initialization (simulation mode)
- Dynamic vehicle flow simulation (NS/EW traffic varies over time)
- Real-time phase decisions and switching
- Performance statistics (total decisions, success rate, avg latency)
- Phase distribution analysis

```bash
python algorithms_sdk/examples/quick_demo.py
```

### simulation_demo.py

Batch simulation workflow (default 20 steps). Covers:

- Multi-step simulation loop
- Metric collection and statistics
- Phase distribution analysis
- Health status checks

```bash
python algorithms_sdk/examples/simulation_demo.py
# To change step count: edit run_simulation(num_steps=100)
```

### production_demo.py

Production environment connection example. Covers:

- Redis configuration check
- Production-mode SDK initialization
- Manual step invocation
- Health monitoring

```bash
# Check environment only
python algorithms_sdk/examples/production_demo.py --check

# Run demo (requires Redis connection)
python algorithms_sdk/examples/production_demo.py
```

## FAQ

### Q: "Config file not found" error

Make sure you're running from the project root:

```bash
cd /path/to/OpenTraffic
python algorithms_sdk/examples/quick_demo.py
```

### Q: How to switch algorithm versions

```python
sdk = AlgorithmSDK(mode="cityflow", algo_version="v1", config_path="config/test_cityflow.json")
```

### Q: How to use custom logging

```python
def my_logger(msg):
    import logging
    logging.info(msg)

sdk = AlgorithmSDK(mode="cityflow", logger=my_logger, config_path="config/test_cityflow.json")
```
