"""
Algorithm SDK - 初始化模块
"""
from .core.sdk import AlgorithmSDK, create_sdk
from .core.types import (
    Mode,
    AlgorithmVersion,
    PhaseAction,
    SimulationState,
    EnvironmentState,
    DecisionResult,
    MetricsData,
    HealthStatus,
)

__version__ = "1.0.0"

__all__ = [
    # 主类
    "AlgorithmSDK",
    "create_sdk",
    # 类型
    "Mode",
    "AlgorithmVersion",
    "PhaseAction",
    "SimulationState",
    "EnvironmentState",
    "DecisionResult",
    "MetricsData",
    "HealthStatus",
]
