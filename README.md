<div align="center">

[![License](https://img.shields.io/badge/License-Apache%202.0-blue.svg?style=for-the-badge)](LICENSE)
[![Python](https://img.shields.io/badge/Python-3.8+-green.svg?style=for-the-badge&logo=python&logoColor=white)](https://www.python.org/)
[![Platform](https://img.shields.io/badge/Platform-Linux%20x86__64-orange.svg?style=for-the-badge&logo=linux&logoColor=white)]()
[![GitHub Stars](https://img.shields.io/github/stars/OpenTraffic-Team/opentraffic-tsc-engine?style=for-the-badge&logo=github&logoColor=white)](https://github.com/OpenTraffic-Team/opentraffic-tsc-engine)

</div>

### OpenTraffic — 面向智能交通信号控制的开源 SDK。
<br/>

> **GitHub: https://github.com/OpenTraffic-Team/opentraffic-tsc-engine**

<br/>

## 🌟 目录

- [:rocket: 快速开始](#rocket-快速开始)
  - [环境要求](#环境要求)
  - [安装依赖](#安装依赖)
  - [安装 CityFlow（可选）](#安装-cityflow可选)
- [:pencil: 配置说明](#pencil-配置说明)
  - [路口配置](#路口配置)
  - [CityFlow 引擎配置](#cityflow-引擎配置)
  - [Redis / MQ 配置](#redis--mq-配置)
- [:fire: 运行模式](#fire-运行模式)
  - [:ledger: 模式一 — 最简测试（无外部依赖）](#ledger-模式一--最简测试无外部依赖)
  - [:ledger: 模式二 — CityFlow 仿真](#ledger-模式二--cityflow-仿真)
  - [:ledger: 模式三 — Redis 生产模式](#ledger-模式三--redis-生产模式)
- [:mechanical_arm: SDK 使用](#mechanical_arm-sdk-使用)
  - [:books: API 参考](#books-api-参考)
  - [:notebook: 输入/输出格式](#notebook-输入输出格式)
- [:hammer_and_wrench: 编译部署](#hammer_and_wrench-编译部署)
- [:question: 常见问题](#question-常见问题)
- [:heart: 致谢](#heart-致谢)

<br/>

## :rocket: 快速开始

### 环境要求

- **操作系统**: Linux x86_64
- **Python**: >= 3.8

### 安装依赖

```bash
# 克隆项目
git clone https://github.com/OpenTraffic-Team/opentraffic-tsc-engine
cd opentraffic-tsc-engine

# 核心依赖（必装）
pip install numpy scipy scikit-learn redis psutil PyYAML Cython

# PyTorch（算法模型需要）
pip install torch --index-url https://download.pytorch.org/whl/cpu
```

### 安装 CityFlow（可选）

```bash
# 源码安装（项目已内置 CityFlow）
cd CityFlow
pip install .
```

> 详细安装步骤见 [INSTALL.md](INSTALL.md)

<br/>

## :pencil: 配置说明

### 路口配置

路口配置文件（如 `config/test_cityflow.json` 或 `config/test_net.json`）定义了信号控制参数：

| 字段 | 类型 | 说明 |
|--------|------|------|
| `cur_inter_id` | string | 路口标识，如 `"XML_CNL"` |
| `lane_to_phase` | dict | 车道到相位映射 |
| `phases` | list | 可用相位名称列表 |
| `stagePhase` | dict | 相位编号 → 名称映射 |
| `phase_min_change_time` | dict | 各相位最小绿灯时间（秒） |
| `phase_max_keep_time` | dict | 各相位最大绿灯时间（秒） |
| `algo_version` | string | 算法版本（`"v1"`） |
| `cityflowTest` | int | CityFlow 测试标记（0/1） |
| `debug` | bool | 调试模式 |
| `morning_rush` / `evening_rush` | list | 高峰时段 |

### CityFlow 引擎配置

位于 `config/cityflow/`：

```
config/cityflow/
├── algo_config.yaml     # 算法参数
├── config.json          # CityFlow 引擎参数
├── roadnet.json         # 路网定义
└── flow.json            # 车流定义（由脚本自动生成）
```

### Redis / MQ 配置

编辑 `config/mq_config.json` 配置生产模式 Redis 连接：

```json
{
    "redis_addr": "<Redis 服务器 IP>",
    "redis_port": 6379,
    "redis_password": "<密码>",
    "intersection": "HHL_QHDD",
    "redis_keys": {
        "origin_state":       {"prefix": "origin_info_state", "db": 1},
        "env_state":          {"prefix": "signal_env_state",  "db": 0},
        "algorithm_control":  {"prefix": "algorithm_control", "db": 0},
        "signal_config":      {"prefix": "signalConfig",      "db": 0},
        "alg_config":         {"prefix": "algConfig",         "db": 0},
        "sensor_config":      {"prefix": "sensorConfig",      "db": 0},
        "hardware_config":    {"prefix": "intersection_device","db": 0}
    }
}
```

<br/>

## :fire: 运行模式

### :books: 相关文件
* `test_simple.py` — 最简算法测试（无外部依赖）
* `test_sdk_cityflow.py` — CityFlow 集成仿真测试
* `run_algorithms_real.py` — 生产模式算法主程序

### :ledger: 模式一 — 最简测试（无外部依赖）

***适用场景：快速验证算法逻辑，无需任何外部服务。***

```bash
python test_simple.py
```

使用合成数据运行算法 — 无需 CityFlow，无需 Redis。

### :ledger: 模式二 — CityFlow 仿真

***适用场景：完整的 CityFlow 交通仿真，支持可视化回放。***

```bash
# 运行 3600 步自适应算法仿真
python test_sdk_cityflow.py

# 自定义步数
python test_sdk_cityflow.py --steps 600

# 固定配时对比模式
python test_sdk_cityflow.py --fixed
```

仿真结束后，用浏览器打开 `frontend/index.html` 上传回放文件即可查看。

> 未安装 CityFlow 时会自动使用内置 Mock 引擎，用于纯算法逻辑验证。

### :ledger: 模式三 — Redis 生产模式

***适用场景：模拟真实生产环境，通过 Redis Stream 传输数据。***

**架构：**

```
┌──────────────────────────┐      ┌─────────────────┐
│ signal_env_simulator.py  │ ──→  │                 │
│ (模拟信号机推送状态)        │      │   Redis Stream  │
└──────────────────────────┘      │                 │
                                  │  origin_info_   │
┌──────────────────────────┐      │  state:xxx      │
│ fake_push.py             │ ──→  │  signal_env_    │
│ (模拟传感器数据推送)        │      │  state:xxx      │
└──────────────────────────┘      │  algorithm_     │
                                  │  control:xxx    │
┌──────────────────────────┐      │                 │
│ run_algorithms_real.py   │ ←──→ │                 │
│ (算法主程序)               │      └─────────────────┘
└──────────────────────────┘
```

**步骤：**

```bash
# 1. 初始化 Redis 配置（仅首次）
python real_test/setup_redis_config.py

# 2. 启动信号机模拟器
python real_test/signal_env_simulator.py

# 3. （可选）推送假算法数据
python real_test/fake_push.py --phase 2

# 4. 启动算法主程序
python run_algorithms_real.py
```

<br/>

## :mechanical_arm: SDK 使用

### :books: API 参考

SDK 提供两层 API：

| 层级 | 类 | 适用场景 |
|------|-----|----------|
| 高层 | `AlgorithmSDK` | 统一接口，自动适配不同模式 |
| 底层 | `AdvancedControl` | 直接调用，支持 `test=True` 本地测试 |

**方式一：AlgorithmSDK（推荐）**

```python
from algorithms_sdk import AlgorithmSDK

# 仿真模式
sdk = AlgorithmSDK(
    mode="cityflow",
    config_path="config/test_cityflow.json",
    algo_version="v1"
)

# 执行决策
result = sdk.step(state, env_state)

# 查看指标
metrics = sdk.get_metrics()

# 健康检查
health = sdk.get_health_status()

# 关闭
sdk.close()
```

**方式二：AdvancedControl 直接调用**

```python
from algorithms_sdk.advanced_control import AdvancedControl

# test=True：本地测试，不连接 Redis
algo = AdvancedControl(
    test=True,
    config_path="config/test_net.json"
)

# 执行决策
phase = algo.take_action(state, env_state)

# 生产模式（连接 Redis）
# algo = AdvancedControl(mq_path="config/mq_config.json")
# phase = algo.take_action_to_redis()
```

### :notebook: 输入/输出格式

**state（车辆数据）** — 支持两种格式：

<details>
<summary><b>格式一：CityFlow 仿真格式</b></summary>

```python
state = {
    "HHL_QHDD": {
        "HHL_QHDD_N_0": ["v1", "v2"],
        "HHL_QHDD_N_1": [],
        "HHL_QHDD_S_0": ["v4"],
    }
}
vehicles = {
    "v1": {"speed": 5.0, "running": "1"},
    "v2": {"speed": 3.0, "running": "1"},
}
```
</details>

<details>
<summary><b>格式二：生产环境格式</b>（recognitionSnap 传感器数据）</summary>

```python
state = {
    "XML_CNL": {
        "cameraState": {},
        "sensor_status": {"tirStatus[road_1]": {}, ...},
        "recognitionSnap[road_1]": {
            "timestamp": 1700000000,
            "vehicles": [
                {"id": "v1", "lane": "XML_CNL_N_0", "speed": [5.0], "type": "vehicle"}
            ]
        },
    }
}
```
</details>

**env_state（信号机状态）**

```python
env_state = {
    "phases": [1, 2],               # 可用相位编号
    "currentPhase": 1,              # 当前相位编号
    "phaseTime": 30,                # 当前相位已运行时间（秒）
    "currentPlan": "1",             # 当前方案
    "signalCtlStatus": True,        # 信号机是否在控
    "timestamp": 1700000000.0
}
```

**返回值**

```python
# take_action() 返回值：
phase = 1       # 正常决策：相位编号
phase = None    # 安全规则未通过 或 异常检测触发

# AlgorithmSDK.step() 返回值：
@dataclass
class DecisionResult:
    action: PhaseAction        # 决策动作
    timestamp: float           # 时间戳
    inference_time_ms: float   # 推理耗时（毫秒）
    algorithm_version: str     # 算法版本
```

<br/>

## :hammer_and_wrench: 编译部署

```bash
cd build
bash build.sh          # x86_64 编译，生成 algorithms.tar.gz
bash build_arm.sh      # ARM64 交叉编译
```

<br/>

## :question: 常见问题

<details>
<summary><b>SO 文件加载失败？</b></summary>

```bash
uname -m                          # 应输出 x86_64
python -c "import struct; print(struct.calcsize('P')*8)"  # 应输出 64
```
</details>

<details>
<summary><b>许可证校验失败？</b></summary>

检查系统时间是否正确，确认算法文件有效性。
</details>

<details>
<summary><b>CityFlow 未安装？</b></summary>

运行 `test_sdk_cityflow.py` 时自动切换到 Mock 引擎模式。
</details>

<details>
<summary><b>Redis 连接失败？</b></summary>

```bash
python -c "import redis; r=redis.Redis(host='<IP>', port=6390, password='<PWD>'); print(r.ping())"
```
</details>

<br/>

## :heart: 致谢

感谢 [CityFlow](https://github.com/cityflow-project/CityFlow) 提供的开源交通仿真平台！

</div>
