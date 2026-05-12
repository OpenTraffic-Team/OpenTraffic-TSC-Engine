"""
Algorithm SDK - 异常定义
"""


class SDKError(Exception):
    """SDK基础异常"""
    pass


class LicenseExpiredError(SDKError):
    """许可证过期"""
    pass


class LicenseConfigError(SDKError):
    """许可证配置错误"""
    pass


class SDKInitError(SDKError):
    """SDK初始化错误"""
    pass


class AlgorithmError(SDKError):
    """算法执行错误"""
    pass


class ConfigError(SDKError):
    """配置错误"""
    pass


class AdapterError(SDKError):
    """适配器错误"""
    pass


__all__ = [
    "SDKError",
    "LicenseExpiredError",
    "LicenseConfigError",
    "SDKInitError",
    "AlgorithmError",
    "ConfigError",
    "AdapterError",
]
