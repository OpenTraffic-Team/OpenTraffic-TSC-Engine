<div align="right">

**中文** | [**English**](README_EN.md)

</div>

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

# 一键安装（Python 包 + 所有依赖）
pip install .
```

> PyTorch 默认安装 CPU 版。如需 GPU 版，先执行 `pip install torch --index-url https://download.pytorch.org/whl/cu118`

### 安装 CityFlow（可选）

参考 [CityFlow 官方安装指南](https://cityflow.readthedocs.io/en/latest/install.html) 自行安装。

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

> **关键流程**：原始传感器数据（`recognitionSnap` / CityFlow lane 格式）**必须先经过特征提取转换**为 `vehicle_map` 格式，才能被算法消费。算法内部的 `AdvancedV1.algorithm_control()` 直接读取 `vehicle_map["waiting_vehicle"]` 和 `vehicle_map["running_vehicle"]`，跳过转换会导致 `KeyError`。

---

#### 数据转换管线

```
原始传感器数据                       特征提取转换                          算法输入
────────────────────────────────────────────────────────────────────────────────────

[生产环境] recognitionSnap 格式
{intersection_id: {
  recognitionSnap[road_X]: {         FeatureExtract                vehicle_map = {
    vehicles: [{id, lane,           .convert_cur_state()            running_vehicle: {WE: n, EW: n, ...},
     speed, type}]                   ──────────────►                waiting_vehicle: {WE: n, EW: n, ...},
  },                                 解析传感器配置                   running_person:  {S: n, W: n, ...},
  sensor_status: {...},              车道→相位映射                   lane_queue_length: [...],
  cameraState: {}                    车辆归类(运行/等待)              num_in_deg: [...],
}}                                   按行进方向分组                   vehicle_lane_to_phase: {...},
                                                                   timestamp: ...,
                                                                   cameraState: {...}
                                                                 }

[CityFlow 仿真] lane→vehicle 格式
{intersection_id: {
  lane_id: [v1, v2, ...]            FeatureExtract                vehicle_map = {
}                                    .convert_cur_state_cf()        running_vehicle: {WE: n, EW: n, ...},
vehicles = {                         ──────────────►                waiting_vehicle: {WE: n, EW: n, ...}
  v1: {speed, running},                                             }
  v2: {speed, running},
}
```

##### 转换函数调用时机

| 运行模式 | 转换调用位置 | 说明 |
|---------|-------------|------|
| **生产模式** (`take_action_to_redis`) | `AdvancedControl.take_action_to_redis()` 内部自动调用 `convert_cur_state()` | 从 Redis 拉到 origin_state 后立即转换，再传给 `take_action()` |
| **CityFlow 仿真** | `SimulationAdapter.step()` 内部调用 `convert_cur_state_cf()` | 适配器层自动完成转换 |
| **直接调用 `take_action()`** | **不会自动转换** — 调用方必须预先转换 | 这是最常出错的场景，见下方示例 |

---

#### 格式一：CityFlow 仿真格式（输入）

<details>
<summary><b>CityFlow 原始格式 → 转换后格式</b></summary>

**原始数据（传入 adapter/sdk）：**

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

**经 `convert_cur_state_cf()` 转换后（传入 `take_action()`）：**

```python
state = {
    "HHL_QHDD": {
        "running_vehicle": {"WE": 0, "EW": 0, "WN": 0, "ES": 0,
                            "NS": 0, "SN": 0, "NE": 0, "SW": 0},
        "waiting_vehicle": {"WE": 0, "EW": 0, "WN": 0, "ES": 0,
                            "NS": 0, "SN": 0, "NE": 0, "SW": 0}
    }
}
```

> CityFlow 路径下，`SimulationAdapter.step()` 会自动调用 `convert_cur_state_cf()`，用户无需手动转换。
</details>

---

#### 格式二：生产环境 recognitionSnap 格式（输入）

<details>
<summary><b>recognitionSnap 原始格式（传感器数据）</b></summary>

这是从 Redis/传感器直接获取的原始数据格式：

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

**字段说明：**

| 字段 | 类型 | 说明 |
|------|------|------|
| `recognitionSnap[road_id]` | dict | **必须以 `recognitionSnap[` 开头**，`road_id` 需与传感器配置中的道路 ID 匹配 |
| `recognitionSnap[road_id].vehicles` | list | 车辆列表，每项含 `id`, `lane`, `speed`（数组）, `type`（`"vehicle"` 或 `"person"`） |
| `recognitionSnap[road_id].timestamp` | int | 传感器时间戳 |
| `sensor_status` | dict | `tirStatus[road_id]` → 传感器故障状态（空 dict 表示正常） |
| `cameraState` | dict | 相机状态（空 dict 表示正常） |
</details>

<details>
<summary><b>经 convert_cur_state() 转换后的 vehicle_map 格式</b></summary>

**这是传入 `take_action()` 时 `state[intersection_id]` 实际需要的格式：**

```python
state = {
    "XML_CNL": {
        "running_vehicle": {
            "WE": 0, "EW": 1, "WN": 0, "ES": 0,
            "NS": 0, "SN": 0, "NE": 0, "SW": 0,
            "WW": 0, "EE": 0, "NN": 0, "SS": 0
        },
        "waiting_vehicle": {
            "WE": 0, "EW": 0, "WN": 0, "ES": 0,
            "NS": 0, "SN": 0, "NE": 0, "SW": 0,
            "WW": 0, "EE": 0, "NN": 0, "SS": 0
        },
        "running_person": {"S": 0, "W": 0, "N": 0, "E": 0},
        "lane_queue_length": [],       # 各车道排队长度（v3 算法）
        "num_in_deg": [],              # 车道四等分等待车辆数（v3 算法）
        "vehicle_lane_to_phase": {},   # 车道→车辆列表映射
        "timestamp": 1700000000,
        "cameraState": {}
    }
}
```

**字段说明：**

| 字段 | 说明 |
|------|------|
| `running_vehicle` | 按行进方向（WE/EW/NS/SN/...）统计的**运行中**车辆数（速度 > `MIN_RUNNING_SPEED`） |
| `waiting_vehicle` | 按行进方向统计的**等待中**车辆数（速度 <= `MIN_RUNNING_SPEED`） |
| `running_person` | 按方向统计的行人数量 |
| `lane_queue_length` | 每条进口道的排队长度（仅 v3） |
| `num_in_deg` | 车道按长度四等分后各段等待车辆数（仅 v3） |
| `vehicle_lane_to_phase` | 每条车道上的车辆对象列表（用于 v3 特征提取） |
| `timestamp` | 传感器数据中最大的时间戳 |
| `cameraState` | 各传感器的故障状态 |

> **方向编码含义**：两位字母表示 from→to，如 `WE` = 西→东（直行），`WN` = 西→北（左转），`SW` = 南→西（右转）。
</details>

---

#### 直接调用 `take_action()` 的正确方式

直接调用 `take_action()` 时，**必须先将原始数据通过 `convert_cur_state()` 转换**。生产模式中这一步在 `take_action_to_redis()` 内部自动完成，但直接调用不会。

**错误用法（缺少转换，会 KeyError 崩溃）：**

```python
algo = AdvancedControl(test=True, config_path="config/test_net.json")

# 原始 recognitionSnap 数据
raw_state = {
    "XML_CNL": {
        "recognitionSnap[road_1]": {
            "vehicles": [{"id": "v1", "lane": "XML_CNL_N_0", "speed": [5.0], "type": "vehicle"}]
        }
    }
}

# ❌ 直接传入原始数据 — state["XML_CNL"] 中没有 "waiting_vehicle" 键，
#    AdvancedV1.algorithm_control() 会抛出 KeyError
phase = algo.take_action(raw_state, env_state)
```

**正确用法：**

```python
algo = AdvancedControl(test=True, config_path="config/test_net.json")

raw_state = {
    "XML_CNL": {
        "recognitionSnap[road_1]": {
            "vehicles": [{"id": "v1", "lane": "XML_CNL_N_0", "speed": [5.0], "type": "vehicle"}]
        },
        "sensor_status": {"tirStatus[road_1]": {}},
        "cameraState": {}
    }
}

# ✅ 先转换，再调用
vehicle_map = algo.convert_cur_state(raw_state)
state = {algo.config.INTERSECTION: vehicle_map}

phase = algo.take_action(state, env_state)
```

---

#### 传感器配置与数据对齐

`FeatureExtract.convert_cur_state()` 依赖**传感器配置**来解析 `recognitionSnap` 数据：

- `recognitionSnap[road_id]` 中的 `road_id` 必须与传感器配置中某条道路（`roads[].id`）或人行道（`crosswalks[].id`）匹配
- 如果没有任何匹配，对应数据会被静默跳过（不会报错，但车辆数据全部丢失）
- `vehicle["lane"]` 必须与算法配置中的 `lane_to_phase` 键名匹配，否则该车辆被跳过
- 传感器配置通过以下方式加载：
  - **生产模式**：从 Redis 读取 `sensorConfig` 键
  - **测试模式**：使用 `DEFAULT_SENSOR_CONF`（`algorithms/utils/config.py`）或通过 `sensor_cnf` 参数传入

---

#### env_state（信号机状态）

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

#### 返回值

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

## 🌟 Star 历史

<a href="https://www.star-history.com/#OpenTraffic-Team/opentraffic-tsc-engine&Date">
  <img src="https://api.star-history.com/svg?repos=OpenTraffic-Team/opentraffic-tsc-engine&type=Date" width="400" height="250" />
</a>

</div>
