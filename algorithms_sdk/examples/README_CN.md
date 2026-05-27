<div align="right">

**中文** | [**English**](README.md)

</div>

# Algorithm SDK 示例

包含 Algorithm SDK 的完整使用示例。

## 示例列表

| 文件 | 说明 | 模式 |
|------|------|------|
| `quick_demo.py` | 快速上手，动态车辆模拟 + 实时相位决策 | 仿真 |
| `simulation_demo.py` | 批量仿真流程，含统计和分析 | 仿真 |
| `production_demo.py` | 生产环境配置和连接示例 | 生产 |
| `real_algo_runner.py` | 真实算法运行器（长时间仿真） | 仿真 |

## 快速开始

```bash
# 入门 - 动态车辆模拟
python algorithms_sdk/examples/quick_demo.py

# 基础 - 批量仿真
python algorithms_sdk/examples/simulation_demo.py

# 生产环境检查
python algorithms_sdk/examples/production_demo.py --check
```

## 示例详解

### quick_demo.py

动态车辆模拟，约 90 秒实时运行。演示：
- SDK 初始化（仿真模式）
- 动态车辆进出模拟（NS/EW 方向流量随时间变化）
- 实时相位决策和切换
- 性能统计（总决策、成功率、平均耗时）
- 相位分布分析

```bash
python algorithms_sdk/examples/quick_demo.py
```

### simulation_demo.py

批量仿真流程（默认 20 步）。演示：
- 多步仿真循环
- 指标收集和统计
- 相位分布分析
- 健康状态检查

```bash
python algorithms_sdk/examples/simulation_demo.py
# 修改步数：编辑 run_simulation(num_steps=100)
```

### production_demo.py

生产环境连接示例。演示：
- Redis 配置检查
- 生产模式 SDK 初始化
- 手动 step 调用
- 健康监控

```bash
# 仅检查环境
python algorithms_sdk/examples/production_demo.py --check

# 运行演示（需要 Redis 连接）
python algorithms_sdk/examples/production_demo.py
```

## 常见问题

### Q: 报错 "配置文件未找到"

确保从项目根目录运行：
```bash
cd /path/to/OpenTraffic
python algorithms_sdk/examples/quick_demo.py
```

### Q: 如何切换算法版本

```python
sdk = AlgorithmSDK(mode="cityflow", algo_version="v2_1", config_path="config/test_cityflow.json")
```

### Q: 如何自定义日志

```python
def my_logger(msg):
    import logging
    logging.info(msg)

sdk = AlgorithmSDK(mode="cityflow", logger=my_logger, config_path="config/test_cityflow.json")
```
