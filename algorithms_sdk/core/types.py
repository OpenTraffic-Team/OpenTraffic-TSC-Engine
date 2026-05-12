"""
Algorithm SDK - 类型定义
定义SDK对外的输入输出数据类型
"""
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Any
from enum import Enum


class Mode(Enum):
    """SDK运行模式"""
    CITYFLOW = "cityflow"      # CityFlow仿真
    SUMO = "sumo"              # SUMO仿真
    PRODUCTION = "production"  # 生产环境（连接中间件）


class AlgorithmVersion(Enum):
    """算法版本"""
    V1_MAX_PRESSURE = "v1"      # 最大压力算法
    V2_MLP = "v2"               # MLP神经网络
    V3_FUZZY = "v3"             # 模糊控制
    V4_ATTENTION = "v4"         # 注意力机制


@dataclass
class PhaseAction:
    """相位动作结果"""
    phase: str                          # 相位名称
    phase_index: int                    # 相位索引
    confidence: float = 1.0             # 置信度
    reasoning: Optional[str] = None     # 决策原因
    safety_check_passed: bool = True    # 安全检查是否通过


@dataclass
class SimulationState:
    """仿真环境状态输入"""
    intersection_id: str                # 路口ID
    current_phase: int                  # 当前相位索引
    phase_time: float                   # 当前相位已运行时间(秒)
    current_plan: int                   # 当前方案号
    vehicles: List[Dict] = field(default_factory=list)
    waiting_vehicles: Dict[str, int] = field(default_factory=dict)
    running_vehicles: Dict[str, int] = field(default_factory=dict)


@dataclass
class EnvironmentState:
    """信号机环境状态"""
    intersection_id: str                # 路口ID
    currentPhase: int                    # 当前相位索引
    phaseTime: float                     # 相位已运行时间
    currentPlan: int                     # 当前方案
    phases: List[str] = field(default_factory=list)


@dataclass
class DecisionResult:
    """SDK决策结果"""
    action: PhaseAction                  # 决策动作
    timestamp: float                    # 决策时间戳
    inference_time_ms: float            # 推理耗时(毫秒)
    algorithm_version: str               # 算法版本


@dataclass
class MetricsData:
    """性能指标数据"""
    total_decisions: int = 0
    successful_decisions: int = 0
    failed_decisions: int = 0
    avg_inference_time_ms: float = 0.0


@dataclass
class HealthStatus:
    """健康检查状态"""
    is_healthy: bool
    message: str
    last_decision_time: Optional[float] = None
    error_count: int = 0
    memory_usage_mb: float = 0.0


__all__ = [
    "Mode", "AlgorithmVersion", "PhaseAction",
    "SimulationState", "EnvironmentState", "DecisionResult",
    "MetricsData", "HealthStatus",
]
