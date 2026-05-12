# OpenTraffic — 交通信号控制算法 SDK

面向智能交通信号控制的开源 SDK，提供统一 Python 接口，支持 CityFlow 仿真和生产环境（Redis）部署。

[![License](https://img.shields.io/badge/License-Apache%202.0-blue.svg)](LICENSE)
[![Python](https://img.shields.io/badge/Python-3.8+-green.svg)](https://www.python.org/)
[![Platform](https://img.shields.io/badge/Platform-Linux%20x86__64-orange.svg)]()

---

## 功能特性

| 特性 | 说明 |
|------|------|
| 多算法支持 | 最大压力（v1）、注意力机制（v2.x），后续逐步开放更多 |
| 多模式支持 | CityFlow 仿真、生产环境（Redis 消息队列） |
| 统一接口 | 一套 API 适配不同运行环境 |
| 安全规则链 | 内置前置/后置安全规则，保障信号控制安全 |
| 性能监控 | 实时统计推理耗时、决策成功率、内存占用 |
| 健康检查 | 内置服务状态检测接口 |
| 许可证管理 | 内置授权校验，支持过期控制 |

---

## 环境要求

- **操作系统**: Linux x86_64
- **Python**: >= 3.8
- **算法源码**: `algorithms/` 目录（开源版本，`.py` 源文件）

### 安装依赖

```bash
# 克隆项目
git clone https://github.com/OpenTraffic-Team/OpenTraffic-Control
cd OpenTraffic

# 核心依赖（必装）
pip install numpy scipy scikit-learn redis psutil PyYAML Cython

# PyTorch（v2.x 算法模型需要）
pip install torch --index-url https://download.pytorch.org/whl/cpu

# 可选依赖
pip install cityflow    # CityFlow 仿真

# 或一键安装（见 INSTALL.md）
```

> 详细安装步骤见 [INSTALL.md](INSTALL.md)

---

## 项目结构

```
OpenTraffic/
├── algorithms/                  # 算法源码（.py 文件，部署时编译为 .so）
│   ├── advanced_control.py      # 算法主控
│   ├── cycle_control.py         # 周期控制
│   ├── license_check.py         # 许可证校验
│   ├── anomaly/                 # 异常检测模块
│   ├── enums/                   # 枚举定义
│   ├── models/                  # 算法模型（v1, v2_1, v2_2, v2_3,）
│   ├── saferules/               # 安全规则系统（pre/post rules）
│   └── utils/                   # 工具（配置、特征提取、日志、ReplayBuffer）
├── algorithms_sdk/              # SDK Python 源码
│   ├── __init__.py              # SDK 入口（AlgorithmSDK）
│   ├── advanced_control.py      # AdvancedControl 主控制类
│   ├── config.py                # 配置管理
│   ├── core/                    # 核心模块
│   │   ├── sdk.py               # AlgorithmSDK 类
│   │   ├── types.py             # 类型定义（DecisionResult, MetricsData 等）
│   │   ├── constants.py         # 版本常量
│   │   └── exceptions.py        # 异常定义
│   ├── adapters/                # 适配器层
│   │   ├── base.py              # 基类
│   │   ├── simulation.py        # 仿真适配器（CityFlow）
│   │   └── production.py        # 生产环境适配器（Redis）
│   ├── monitoring/              # 监控模块
│   │   ├── metrics.py           # 指标收集
│   │   └── health.py            # 健康检查
│   ├── mq_utils/                # 消息队列工具
│   │   ├── mq_config.py         # MQ 配置解析
│   │   └── redis/               # Redis Stream 读写
│   ├── mock/                    # CityFlow Mock 引擎
│   ├── utils/                   # 数据转换工具
│   └── examples/                # SDK 使用示例
├── config/                      # 配置文件
│   ├── mq_config.json           # Redis 连接配置
│   ├── test_cityflow.json       # CityFlow 仿真测试配置
│   ├── test_net.json            # 离线/生产测试配置
│   └── cityflow/                # CityFlow 引擎配置
│       ├── algo_config.yaml     # 算法参数
│       ├── config.json          # CityFlow 引擎参数
│       ├── roadnet.json         # 路网定义
│       └── flow.json            # 车流定义（由脚本自动生成）
├── real_test/                   # Redis 联调测试工具
│   ├── signal_env_simulator.py  # 信号机状态模拟器
│   ├── fake_push.py             # 假算法数据推送器
│   └── setup_redis_config.py    # Redis 配置初始化
├── frontend/                    # 仿真回放前端（浏览器打开 index.html）
├── test_simple.py               # 最简算法测试（无外部依赖）
├── test_sdk_cityflow.py         # CityFlow 集成仿真测试
├── run_algorithms_real.py       # 生产模式算法主程序
├── INSTALL.md                   # 环境安装指南
├── LICENSE                      # Apache 2.0
└── README.md
```

---

## 快速开始

### 最简测试（无需任何外部服务）

```bash
python test_simple.py
```

### CityFlow 仿真测试

```bash
# 需要先安装 CityFlow
pip install cityflow

# 运行 3600 步自适应算法仿真
python test_sdk_cityflow.py

# 自定义步数
python test_sdk_cityflow.py --steps 600

# 固定配时对比模式
python test_sdk_cityflow.py --fixed
```

仿真结束后，用浏览器打开 `frontend/index.html` 上传回放文件即可查看。

> 未安装 CityFlow 时会自动使用内置 Mock 引擎，用于纯算法逻辑验证。

---

## SDK 使用说明

SDK 提供两层 API：

| 层级 | 类 | 适用场景 |
|------|-----|----------|
| 高层 | `AlgorithmSDK` | 统一接口，自动适配不同模式 |
| 底层 | `AdvancedControl` | 直接调用，支持 `test=True` 本地测试 |

### 方式一：AlgorithmSDK（推荐）

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

### 方式二：AdvancedControl 直接调用

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

---

## 输入/输出格式

### state（车辆数据）

支持两种格式：

**格式一：CityFlow 仿真格式**

```python
state = {
    "HHL_QHDD": {
        "HHL_QHDD_N_0": ["v1", "v2"],
        "HHL_QHDD_N_1": [],
        "HHL_QHDD_S_0": ["v4"],
        # ...
    }
}
# 车辆信息单独传入
vehicles = {
    "v1": {"speed": 5.0, "running": "1"},
    "v2": {"speed": 3.0, "running": "1"},
}
```

**格式二：生产环境格式**（`recognitionSnap` 传感器数据）

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
        # ...
    }
}
```

### env_state（信号机状态）

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

### take_action() 返回值

```python
phase = 1       # 正常决策：相位编号
phase = None    # 安全规则未通过 或 异常检测触发
```

### AlgorithmSDK.step() 返回值

```python
@dataclass
class DecisionResult:
    action: PhaseAction        # 决策动作
    timestamp: float           # 时间戳
    inference_time_ms: float   # 推理耗时（毫秒）
    algorithm_version: str     # 算法版本
```

---

## Redis 联调测试（生产模式模拟）

模拟真实生产环境：通过 Redis Stream 传输传感器和信号机数据，算法从 Redis 读取并推送决策。

### 架构

```
┌──────────────────────────┐      ┌─────────────────┐
│ signal_env_simulator.py  │ ──→  │                 │
│ (模拟信号机推送 env_state) │      │   Redis Stream  │
└──────────────────────────┘      │                 │
                                  │  origin_info_   │
┌──────────────────────────┐      │  state:xxx      │
│ fake_push.py             │ ──→  │  signal_env_    │
│ (模拟算法假数据推送)        │      │  state:xxx      │
└──────────────────────────┘      │  algorithm_     │
                                  │  control:xxx    │
┌──────────────────────────┐      │                 │
│ run_algorithms_real.py   │ ←──→ │                 │
│ (算法主程序)               │      └─────────────────┘
└──────────────────────────┘
```

### 步骤

**1. 配置 Redis 连接**

编辑 `config/mq_config.json`：

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

**2. 初始化 Redis 配置**

```bash
# 写入路口配置（仅首次）
python real_test/setup_redis_config.py

# 预览模式（不实际写入）
python real_test/setup_redis_config.py --dry-run
```

**3. 启动信号机模拟器**

```bash
python real_test/signal_env_simulator.py
```

**4. （可选）推送假算法数据**

```bash
python real_test/fake_push.py --phase 2
```

**5. 启动算法主程序**

```bash
python run_algorithms_real.py
```

---

## 配置文件说明

### 路口配置（`config/test_cityflow.json` / `config/test_net.json`）

| 配置项 | 类型 | 说明 |
|--------|------|------|
| `cur_inter_id` | string | 路口标识，如 `"XML_CNL"` |
| `lane_to_phase` | dict | 车道到相位映射 |
| `phases` | list | 可用相位名称列表 |
| `stagePhase` | dict | 相位编号 → 名称映射 |
| `phase_min_change_time` | dict | 各相位最小绿灯时间（秒） |
| `phase_max_keep_time` | dict | 各相位最大绿灯时间（秒） |
| `algo_version` | string | 算法版本（`"v1"` / `"v2_1"` / `"v2_2"` / `"v2_3"`） |
| `cityflowTest` | int | CityFlow 测试标记（0/1） |
| `debug` | bool | 调试模式 |
| `morning_rush` / `evening_rush` | list | 高峰时段 |

### 中间件配置（`config/mq_config.json`）

| 字段 | 说明 |
|------|------|
| `redis_addr` | Redis 服务器 IP |
| `redis_port` | Redis 端口 |
| `redis_password` | Redis 密码 |
| `intersection` | 当前控制的路口 ID |
| `redis_keys.*.prefix` | Redis key 前缀 |
| `redis_keys.*.db` | Redis 数据库编号（0-15） |

---

## 编译部署

```bash
cd build
bash build.sh          # x86_64 编译，生成 algorithms.tar.gz
bash build_arm.sh      # ARM64 交叉编译
```

---

## 常见问题

### SO 文件加载失败

```bash
# 确认平台架构
uname -m                          # 应输出 x86_64
python -c "import struct; print(struct.calcsize('P')*8)"  # 应输出 64
```

### 许可证校验失败

检查系统时间是否正确，确认算法文件有效性。

### CityFlow 未安装

运行 `test_sdk_cityflow.py` 时自动切换到 Mock 引擎模式。

### Redis 连接失败

```bash
python -c "import redis; r=redis.Redis(host='<IP>', port=6390, password='<PWD>'); print(r.ping())"
```

---

## 核心依赖

| 依赖 | 版本 | 用途 |
|------|------|------|
| Python | >= 3.8 | 运行环境 |
| numpy | >= 1.24 | 数值计算 |
| scipy | >= 1.10 | 科学计算 |
| scikit-learn | >= 1.3 | 机器学习 |
| PyTorch | >= 2.0 | 神经网络模型（v2.x） |
| redis-py | >= 4.0 | Redis 连接 |
| psutil | >= 5.9 | 内存监控 |
| PyYAML | >= 6.0 | YAML 解析 |
| CityFlow | >= 1.0 | 仿真引擎（可选） |

---

## License

Apache License 2.0 — 详见 [LICENSE](LICENSE) 文件

---

## 贡献

欢迎提交 Issue 和 Pull Request！
