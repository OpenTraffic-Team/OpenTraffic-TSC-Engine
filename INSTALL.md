# OpenTraffic 环境安装指南

## 1. 基础环境

- **操作系统**: Linux (x86_64 / ARM64)
- **Python**: 3.8+
- **Conda** (推荐): Miniconda / Anaconda

```bash
conda create -n trafficlight38 python=3.8
conda activate trafficlight38
```

## 2. Python 依赖

| 包名 | 版本 | 用途 |
|------|------|------|
| numpy | >=1.24 | 数值计算 |
| scipy | >=1.10 | 科学计算 |
| scikit-learn | >=1.3 | 机器学习（Lasso 回归） |
| torch | >=2.0 | 神经网络模型（v2.x 算法） |
| redis-py | >=4.0 | Redis 消息中间件 |
| psutil | >=5.9 | 系统监控 |
| PyYAML | >=6.0 | YAML 配置文件解析 |
| joblib | >=1.4 | sklearn 依赖 |
| Cython | >=3.0 | 编译 .py → .so（仅 build 需要） |

### 一键安装

```bash
pip install numpy scipy scikit-learn redis psutil PyYAML joblib Cython

# PyTorch (CPU 版，约 200MB)
pip install torch --index-url https://download.pytorch.org/whl/cpu
```

> **注意:** 如果使用 GPU 版 PyTorch，请根据 CUDA 版本选择对应安装命令：
> ```bash
# CUDA 11.8
pip install torch --index-url https://download.pytorch.org/whl/cu118
# CUDA 12.1
pip install torch --index-url https://download.pytorch.org/whl/cu121
```

## 3. CityFlow 仿真引擎 (可选)

CityFlow 是 C++ 编写的交通流仿真器，需要从源码编译。

```bash
# 安装依赖
sudo apt-get install -y cmake build-essential libboost-all-dev

# 克隆并编译
git clone https://github.com/cityflow-project/CityFlow.git
cd CityFlow
pip install .
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


