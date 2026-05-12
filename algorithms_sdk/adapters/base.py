"""
Algorithm SDK - 适配器基类
"""
from abc import ABC, abstractmethod
from typing import Dict, Any, Optional, Callable


class BaseAdapter(ABC):
    """适配器基类"""

    def __init__(
        self,
        mode,
        config_path: Optional[str] = None,
        logger: Optional[Callable] = None,
        **kwargs,
    ):
        self.mode = mode
        self.config_path = config_path
        self.logger = logger or print
        self.controller = None
        self._is_running = False

    @abstractmethod
    def initialize(self, **kwargs):
        """初始化适配器"""
        pass

    @abstractmethod
    def step(self, state: Dict, env_state: Dict) -> Any:
        """执行一步"""
        pass

    def convert_cityflow_state(self, cityflow_state: Dict, vehicles: list) -> Dict:
        """CityFlow状态转换"""
        return self.controller.convert_cur_state_cf(cityflow_state, vehicles)

    def convert_sumo_state(self, sumo_state: Dict) -> Dict:
        """SUMO状态转换"""
        return sumo_state

    def close(self):
        """关闭适配器"""
        self._is_running = False

    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.close()


__all__ = ["BaseAdapter"]
