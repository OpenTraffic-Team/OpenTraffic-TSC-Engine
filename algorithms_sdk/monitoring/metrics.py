"""
Algorithm SDK - 性能指标模块
提供决策性能监控和统计功能
"""
import time
from typing import Dict, List, Optional
from dataclasses import dataclass, field
from collections import deque


@dataclass
class MetricRecord:
    """单条指标记录"""
    timestamp: float
    inference_time_ms: float
    decision: str
    success: bool
    phase_index: int


class MetricsCollector:
    """
    性能指标收集器

    功能：
    - 记录每次决策的性能数据
    - 计算统计数据（平均值、最大值、最小值）
    - 支持时间窗口统计
    """

    def __init__(self, window_size: int = 1000):
        """
        Args:
            window_size: 时间窗口大小（保留最近N条记录）
        """
        self.window_size = window_size
        self._records: deque = deque(maxlen=window_size)
        self._total_decisions = 0
        self._successful_decisions = 0
        self._failed_decisions = 0
        self._total_inference_time = 0.0

    def record(self, inference_time_ms: float, decision: str,
               success: bool = True, phase_index: int = 0):
        """记录一次决策"""
        record = MetricRecord(
            timestamp=time.time(),
            inference_time_ms=inference_time_ms,
            decision=decision,
            success=success,
            phase_index=phase_index
        )
        self._records.append(record)
        self._total_decisions += 1
        if success:
            self._successful_decisions += 1
        else:
            self._failed_decisions += 1
        self._total_inference_time += inference_time_ms

    def get_summary(self) -> Dict:
        """获取统计摘要"""
        if not self._records:
            return {
                "total_decisions": 0,
                "successful_decisions": 0,
                "failed_decisions": 0,
                "success_rate": 0.0,
                "avg_inference_time_ms": 0.0,
                "min_inference_time_ms": 0.0,
                "max_inference_time_ms": 0.0,
            }

        inference_times = [r.inference_time_ms for r in self._records]

        return {
            "total_decisions": self._total_decisions,
            "successful_decisions": self._successful_decisions,
            "failed_decisions": self._failed_decisions,
            "success_rate": self._successful_decisions / self._total_decisions * 100,
            "avg_inference_time_ms": sum(inference_times) / len(inference_times),
            "min_inference_time_ms": min(inference_times),
            "max_inference_time_ms": max(inference_times),
            "window_size": len(self._records),
        }

    def get_recent_records(self, count: int = 10) -> List[MetricRecord]:
        """获取最近的N条记录"""
        records = list(self._records)
        return records[-count:]

    def get_recent_avg_time(self, count: int = 100) -> float:
        """获取最近N次决策的平均推理时间"""
        records = list(self._records)[-count:]
        if not records:
            return 0.0
        return sum(r.inference_time_ms for r in records) / len(records)

    def reset(self):
        """重置所有统计"""
        self._records.clear()
        self._total_decisions = 0
        self._successful_decisions = 0
        self._failed_decisions = 0
        self._total_inference_time = 0.0


class PhaseDistribution:
    """相位决策分布统计"""

    def __init__(self):
        self._phase_count: Dict[int, int] = {}

    def record(self, phase_index: int):
        """记录一次相位决策"""
        self._phase_count[phase_index] = self._phase_count.get(phase_index, 0) + 1

    def get_distribution(self) -> Dict[int, float]:
        """获取相位分布比例"""
        total = sum(self._phase_count.values())
        if total == 0:
            return {}
        return {
            phase: count / total * 100
            for phase, count in self._phase_count.items()
        }

    def get_counts(self) -> Dict[int, int]:
        """获取相位次数统计"""
        return self._phase_count.copy()

    def reset(self):
        """重置统计"""
        self._phase_count.clear()


__all__ = ["MetricsCollector", "PhaseDistribution", "MetricRecord"]
