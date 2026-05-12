import json


class MQConfig:
    # 默认 key 前缀及所在 db
    _DEFAULT_KEYS = {
        "origin_state":      {"prefix": "origin_info_state",  "db": 2},
        "env_state":         {"prefix": "signal_env_state",   "db": 2},
        "lane_to_phase":     {"prefix": "lane_to_phase",      "db": 2},
        "algorithm_control": {"prefix": "algorithm_control",  "db": 2},
        "signal_config":     {"prefix": "signalConfig",       "db": 0},
        "alg_config":        {"prefix": "algConfig",          "db": 0},
        "sensor_config":     {"prefix": "sensorConfig",       "db": 0},
        "hardware_config":   {"prefix": "intersection_device","db": 0},
    }

    def __init__(self, config_path):
        with open(config_path) as f:
            config = json.load(f)
        self.REDIS_ADDR = config["redis_addr"]
        self.REDIS_PORT = config["redis_port"]
        self.REDIS_PASSWORD = config["redis_password"]
        self.INTERSECTION = config.get("intersection", "")
        self.STREAM_READ_FROM_ORIGIN = config.get("state_stream_read_from", "$")
        self.STREAM_READ_FROM_ENV    = config.get("env_stream_read_from", "$")

        # 合并用户配置与默认值：每个 key 可以单独指定 prefix 和 db
        default_db_config = config.get("db_config", 0)
        user_keys = config.get("redis_keys", {})

        def _resolve(name):
            default = self._DEFAULT_KEYS[name]
            user = user_keys.get(name, {})
            if isinstance(user, str):
                return {"prefix": user, "db": default["db"]}
            return {
                "prefix": user.get("prefix", default["prefix"]),
                "db": user.get("db", default.get("db", default_db_config)),
            }

        self.KEY_ORIGIN_STATE    = _resolve("origin_state")["prefix"]
        self.DB_ORIGIN_STATE     = _resolve("origin_state")["db"]
        self.KEY_ENV_STATE       = _resolve("env_state")["prefix"]
        self.DB_ENV_STATE        = _resolve("env_state")["db"]
        self.KEY_LANE_TO_PHASE   = _resolve("lane_to_phase")["prefix"]
        self.DB_LANE_TO_PHASE    = _resolve("lane_to_phase")["db"]
        self.KEY_ALGORITHM_CONTROL = _resolve("algorithm_control")["prefix"]
        self.DB_ALGORITHM_CONTROL  = _resolve("algorithm_control")["db"]
        self.KEY_SIGNAL_CONFIG   = _resolve("signal_config")["prefix"]
        self.DB_SIGNAL_CONFIG    = _resolve("signal_config")["db"]
        self.KEY_ALG_CONFIG      = _resolve("alg_config")["prefix"]
        self.DB_ALG_CONFIG       = _resolve("alg_config")["db"]
        self.KEY_SENSOR_CONFIG   = _resolve("sensor_config")["prefix"]
        self.DB_SENSOR_CONFIG    = _resolve("sensor_config")["db"]
        self.KEY_HARDWARE_CONFIG = _resolve("hardware_config")["prefix"]
        self.DB_HARDWARE_CONFIG  = _resolve("hardware_config")["db"]
