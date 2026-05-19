# OpenTraffic 环境安装指南

## 1. 基础环境

- **操作系统**: Linux (x86_64 / ARM64)
- **Python**: 3.8+
- **Conda** (推荐): Miniconda / Anaconda

```bash
conda create -n trafficlight38 python=3.8
conda activate trafficlight38
```

## 2. 一键安装

```bash
# 克隆项目
git clone https://github.com/OpenTraffic-Team/opentraffic-tsc-engine
cd opentraffic-tsc-engine

# 安装核心依赖 + 算法包
pip install .
```

这会自动安装以下 Python 依赖：

| 包名 | 用途 |
|------|------|
| numpy | 数值计算 |
| scipy | 科学计算 |
| scikit-learn | 机器学习（Lasso 回归） |
| torch | 神经网络模型（v2.x 算法） |
| redis-py | Redis 消息中间件 |
| psutil | 系统监控 |
| PyYAML | YAML 配置文件解析 |
| joblib | sklearn 依赖 |

> **注意:** PyTorch 默认安装 CPU 版本。如需 GPU 版本，请先手动安装：
> ```bash
> # CUDA 11.8
> pip install torch --index-url https://download.pytorch.org/whl/cu118
> # CUDA 12.1
> pip install torch --index-url https://download.pytorch.org/whl/cu121
> ```

## 3. CityFlow 仿真引擎 (可选)

CityFlow 是 C++ 编写的交通流仿真器，需要 CMake + Boost。

```bash
# 安装系统依赖
sudo apt-get install -y cmake build-essential libboost-all-dev

# 安装 CityFlow Python 包
pip install ./CityFlow/
```

> 如果不想安装 CityFlow，`test_sdk_cityflow.py` 会自动使用内置 Mock 引擎。

## 4. Redis (生产模式需要)

生产模式使用 Redis 作为消息中间件，需要运行 Redis 服务。

```bash
# Ubuntu
sudo apt-get install redis-server

# 或使用 Docker
docker run -d -p 6379:6379 redis:latest
```

## 5. 验证安装

```bash
# 1. 最简测试 (无外部依赖)
python test_simple.py

# 2. CityFlow 集成测试 (自动使用 Mock, 无需 CityFlow)
python test_sdk_cityflow.py --steps 100

# 3. 固定配时对比测试
python test_sdk_cityflow.py --steps 3600 --fixed
```

预期输出：所有测试正常完成，无 ModuleNotFoundError。

## 6. 开发模式安装
 
如果需要修改源码，使用可编辑模式安装：

```bash
pip install -e ".[dev]"
```

这会以开发模式安装，修改 `.py` 文件后无需重新安装。同时安装开发依赖（pytest、Cython 等）。

