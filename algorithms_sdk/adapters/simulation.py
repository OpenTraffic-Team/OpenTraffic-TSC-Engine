"""
Algorithm SDK - 仿真适配器
支持 CityFlow 和 SUMO
"""
from typing import Dict, List, Optional, Any

from .base import BaseAdapter
from ..core.exceptions import AdapterError, SDKInitError


class SimulationAdapter(BaseAdapter):
    """
    仿真适配器
    封装算法核心，提供统一的仿真接口
    """

    def __init__(
        self,
        mode,
        config_path: str = None,
        logger=None,
        test_mode: bool = True,
        algo_version: str = "v4",
        **kwargs,
    ):
        super().__init__(mode, config_path, logger, **kwargs)
        self.algo_version = algo_version
        self.test_mode = test_mode
        self._vehicles = []
        self._last_lane_info = None
        self.initialize(**kwargs)

    def initialize(self, **kwargs):
        """初始化算法核心"""
        try:
            from algorithms.advanced_control import AdvancedControl

            self.controller = AdvancedControl(
                mq_path=None,
                logger=self.logger,
                sensor_cnf=kwargs.get("sensor_cnf", {}),
                config_path=self.config_path,
                test=self.test_mode,
            )
            self._is_running = True
            self.logger(f"[Adapter] 仿真适配器初始化成功 - 算法版本: {self.algo_version}")
        except ImportError as e:
            raise SDKInitError(f"算法模块导入失败: {e}")
        except Exception as e:
            raise SDKInitError(f"适配器初始化失败: {e}")

    def step(self, state: Dict, env_state: Dict) -> str:
        """
        执行一步决策

        Args:
            state: 仿真环境状态 (CityFlow/SUMO格式)
                格式: {"路口ID": interLaneInfo} 或直接是 interLaneInfo
            env_state: 信号机环境状态

        Returns:
            决策相位 (如 "phase1", "phase2")
        """
        if not self._is_running:
            raise AdapterError("适配器未初始化")

        # 提取路口ID和车道信息
        if isinstance(state, dict):
            # 如果是 {"路口ID": interLaneInfo} 格式
            intersection_id = list(state.keys())[0]
            interLaneInfo = state[intersection_id]
        else:
            # 如果直接是 interLaneInfo
            interLaneInfo = state

        # 根据仿真平台转换状态
        if self.mode.value == "cityflow":
            lane_info = self.controller.convert_cur_state_cf(interLaneInfo, self._vehicles)
        else:
            lane_info = self.controller.convert_cur_state(state)

        self._last_lane_info = lane_info

        # 封装state格式
        formatted_state = {intersection_id: lane_info}

        # 调用算法
        action = self.controller.take_action(formatted_state, env_state)
        return action

    def set_vehicles(self, vehicles: list):
        """设置车辆列表 (CityFlow专用)"""
        self._vehicles = vehicles

    def get_lane_info(self):
        """获取当前车道信息"""
        return self._last_lane_info

    def reset(self):
        """重置适配器状态"""
        self._vehicles = []
        self._last_lane_info = None
        if hasattr(self.controller, "reset"):
            self.controller.reset()


__all__ = ["SimulationAdapter"]
