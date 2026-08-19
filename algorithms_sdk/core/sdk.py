"""
Algorithm SDK - 核心SDK类
提供统一的算法调用接口
"""
import time
import psutil
import os
from typing import Dict, Any, Optional, Callable

from .constants import SDK_VERSION
from .exceptions import SDKError, LicenseExpiredError, SDKInitError, AlgorithmError
from .types import Mode, DecisionResult, PhaseAction, MetricsData, HealthStatus


def check_license(required=True):
    """
    授权校验（fail-closed）：
    - 许可证模块缺失时：required=True 抛异常（生产环境），False 返回 False（开发/仿真）
    - 校验失败由 verify_license 内部直接拒绝启动（不会"警告后放行"）
    """
    try:
        from algorithms.license_check import verify_license
    except ImportError:
        if required:
            raise LicenseExpiredError("缺少授权校验模块 (algorithms.license_check)，无法启动")
        return False
    return verify_license()



def create_sdk(mode: str = "cityflow", **kwargs):
    """创建SDK实例的工厂函数"""
    return AlgorithmSDK(mode=mode, **kwargs)


class AlgorithmSDK:
    """
    交通信号控制算法SDK

    提供统一的接口调用算法，支持三种运行模式：
    - cityflow: CityFlow仿真
    - sumo: SUMO仿真
    - production: 生产环境（连接中间件）
    """

    def __init__(
        self,
        mode: str = "cityflow",
        config_path: str = None,
        mq_config_path: str = None,
        algo_version: str = "v1",
        logger: Callable = None,
        **kwargs,
    ):
        """
        初始化SDK

        Args:
            mode: 运行模式 (cityflow/sumo/production)
            config_path: 路口配置文件路径
            mq_config_path: 中间件配置文件路径（仅production模式）
            algo_version: 算法版本 (v1/v2/v3/v4)
            logger: 日志回调函数
        """
        self.version = SDK_VERSION
        self.mode = Mode(mode)
        self.config_path = config_path
        self.mq_config_path = mq_config_path
        self.algo_version = algo_version
        self.logger = logger or print

        self._controller = None
        self._adapter = None
        self._is_initialized = False

        # 统计指标
        self._total_decisions = 0
        self._successful_decisions = 0
        self._failed_decisions = 0
        self._total_inference_time = 0.0
        self._last_decision_time = None
        self._error_count = 0

        self._initialize(**kwargs)

    def _initialize(self, **kwargs):
        """初始化SDK"""
        try:
            # 授权校验：生产模式强制 fail-closed，仿真/开发模式模块缺失时不阻断
            check_license(required=(self.mode == Mode.PRODUCTION))

            # 根据模式初始化
            if self.mode == Mode.CITYFLOW or self.mode == Mode.SUMO:
                self._initialize_simulation(**kwargs)
            elif self.mode == Mode.PRODUCTION:
                self._initialize_production(**kwargs)
            else:
                raise SDKInitError(f"不支持的运行模式: {self.mode}")

            self._is_initialized = True
            self.logger(f"[SDK] 初始化成功 - 版本: {self.version}, 模式: {self.mode.value}")

        except Exception as e:
            raise SDKInitError(f"SDK初始化失败: {e}")

    def _initialize_simulation(self, **kwargs):
        """初始化仿真模式"""
        from algorithms_sdk.adapters.simulation import SimulationAdapter

        self._adapter = SimulationAdapter(
            mode=self.mode,
            config_path=self.config_path,
            logger=self.logger,
            test_mode=True,
            algo_version=self.algo_version,
            **kwargs,
        )
        self._controller = self._adapter.controller

    def _initialize_production(self, **kwargs):
        """初始化生产模式"""
        mq_config_path = self.mq_config_path
        if not mq_config_path:
            raise SDKInitError("生产模式需要提供 mq_config_path")

        from algorithms_sdk.adapters.production import ProductionAdapter

        self._adapter = ProductionAdapter(
            mode=self.mode,
            mq_config_path=mq_config_path,
            config_path=self.config_path,
            logger=self.logger,
            **kwargs,
        )
        self._controller = self._adapter.controller

    @property
    def is_initialized(self) -> bool:
        """检查SDK是否已初始化"""
        return self._is_initialized

    def step(self, state: Dict, env_state: Dict) -> DecisionResult:
        """
        执行一步决策

        Args:
            state: 仿真环境状态 (CityFlow/SUMO格式)
            env_state: 信号机环境状态

        Returns:
            DecisionResult: 决策结果
        """
        if not self._is_initialized:
            raise SDKError("SDK未初始化，请先创建SDK实例")

        start_time = time.time()

        try:
            # 调用适配器执行决策
            action_str = self._adapter.step(state, env_state)

            # 更新统计
            self._total_decisions += 1
            if action_str is not None:
                self._successful_decisions += 1
            else:
                self._failed_decisions += 1
            self._last_decision_time = time.time()

            # 计算推理时间
            inference_time_ms = (time.time() - start_time) * 1000
            self._total_inference_time += inference_time_ms

            # 解析动作
            phase_index = 0
            if action_str is not None:
                try:
                    phase_index = int(action_str.replace("phase", "").replace("Phase", "")) - 1
                    if phase_index < 0:
                        phase_index = 0
                except (ValueError, AttributeError):
                    phase_index = 0

            result = DecisionResult(
                action=PhaseAction(
                    phase=str(action_str) if action_str else "None",
                    phase_index=phase_index,
                    confidence=1.0 if action_str else 0.0,
                    safety_check_passed=True,
                ),
                timestamp=time.time(),
                inference_time_ms=inference_time_ms,
                algorithm_version=self.algo_version,
            )

            return result

        except Exception as e:
            self._failed_decisions += 1
            self._error_count += 1
            raise AlgorithmError(f"算法执行失败: {e}")

    def get_metrics(self) -> MetricsData:
        """获取性能指标"""
        avg_time = 0.0
        if self._total_decisions > 0:
            avg_time = self._total_inference_time / self._total_decisions

        return MetricsData(
            total_decisions=self._total_decisions,
            successful_decisions=self._successful_decisions,
            failed_decisions=self._failed_decisions,
            avg_inference_time_ms=avg_time,
        )

    def get_health_status(self) -> HealthStatus:
        """获取健康状态"""
        memory_mb = psutil.Process(os.getpid()).memory_info().rss / 1024 / 1024

        is_healthy = self._is_initialized and self._error_count < 10
        message = "OK" if is_healthy else "存在错误"

        return HealthStatus(
            is_healthy=is_healthy,
            message=message,
            last_decision_time=self._last_decision_time,
            error_count=self._error_count,
            memory_usage_mb=memory_mb,
        )

    def start_auto_run(self):
        """
        启动自动运行（仅生产模式）

        生产模式下调用此方法启动自动监听中间件，
        SDK会自动接收数据并输出决策，无需手动调用step()
        """
        if self.mode != Mode.PRODUCTION:
            raise SDKError("start_auto_run 仅支持生产模式")

        if not self._is_initialized:
            raise SDKError("SDK未初始化")

        self._adapter.start_auto_run()

    def reset(self):
        """重置统计指标"""
        self._total_decisions = 0
        self._successful_decisions = 0
        self._failed_decisions = 0
        self._total_inference_time = 0.0
        self._last_decision_time = None

        if self._adapter and hasattr(self._adapter, 'reset'):
            self._adapter.reset()

    def close(self):
        """关闭SDK"""
        if self._controller and hasattr(self._controller, "stop"):
            try:
                self._controller.stop()
            except (AttributeError, Exception):
                pass
        if self._adapter:
            self._adapter.close()
        self._is_initialized = False

    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.close()
