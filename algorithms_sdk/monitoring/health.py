"""
Algorithm SDK - 健康检查模块
提供系统健康状态监控功能
"""
import time
import psutil
import os
from typing import Dict, List, Optional, Callable
from dataclasses import dataclass, field
from enum import Enum


class HealthLevel(Enum):
    """健康等级"""
    HEALTHY = "healthy"      # 完全健康
    WARNING = "warning"      # 轻微问题
    CRITICAL = "critical"   # 严重问题
    UNKNOWN = "unknown"     # 未知状态


@dataclass
class ComponentHealth:
    """组件健康状态"""
    name: str
    status: HealthLevel
    message: str
    last_check_time: float = field(default_factory=time.time)
    details: Dict = field(default_factory=dict)


class HealthChecker:
    """
    健康检查器

    功能：
    - 检查各组件健康状态
    - 支持自定义检查项
    - 记录历史健康状态
    """

    def __init__(self, error_threshold: int = 10):
        """
        Args:
            error_threshold: 错误次数阈值，超过则标记为不健康
        """
        self.error_threshold = error_threshold
        self._components: Dict[str, ComponentHealth] = {}
        self._check_callbacks: List[Callable] = []
        self._last_overall_check = 0.0
        self._error_count = 0
        self._memory_baseline_mb = self._get_current_memory()

    def register_component(self, name: str):
        """注册需要检查的组件"""
        self._components[name] = ComponentHealth(
            name=name,
            status=HealthLevel.UNKNOWN,
            message="未检查"
        )

    def register_check_callback(self, callback: Callable):
        """注册自定义检查回调"""
        self._check_callbacks.append(callback)

    def check(self) -> Dict:
        """
        执行健康检查

        Returns:
            健康检查结果字典
        """
        self._last_overall_check = time.time()

        # 检查内存
        self._check_memory()

        # 检查CPU
        self._check_cpu()

        # 执行自定义检查
        for callback in self._check_callbacks:
            try:
                callback(self)
            except Exception:
                pass

        # 综合判断
        return self.get_overall_status()

    def _check_memory(self):
        """检查内存使用"""
        try:
            memory_mb = self._get_current_memory()
            memory_percent = memory_mb / (psutil.virtual_memory().total / 1024 / 1024) * 100

            if memory_percent > 90:
                status = HealthLevel.CRITICAL
                message = f"内存使用过高: {memory_percent:.1f}%"
            elif memory_percent > 75:
                status = HealthLevel.WARNING
                message = f"内存使用较高: {memory_percent:.1f}%"
            else:
                status = HealthLevel.HEALTHY
                message = f"内存使用正常: {memory_percent:.1f}%"

            self._components["memory"] = ComponentHealth(
                name="memory",
                status=status,
                message=message,
                details={
                    "usage_mb": memory_mb,
                    "usage_percent": memory_percent,
                    "baseline_mb": self._memory_baseline_mb
                }
            )
        except Exception as e:
            self._components["memory"] = ComponentHealth(
                name="memory",
                status=HealthLevel.UNKNOWN,
                message=f"内存检查失败: {e}"
            )

    def _check_cpu(self):
        """检查CPU使用"""
        try:
            cpu_percent = psutil.cpu_percent(interval=0.1)

            if cpu_percent > 90:
                status = HealthLevel.WARNING
                message = f"CPU使用率较高: {cpu_percent:.1f}%"
            else:
                status = HealthLevel.HEALTHY
                message = f"CPU使用率正常: {cpu_percent:.1f}%"

            self._components["cpu"] = ComponentHealth(
                name="cpu",
                status=status,
                message=message,
                details={"usage_percent": cpu_percent}
            )
        except Exception as e:
            self._components["cpu"] = ComponentHealth(
                name="cpu",
                status=HealthLevel.UNKNOWN,
                message=f"CPU检查失败: {e}"
            )

    def _get_current_memory(self) -> float:
        """获取当前进程内存使用(MB)"""
        return psutil.Process(os.getpid()).memory_info().rss / 1024 / 1024

    def record_error(self):
        """记录一个错误"""
        self._error_count += 1

    def get_overall_status(self) -> Dict:
        """获取整体健康状态"""
        has_warning = False
        has_critical = False

        for component in self._components.values():
            if component.status == HealthLevel.CRITICAL:
                has_critical = True
            elif component.status == HealthLevel.WARNING:
                has_warning = True

        if has_critical or self._error_count >= self.error_threshold:
            level = HealthLevel.CRITICAL
        elif has_warning:
            level = HealthLevel.WARNING
        else:
            level = HealthLevel.HEALTHY

        return {
            "status": level.value,
            "error_count": self._error_count,
            "memory_usage_mb": self._get_current_memory(),
            "components": {
                name: {
                    "status": comp.status.value,
                    "message": comp.message,
                    "details": comp.details
                }
                for name, comp in self._components.items()
            },
            "last_check_time": self._last_overall_check,
            "is_healthy": level == HealthLevel.HEALTHY
        }

    def get_component_status(self, name: str) -> Optional[ComponentHealth]:
        """获取指定组件的健康状态"""
        return self._components.get(name)

    def reset_error_count(self):
        """重置错误计数"""
        self._error_count = 0


__all__ = ["HealthChecker", "HealthLevel", "ComponentHealth"]
