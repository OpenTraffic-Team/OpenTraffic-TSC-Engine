"""
Algorithm SDK - 核心模块
"""
from .sdk import AlgorithmSDK, create_sdk, check_license, SDK_VERSION
from .types import (
    Mode, AlgorithmVersion, PhaseAction,
    SimulationState, EnvironmentState, DecisionResult,
    MetricsData, HealthStatus,
)
from .constants import SDK_VERSION as VERSION

__version__ = VERSION

__all__ = [
    "AlgorithmSDK", "create_sdk", "check_license", "SDK_VERSION",
    "Mode", "AlgorithmVersion", "PhaseAction",
    "SimulationState", "EnvironmentState", "DecisionResult",
    "MetricsData", "HealthStatus",
]
