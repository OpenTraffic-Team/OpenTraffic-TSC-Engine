#!/usr/bin/env python3
"""
最简单的算法测试脚本
不需要CityFlow，不需要Redis，直接调用算法
"""
import sys
import os

# 添加algorithms路径
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from algorithms.advanced_control import AdvancedControl

def test_algorithm():
    print("=" * 60)
    print("算法测试 - 最简版")
    print("=" * 60)

    # 1. 初始化算法（test=True 表示本地测试模式，不连接Redis）
    print("\n[1] 初始化算法...")
    try:
        algo = AdvancedControl(
            test=True,
            config_path="config/test_net.json"
        )
        print("    算法初始化成功！")
    except Exception as e:
        print(f"    初始化失败: {e}")
        return

    # 2. 构造测试数据
    print("\n[2] 构造测试数据...")

    # 车辆状态 - 按recognitionSnap格式组织（传感器数据格式）
    # 格式：{rec_id: {"vehicles": [...], "timestamp": xxx}}
    # 注意：intersection_id需要与配置中的cur_inter_id一致（XML_CNL）
    timestamp = 1700000000  # 示例时间戳

    # 根据配置中的lane_to_phase，车道包括：
    # XML_CNL_N_0 -> NS_NW
    # XML_CNL_N_1 -> NS_NE
    # XML_CNL_S_1 -> SN
    # XML_CNL_S_2 -> SW
    # XML_CNL_W_1 -> WE
    # XML_CNL_W_2 -> WN
    # XML_CNL_E_0 -> EW_EN
    # XML_CNL_E_1 -> EW_ES
    state = {
        "XML_CNL": {
            "cameraState": {},  # 相机状态，为空表示没有错误
            "sensor_status": {
                "tirStatus[road_1_2_3]": {},
                "tirStatus[road_1_0_1]": {},
                "tirStatus[road_2_1_2]": {},
                "tirStatus[road_0_1_0]": {}
            },
            # 道路数据（每个rec_id对应一个传感器）
            "recognitionSnap[road_1_2_3]": {
                "timestamp": timestamp,
                "vehicles": [
                    {"id": "v1", "lane": "XML_CNL_N_0", "speed": [5.0], "type": "vehicle"}
                ]
            },
            "recognitionSnap[road_1_0_1]": {
                "timestamp": timestamp,
                "vehicles": [
                    {"id": "v2", "lane": "XML_CNL_W_1", "speed": [0.0], "type": "vehicle"}
                ]
            },
            "recognitionSnap[road_2_1_2]": {
                "timestamp": timestamp,
                "vehicles": []
            },
            "recognitionSnap[road_0_1_0]": {
                "timestamp": timestamp,
                "vehicles": [
                    {"id": "v3", "lane": "XML_CNL_E_1", "speed": [3.0], "type": "vehicle"}
                ]
            }
        }
    }

    # 信号机状态
    env_state = {
        "phases": [1, 2],           # 相位编号列表（对应stagePhase中的键）
        "currentPhase": 1,          # 当前相位索引/编号
        "phaseTime": 30,            # 当前相位已运行时间(秒)
        "currentPlan": "WE_EW_WN_ES", # 当前相位名称
        "timestamp": timestamp       # 时间戳
    }

    print(f"    车辆状态: {state}")
    print(f"    信号机状态: {env_state}")

    # 3. 调用算法
    print("\n[3] 调用算法...")
    try:
        # 直接传入原始状态，算法会通过convert_cur_state转换
        phase = algo.take_action(state, env_state)
        print(f"    算法返回: {phase}")

    except Exception as e:
        print(f"    算法调用失败: {e}")
        import traceback
        traceback.print_exc()

    print("\n" + "=" * 60)
    print("测试完成！")
    print("=" * 60)


if __name__ == "__main__":
    test_algorithm()
