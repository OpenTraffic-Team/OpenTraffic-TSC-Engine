"""
Algorithm SDK - 仿真模式示例
演示如何使用SDK进行CityFlow/SUMO仿真
"""
import sys
import os

# 获取项目根目录 (LightTest/)
project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.chdir(project_root)
sys.path.insert(0, project_root)

from algorithms_sdk import AlgorithmSDK


def create_simulation_state():
    """创建仿真测试数据"""
    # CityFlow格式：车道 -> 车辆ID列表
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

    # 车辆信息
    interVehicles = {
        "v1": {"speed": 5.0, "running": "1"},
        "v2": {"speed": 3.0, "running": "1"},
        "v3": {"speed": 0.0, "running": "0"},
        "v4": {"speed": 2.0, "running": "1"},
        "v5": {"speed": 0.5, "running": "1"},
    }

    return {"XML_CNL": interLaneInfo}, interVehicles


def create_env_state(step: int = 0):
    """创建环境状态"""
    return {
        "phases": [1, 2],
        "currentPhase": 1,
        "phaseTime": 30 + step * 5,
        "currentPlan": "1",
        "timestamp": 1700000000 + step
    }


def run_simulation(num_steps: int = 20):
    """
    运行仿真

    Args:
        num_steps: 仿真步数
    """
    print("=" * 60)
    print("Algorithm SDK 仿真模式演示")
    print("=" * 60)

    try:
        # 创建SDK实例
        print("\n[1] 初始化SDK...")
        sdk = AlgorithmSDK(
            mode="cityflow",
            config_path="config/test_cityflow.json",
            algo_version="v1"
        )
        print(f"    SDK版本: {sdk.version}")
        print(f"    运行模式: {sdk.mode.value}")

        # 获取仿真数据
        print("\n[2] 准备仿真数据...")
        state, vehicles = create_simulation_state()
        sdk._adapter.set_vehicles(vehicles)
        print(f"    车辆数量: {len(vehicles)}")

        # 运行仿真
        print(f"\n[3] 运行仿真 ({num_steps} 步)...")
        print("-" * 60)

        decisions = []
        for step in range(num_steps):
            env_state = create_env_state(step)
            result = sdk.step(state, env_state)

            decisions.append({
                "step": step + 1,
                "phase": result.action.phase,
                "inference_time": result.inference_time_ms
            })

            if (step + 1) % 5 == 0:
                print(f"    步 {step + 1:2d}: 相位={result.action.phase}, "
                      f"耗时={result.inference_time_ms:.2f}ms")

        print("-" * 60)

        # 显示统计
        print("\n[4] 仿真统计...")
        metrics = sdk.get_metrics()
        print(f"    总决策次数: {metrics.total_decisions}")
        print(f"    成功决策:   {metrics.successful_decisions}")
        print(f"    失败决策:   {metrics.failed_decisions}")
        print(f"    平均推理时间: {metrics.avg_inference_time_ms:.2f}ms")

        # 健康检查
        print("\n[5] 健康检查...")
        health = sdk.get_health_status()
        print(f"    状态: {'正常' if health.is_healthy else '异常'}")
        print(f"    内存占用: {health.memory_usage_mb:.1f}MB")

        # 相位分布
        print("\n[6] 相位决策分布...")
        phase_counts = {}
        for d in decisions:
            p = d["phase"]
            phase_counts[p] = phase_counts.get(p, 0) + 1
        for phase, count in sorted(phase_counts.items()):
            pct = count / len(decisions) * 100
            print(f"    {phase}: {count}次 ({pct:.1f}%)")

        # 关闭
        sdk.close()
        print("\n" + "=" * 60)
        print("仿真完成！")
        print("=" * 60)

    except Exception as e:
        print(f"\n错误: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    run_simulation(num_steps=20)
