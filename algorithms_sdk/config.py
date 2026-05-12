"""
Algorithm SDK - 配置管理模块
提供SDK配置加载和管理功能
"""
import os
import json
from typing import Dict, Optional, Any
from dataclasses import dataclass, field


@dataclass
class SDKConfig:
    """SDK配置"""
    mode: str = "cityflow"
    config_path: Optional[str] = None
    mq_config_path: Optional[str] = None
    algo_version: str = "v4"
    log_level: str = "INFO"
    enable_metrics: bool = True
    enable_health_check: bool = True
    check_interval_seconds: int = 60
    extra: Dict[str, Any] = field(default_factory=dict)


class ConfigManager:
    """
    配置管理器

    功能：
    - 从文件加载配置
    - 从环境变量加载配置
    - 配置验证和默认值
    """

    DEFAULT_CONFIG = {
        "mode": "cityflow",
        "algo_version": "v4",
        "log_level": "INFO",
        "enable_metrics": True,
        "enable_health_check": True,
        "check_interval_seconds": 60,
    }

    ENV_PREFIX = "ALGORITHM_SDK_"

    def __init__(self, config_path: Optional[str] = None):
        """
        Args:
            config_path: 配置文件路径 (JSON/YAML)
        """
        self.config_path = config_path
        self._config: Dict = self.DEFAULT_CONFIG.copy()

        if config_path:
            self.load_from_file(config_path)

        self._load_from_env()

    def load_from_file(self, path: str):
        """从文件加载配置"""
        if not os.path.exists(path):
            raise FileNotFoundError(f"配置文件不存在: {path}")

        ext = os.path.splitext(path)[1].lower()

        with open(path, 'r', encoding='utf-8') as f:
            if ext in ['.json', '.jsonc']:
                file_config = json.load(f)
            else:
                raise ValueError(f"不支持的配置文件格式: {ext}")

        self._config.update(file_config)

    def _load_from_env(self):
        """从环境变量加载配置"""
        env_mappings = {
            f"{self.ENV_PREFIX}MODE": "mode",
            f"{self.ENV_PREFIX}CONFIG_PATH": "config_path",
            f"{self.ENV_PREFIX}MQ_CONFIG_PATH": "mq_config_path",
            f"{self.ENV_PREFIX}ALGO_VERSION": "algo_version",
            f"{self.ENV_PREFIX}LOG_LEVEL": "log_level",
        }

        for env_key, config_key in env_mappings.items():
            value = os.environ.get(env_key)
            if value:
                self._config[config_key] = value

        # 布尔值环境变量
        for key in ["enable_metrics", "enable_health_check"]:
            env_key = f"{self.ENV_PREFIX}{key.upper()}"
            value = os.environ.get(env_key)
            if value:
                self._config[key] = value.lower() in ('true', '1', 'yes')

    def get(self, key: str, default: Any = None) -> Any:
        """获取配置项"""
        return self._config.get(key, default)

    def set(self, key: str, value: Any):
        """设置配置项"""
        self._config[key] = value

    def to_sdk_config(self) -> SDKConfig:
        """转换为SDKConfig对象"""
        return SDKConfig(
            mode=self._config.get("mode", "cityflow"),
            config_path=self._config.get("config_path"),
            mq_config_path=self._config.get("mq_config_path"),
            algo_version=self._config.get("algo_version", "v4"),
            log_level=self._config.get("log_level", "INFO"),
            enable_metrics=self._config.get("enable_metrics", True),
            enable_health_check=self._config.get("enable_health_check", True),
            check_interval_seconds=self._config.get("check_interval_seconds", 60),
            extra=self._config.get("extra", {}),
        )

    def validate(self) -> tuple:
        """
        验证配置有效性

        Returns:
            (is_valid, error_messages)
        """
        errors = []

        # 检查mode
        valid_modes = ["cityflow", "sumo", "production"]
        if self._config.get("mode") not in valid_modes:
            errors.append(f"不支持的运行模式: {self._config.get('mode')}")

        # 检查config_path
        if self._config.get("config_path"):
            if not os.path.exists(self._config["config_path"]):
                errors.append(f"配置文件不存在: {self._config['config_path']}")

        # 生产模式必须提供mq_config
        if self._config.get("mode") == "production":
            if not self._config.get("mq_config_path"):
                errors.append("生产模式需要提供 mq_config_path")

        return len(errors) == 0, errors

    def to_dict(self) -> Dict:
        """导出为字典"""
        return self._config.copy()

    def __repr__(self):
        return f"ConfigManager({self._config})"


class ConfigLoader:
    """配置文件加载器"""

    @staticmethod
    def load_intersection_config(path: str) -> Dict:
        """加载路口配置"""
        with open(path, 'r', encoding='utf-8') as f:
            return json.load(f)

    @staticmethod
    def load_mq_config(path: str) -> Dict:
        """加载消息队列配置"""
        with open(path, 'r', encoding='utf-8') as f:
            return json.load(f)

    @staticmethod
    def get_default_mq_config() -> Dict:
        """获取默认MQ配置"""
        return {
            "redis": {
                "host": "127.0.0.1",
                "port": 6379,
                "db": 0
            },
            "mq": {
                "host": "127.0.0.1",
                "port": 5672,
                "username": "guest",
                "password": "guest"
            }
        }


__all__ = ["SDKConfig", "ConfigManager", "ConfigLoader"]
