"""
Algorithm SDK - 生产环境适配器
"""
from .base import BaseAdapter
from ..core.exceptions import AdapterError


class ProductionAdapter(BaseAdapter):
    """
    生产环境适配器
    连接中间件 (Redis)，实时控制信号机
    """

    def __init__(
        self,
        mode,
        mq_config_path: str,
        config_path: str = None,
        logger=None,
        **kwargs,
    ):
        super().__init__(mode, config_path, logger, **kwargs)
        self.mq_config_path = mq_config_path
        self._is_running = False
        self.initialize(**kwargs)

    def initialize(self, **kwargs):
        """初始化生产环境"""
        try:
            from algorithms_sdk.advanced_control import AdvancedControl

            self.controller = AdvancedControl(
                mq_path=self.mq_config_path,
                logger=self.logger,
                config_path=self.config_path,
                test=False,
            )
            self._is_running = True
            self.logger("[Adapter] 生产适配器初始化成功")
        except Exception as e:
            raise AdapterError(f"生产适配器初始化失败: {e}")

    def step(self, state, env_state):
        """
        生产模式下不需要手动调用step
        算法会通过中间件自动获取数据和输出决策
        """
        raise NotImplementedError("生产模式使用自动回调，无需手动调用step")

    def start_auto_run(self):
        """启动自动运行 (生产模式)"""
        if not self._is_running:
            raise AdapterError("适配器未初始化")
        self.controller.take_action_to_redis()


__all__ = ["ProductionAdapter"]
