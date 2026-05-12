#!/usr/bin/env python3
"""
Algorithm SDK 快速演示
演示 CityFlow 仿真模式的基本用法

从项目根目录运行: python3 algorithms_sdk/examples/quick_demo.py
"""
import sys
import os
import time
import random

script_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.chdir(script_dir)  # 切换到项目根目录
sys.path.insert(0, script_dir)

from algorithms_sdk import AlgorithmSDK


def create_test_state():
    """
    创建测试数据

    注意：这里的格式是 convert_cur_state_cf 期望的格式：
    - interLaneInfo: {lane: [vehicle_ids]}
    - interVehicles: {vehicle_id: vehicle_info}
    """
    # 车道信息：车道ID -> 车辆ID列表
    interLaneInfo = {
        "XML_CNL_N_0": ["v1", "v2"],
        "XML_CNL_N_1": [],
        "XML_CNL_S_1": ["v4"],
        "XML_CNL_S_2": [],
        "XML_CNL_W_1": ["v5"],
        "XML_CNL_W_2": [],
        "XML_CNL_E_0": [],
        "XML_CNL_E_1": ["v3"],
    }

    # 车辆信息：车辆ID -> 车辆详情
    interVehicles = {
        "v1": {"speed": 5.0, "running": "1"},
        "v2": {"speed": 3.0, "running": "1"},
        "v3": {"speed": 0.0, "running": "0"},  # 等待
        "v4": {"speed": 2.0, "running": "1"},
        "v5": {"speed": 0.5, "running": "1"},
    }

    # 封装成算法期望的 state 格式 (路口ID -> 车道信息)
    # 实际使用时这个由 CityFlow 仿真引擎提供
    intersection_id = "XML_CNL"
    state = {
        intersection_id: interLaneInfo
    }

    return state, interVehicles


def create_test_env_state(timestamp, phase_time=0, current_phase=1):
    """创建环境状态"""
    return {
        "phases": [1, 2],
        "currentPhase": current_phase,
        "phaseTime": phase_time,
        "currentPlan": "1",
        "timestamp": timestamp
    }


def simulate_vehicle_movement(interLaneInfo, interVehicles, elapsed_time, current_phase):
    """模拟车辆移动，动态更新车辆状态
    
    elapsed_time: 从仿真开始经过的秒数
    前50秒南北方向车多，后50秒东西方向车多
    
    车道格式: XML_CNL_<方向>_<编号>
    N_*, S_* = 南北相位 (phase 1)
    E_*, W_* = 东西相位 (phase 2)
    
    规则：
    - 当前相位为绿灯时，该方向的车可以移动 (running)
    - 红灯方向的车在等待 (waiting)
    """
    lanes = list(interLaneInfo.keys())
    
    # 根据时间调整车流量方向偏好
    if elapsed_time < 50:
        # 前50秒：南北方向车多
        def get_entry_prob(lane):
            direction = lane.split('_')[2]  # N, S, E, W
            return 0.6 if direction in ['N', 'S'] else 0.15
    else:
        # 50秒后：东西方向车多
        def get_entry_prob(lane):
            direction = lane.split('_')[2]  # N, S, E, W
            return 0.6 if direction in ['E', 'W'] else 0.15
    
    # 当前相位对应的绿灯方向
    green_directions = {'N', 'S'} if current_phase == 1 else {'E', 'W'}
    
    # 更新现有车辆状态
    for vid in interVehicles:
        # 找出该车辆在哪条车道
        for lane, vehicles in interLaneInfo.items():
            if vid in vehicles:
                direction = lane.split('_')[2]
                if direction in green_directions:
                    # 绿灯方向，车辆移动
                    interVehicles[vid]['running'] = '1'
                    interVehicles[vid]['speed'] = round(random.uniform(3.0, 10.0), 1)
                else:
                    # 红灯方向，车辆等待
                    interVehicles[vid]['running'] = '0'
                    interVehicles[vid]['speed'] = 0.0
                break
    
    # 随机让车辆离开 (从出口车道) - 但不从 interVehicles 删除
    for lane in lanes:
        if lane in interLaneInfo and interLaneInfo[lane] and random.random() < 0.3:
            interLaneInfo[lane].pop(0)
    
    # 随机让新车辆进入
    for lane in lanes:
        if lane in interLaneInfo and random.random() < get_entry_prob(lane):
            vid = f"v{100 + len(interVehicles)}"
            direction = lane.split('_')[2]
            
            # 新进入的车辆状态取决于该方向是否绿灯
            if direction in green_directions:
                running = '1'
                speed = round(random.uniform(3.0, 10.0), 1)
            else:
                running = '0'
                speed = 0.0
            
            interLaneInfo[lane].append(vid)
            interVehicles[vid] = {
                "speed": speed,
                "running": running
            }
    
    return interLaneInfo, interVehicles


def main():
    print("=" * 60)
    print("Algorithm SDK 快速演示")
    print("=" * 60)

    try:
        # 创建 SDK 实例
        print("\n[1] 创建SDK实例...")
        sdk = AlgorithmSDK(
            mode="cityflow",
            config_path="config/test_cityflow.json"
        )
        print(f"    SDK版本: {sdk.version}")
        print(f"    运行模式: {sdk.mode.value}")

        # 设置车辆信息
        print("\n[2] 设置车辆数据...")
        state, interVehicles = create_test_state()
        sdk._adapter.set_vehicles(interVehicles)

        # 执行决策 - 运行约60秒
        print("\n[3] 执行决策 (运行约60秒)...")
        print("-" * 60)
        
        start_time = time.time()
        base_timestamp = 1700000000
        decision_count = 0
        phase_history = []
        last_print_time = start_time
        current_phase = 1
        phase_start_time = start_time  # 记录当前相位开始时间
        env_state = create_test_env_state(base_timestamp, phase_time=0, current_phase=current_phase)
        
        while time.time() - start_time < 90:
            elapsed = int(time.time() - start_time)
            
            # 动态更新车辆状态
            intersection_id = "XML_CNL"
            state[intersection_id], interVehicles = simulate_vehicle_movement(
                state[intersection_id], interVehicles, elapsed, current_phase
            )
            sdk._adapter.set_vehicles(interVehicles)
            
            # 执行决策
            result = sdk.step(state, env_state)
            decision_count += 1
            new_phase = int(result.action.phase)
            phase_history.append(new_phase)
            
            # 如果相位切换了，重置计时
            if new_phase != current_phase:
                current_phase = new_phase
                phase_start_time = time.time()
            
            # 计算当前相位已持续的时长
            elapsed = int(time.time() - start_time)
            phase_time = int(time.time() - phase_start_time)
            env_state = create_test_env_state(
                base_timestamp + elapsed,
                phase_time=phase_time,
                current_phase=current_phase
            )
            
            # 每秒打印一次状态
            if time.time() - last_print_time >= 1.0:
                # 统计各方向车辆数
                ns_count = sum(1 for v in interVehicles.values() if v.get('speed', 0) > 0)
                ew_count = sum(1 for lane, vids in state[intersection_id].items() 
                              for _ in [lane.split('_')[2]] if _ in ['E', 'W'] for __ in [vids])
                phase = int(result.action.phase) if result.action.phase else 0
                direction = "NS" if phase == 1 else "EW"
                print(f"    [{int(elapsed):3d}s] 相位={phase}({int(phase_time):2d}s) | "
                      f"车辆={len(interVehicles):2d} | 耗时={result.inference_time_ms:.2f}ms")
                last_print_time = time.time()
            
            # 每步间隔模拟真实信号周期
            time.sleep(0.5)
        
        print("-" * 60)

        # 查看指标
        print("\n[4] 统计指标...")
        metrics = sdk.get_metrics()
        print(f"    总决策: {metrics.total_decisions}")
        print(f"    成功: {metrics.successful_decisions}")
        print(f"    失败: {metrics.failed_decisions}")
        print(f"    平均耗时: {metrics.avg_inference_time_ms:.2f}ms")
        print(f"    成功率: {metrics.successful_decisions/metrics.total_decisions*100:.1f}%")

        # 相位分布统计
        print("\n[5] 相位分布...")
        phase_counts = {}
        for p in phase_history:
            phase_counts[p] = phase_counts.get(p, 0) + 1
        for phase, count in sorted(phase_counts.items()):
            bar = "█" * int(count / len(phase_history) * 30)
            print(f"    相位 {phase}: {count:4d} ({count/len(phase_history)*100:5.1f}%) {bar}")

        # 健康检查
        print("\n[6] 健康检查...")
        health = sdk.get_health_status()
        print(f"    状态: {'正常' if health.is_healthy else '异常'}")
        print(f"    内存: {health.memory_usage_mb:.1f}MB")
        print(f"    错误次数: {health.error_count}")

        # 关闭
        print("\n[7] 关闭...")
        sdk.close()
        print("    完成")

        print("\n" + "=" * 60)
        print(f"演示完成！总运行时长: {time.time() - start_time:.1f}秒")
        print("=" * 60)

    except Exception as e:
        print(f"\n错误: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    main()
