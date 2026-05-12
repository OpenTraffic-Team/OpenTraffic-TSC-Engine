"""
Redis 配置初始化脚本 (联调前一次性执行)

算法启动时会从 Redis db=0 读取以下 4 个 key：
  - intersection_device:{local_ip}   → 获取路口 code
  - sensorConfig:HHL_QHDD            → 传感器配置
  - signalConfig:HHL_QHDD            → 信号机配置 (stagePhase / isInControl)
  - algConfig:HHL_QHDD               → 算法超参数

本脚本自动探测本机 IP，并将上述 key 写入 Redis。
请在启动算法 (run_algorithms_real.py) 之前先执行一次本脚本。

用法:
    python real_test/setup_redis_config.py
    python real_test/setup_redis_config.py --dry-run   # 只打印，不写入
"""
import argparse
import json
import socket
import sys

import redis


# ============================================================
# Redis 连接参数 (与 config/mq_config.json 保持一致)
# ============================================================
REDIS_HOST     = "47.110.91.222"
REDIS_PORT     = 6390
REDIS_PASSWORD = "TempRedis_2026_LinkOnly_9f3K"
CONFIG_DB      = 0          # 算法从 db=0 读配置
INTERSECTION   = "HHL_QHDD"


# ============================================================
# 传感器配置  (sensorConfig:HHL_QHDD)
# 路口有 N/S/E/W 四条进入道，每条道一个雷达
# road id 与 lane_to_phase 中的车道前缀需保持一致
# ============================================================
SENSOR_CONFIG = {
    "id": INTERSECTION,
    "roads": [
        {
            "id": f"{INTERSECTION}_N",
            "lanes": "[]",
            "radars": {
                "id": "RADAR_N",
                "ip": "10.0.0.1",
                "type": "XD",
                "position": [0.0, 0.0]
            },
            "cameras": []
        },
        {
            "id": f"{INTERSECTION}_S",
            "lanes": "[]",
            "radars": {
                "id": "RADAR_S",
                "ip": "10.0.0.2",
                "type": "XD",
                "position": [0.0, 0.0]
            },
            "cameras": []
        },
        {
            "id": f"{INTERSECTION}_E",
            "lanes": "[]",
            "radars": {
                "id": "RADAR_E",
                "ip": "10.0.0.3",
                "type": "XD",
                "position": [0.0, 0.0]
            },
            "cameras": []
        },
        {
            "id": f"{INTERSECTION}_W",
            "lanes": "[]",
            "radars": {
                "id": "RADAR_W",
                "ip": "10.0.0.4",
                "type": "XD",
                "position": [0.0, 0.0]
            },
            "cameras": []
        }
    ],
    "crosswalks": []
}


# ============================================================
# 信号机配置  (signalConfig:HHL_QHDD)
# stagePhase: 相位编号(字符串) → 相位字符串
#   与 signal_env_simulator.py 的 PHASES=[1,2] 对应
# isInControl: 算法是否接管信号机
# ============================================================
SIGNAL_CONFIG = {
    "signalCtl": {
        "stagePhase": {
            "1": "WE_EW_WN_ES",
            "2": "NS_SN_NE_SW"
        },
        "isInControl": True
    }
}


# ============================================================
# 算法超参数配置  (algConfig:HHL_QHDD)
# 与 algorithms_real/utils/config.py _set_algorithm_config() 对应
# ============================================================
ALG_CONFIG = {
    "algo_version": "v1",
    "debug": True,
    "phases": [
        "WE_EW_WN_ES",
        "NS_SN_NE_SW"
    ],
    "lane_to_phase": {
        "{intersection_id}_N_0": "NS",
        "{intersection_id}_N_1": "NE",
        "{intersection_id}_S_0": "SN",
        "{intersection_id}_S_1": "SW",
        "{intersection_id}_E_0": "EW",
        "{intersection_id}_E_1": "ES",
        "{intersection_id}_W_0": "WE",
        "{intersection_id}_W_1": "WN"
    },
    "stagePhase": {
        "1": "WE_EW_WN_ES",
        "2": "NS_SN_NE_SW"
    },
    "bind_phases": [0, 1],
    "layers_order_flag": [False],
    "phase_min_change_time": {
        "WE_EW_WN_ES": 15,
        "NS_SN_NE_SW": 15
    },
    "phase_min_change_time_high_level": {
        "WE_EW_WN_ES": 20,
        "NS_SN_NE_SW": 20
    },
    "phase_min_change_time_high_morning_level": {
        "WE_EW_WN_ES": 20,
        "NS_SN_NE_SW": 20
    },
    "phase_min_change_time_high_evening_level": {
        "WE_EW_WN_ES": 20,
        "NS_SN_NE_SW": 20
    },
    "phase_max_keep_time": {
        "WE_EW_WN_ES": 60,
        "NS_SN_NE_SW": 60
    },
    "max_keep_time_high_level": {
        "WE_EW_WN_ES": 65,
        "NS_SN_NE_SW": 65
    },
    "max_keep_time_high_morning_level": {
        "WE_EW_WN_ES": 65,
        "NS_SN_NE_SW": 65
    },
    "max_keep_time_high_evening_level": {
        "WE_EW_WN_ES": 65,
        "NS_SN_NE_SW": 65
    },
    "phase_max_keep_num": 5,
    "phase_preference": {"0": 1, "1": 1},
    "delay_time": 1,
    "advanced_weight": 1.4,
    "high_level_weight_minspeed": [2.5, 6.0],
    "min_running_speed": 7,
    "morning_rush": ["08:00", "08:30"],
    "evening_rush": ["18:00", "18:30"],
    "custom_peak_hours": ["16:50", "17:10"],
    "person_min_time": 40,
    "person_recongnize_plan": 0,
    "person_factor": 5,
    "max_transition_duration": 20,
    "init_time": 5,
    "is_cycle_control": False,
    "start_anomaly_detect": False,
    "anomaly_detect_interval": 10
}


# ============================================================
# 工具函数
# ============================================================
def get_local_ip() -> str:
    """探测本机对外 IP（与 advanced_control.get_local_ip 逻辑一致）。"""
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except Exception:
        return "127.0.0.1"


def make_client() -> redis.Redis:
    return redis.Redis(
        host=REDIS_HOST,
        port=REDIS_PORT,
        password=REDIS_PASSWORD,
        db=CONFIG_DB,
        socket_connect_timeout=10,
        decode_responses=True,
    )


def write_key(client: redis.Redis, key: str, value: dict, dry_run: bool):
    json_str = json.dumps(value, ensure_ascii=False)
    if dry_run:
        print(f"  [DRY-RUN] SET {key}")
        print(f"    {json_str[:120]}{'...' if len(json_str) > 120 else ''}")
    else:
        client.set(key, json_str)
        print(f"  [OK] SET {key}  ({len(json_str)} bytes)")


# ============================================================
# 主流程
# ============================================================
def main():
    parser = argparse.ArgumentParser(description="写入算法联调所需的 Redis 配置 key")
    parser.add_argument("--dry-run", action="store_true", help="只打印不写入")
    parser.add_argument("--ip", default=None,
                        help="手动指定本机 IP（默认自动探测，用于 intersection_device key）")
    args = parser.parse_args()

    local_ip = args.ip or get_local_ip()
    print(f"本机 IP: {local_ip}")
    print(f"目标 Redis: {REDIS_HOST}:{REDIS_PORT}  db={CONFIG_DB}")
    print(f"路口 ID: {INTERSECTION}")
    print("-" * 60)

    client = None
    if not args.dry_run:
        client = make_client()
        try:
            client.ping()
            print("[init] Redis ping OK\n")
        except Exception as e:
            print(f"[ERROR] Redis 连接失败: {e}")
            sys.exit(1)

    # 1. intersection_device:{local_ip}
    device_key = f"intersection_device:{local_ip}"
    device_value = {"code": INTERSECTION}
    write_key(client, device_key, device_value, args.dry_run)

    # 2. sensorConfig:HHL_QHDD
    write_key(client, f"sensorConfig:{INTERSECTION}", SENSOR_CONFIG, args.dry_run)

    # 3. signalConfig:HHL_QHDD
    write_key(client, f"signalConfig:{INTERSECTION}", SIGNAL_CONFIG, args.dry_run)

    # 4. algConfig:HHL_QHDD
    write_key(client, f"algConfig:{INTERSECTION}", ALG_CONFIG, args.dry_run)

    print("-" * 60)
    print("完成！4 个配置 key 已写入 Redis db=0。")
    print("接下来按顺序启动：")
    print("  1. python real_test/setup_redis_config.py          ← 本脚本（仅首次）")
    print("  2. python real_test/origin_state_simulator.py      ← 模拟车检数据")
    print("  3. python real_test/signal_env_simulator.py        ← 模拟信号机")
    print("  4. python run_algorithms_real.py                   ← 启动算法")


if __name__ == "__main__":
    main()
