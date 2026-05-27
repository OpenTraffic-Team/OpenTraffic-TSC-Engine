<div align="right">

**中文** | [**English**](SDK_GUIDE.md)

</div>

# Algorithm SDK 使用说明

## 什么是 Algorithm SDK

Algorithm SDK 是 OpenTraffic 交通信号控制引擎的 Python 接口层，提供统一的 API 让你用几行代码就能调用自适应信号控制算法。

---

## 安装

```bash
pip install .
```

依赖：Python >= 3.8，Linux x86_64。

---

## 5 分钟上手

```python
from algorithms_sdk import AlgorithmSDK

# 1. 创建 SDK（仿真模式）
sdk = AlgorithmSDK(
    mode="cityflow",
    config_path="config/test_cityflow.json",
    algo_version="v1"
)

# 2. 准备路口车辆数据
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

# 3. 准备信号机状态
env_state = {
    "phases": [1, 2],
    "currentPhase": 1,
    "phaseTime": 30,
    "currentPlan": "1",
    "timestamp": 1700000000
}

# 4. 获取相位决策
result = sdk.step(state, env_state)
print(f"相位: {result.action.phase}, 耗时: {result.inference_time_ms:.2f}ms")

# 5. 关闭
sdk.close()
```

---

## API 速查

### 初始化

```python
sdk = AlgorithmSDK(
    mode="cityflow",            # "cityflow" | "production"
    config_path=None,           # 路口配置文件
    mq_config_path=None,        # Redis 配置（仅 production）
    algo_version="v1",          # 算法版本: "v1"
    logger=None,                # 自定义日志函数
)
```

### step() — 执行一次决策

```python
result = sdk.step(state, env_state)
# result.action.phase          → "phase1"
# result.action.phase_index     → 0
# result.inference_time_ms      → 12.5
# result.timestamp              → 1700000000.0
```

### get_metrics() — 性能指标

```python
m = sdk.get_metrics()
m.total_decisions          # 总决策次数
m.successful_decisions     # 成功次数
m.failed_decisions         # 失败次数
m.avg_inference_time_ms   # 平均推理耗时
```

### get_health_status() — 健康状态

```python
h = sdk.get_health_status()
h.is_healthy              # 是否健康
h.memory_usage_mb         # 内存占用
h.error_count             # 错误计数
```

### reset() / close()

```python
sdk.reset()   # 重置统计
sdk.close()   # 释放资源
```

---

## 数据格式

### 输入：state（车辆数据）

CityFlow 格式（仿真模式）：

```python
state = {
    "intersection_id": {
        "lane_id": ["vehicle_id1", "vehicle_id2"],
    }
}
```

### 输入：env_state（信号机状态）

```python
env_state = {
    "phases": [1, 2],          # 可用相位
    "currentPhase": 1,          # 当前相位
    "phaseTime": 30,            # 已运行时长(秒)
    "currentPlan": "1",         # 当前方案
    "timestamp": 1700000000
}
```

### 返回：DecisionResult

```python
@dataclass
class DecisionResult:
    action: PhaseAction          # 决策动作（含 phase, phase_index, confidence）
    timestamp: float            # 时间戳
    inference_time_ms: float    # 推理耗时(ms)
    algorithm_version: str       # 算法版本
```

---

## 生产模式

连接 Redis 中间件，从真实信号机获取数据：

```python
sdk = AlgorithmSDK(
    mode="production",
    mq_config_path="config/mq_config.json",
    config_path="config/test_net.json"
)
sdk.start_auto_run()  # 自动监听 Redis 并输出决策
```

---

## 常见问题

**Q: 导入报错 "No module named 'algorithms'"**

从项目根目录运行脚本，确保 `pip install .` 已执行。

**Q: step() 返回 None**

说明安全规则拦截了当前决策。检查输入数据格式是否正确。

**Q: 如何切换算法版本**

修改配置文件的 `algo_version` 字段即可。

**Q: 许可证校验失败**

确认系统时间正确，或联系开发者。
