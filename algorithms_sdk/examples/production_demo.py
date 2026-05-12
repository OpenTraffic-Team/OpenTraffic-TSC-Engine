"""
Algorithm SDK - 生产环境示例
演示如何使用SDK连接生产环境（消息中间件）
"""
import sys
import os

# 获取项目根目录 (LightTest/)
project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.chdir(project_root)
sys.path.insert(0, project_root)

from algorithms_sdk import AlgorithmSDK


def check_production_environment():
    """
    检查生产环境配置

    Returns:
        bool: 环境是否就绪
    """
    print("=" * 60)
    print("Algorithm SDK 生产环境检查")
    print("=" * 60)

    # 检查MQ配置文件
    mq_config_path = "config/mq_config.json"
    if not os.path.exists(mq_config_path):
        print(f"\n[错误] MQ配置文件不存在: {mq_config_path}")
        print("       请创建配置文件或复制示例:")
        print("       cp config/mq_config.json.example config/mq_config.json")
        return False

    print(f"\n[OK] MQ配置文件存在: {mq_config_path}")

    # 检查路口配置文件
    config_path = "config/test_net.json"
    if not os.path.exists(config_path):
        print(f"\n[警告] 路口配置文件不存在: {config_path}")
        print("       将使用默认配置")
    else:
        print(f"[OK] 路口配置文件存在: {config_path}")

    return True


def run_production_demo():
    """运行生产环境演示"""
    print("=" * 60)
    print("Algorithm SDK 生产环境演示")
    print("=" * 60)

    if not check_production_environment():
        print("\n环境检查失败，请先配置生产环境")
        return

    try:
        # 创建SDK实例（连接到消息中间件）
        print("\n[1] 连接消息中间件...")
        sdk = AlgorithmSDK(
            mode="production",
            config_path="config/test_net.json",
            mq_config_path="config/mq_config.json",
            algo_version="v1"
        )
        print(f"    SDK版本: {sdk.version}")
        print(f"    运行模式: {sdk.mode.value}")

        # 健康检查
        print("\n[2] 健康检查...")
        health = sdk.get_health_status()
        print(f"    健康状态: {'正常' if health.is_healthy else '异常'}")
        print(f"    内存占用: {health.memory_usage_mb:.1f}MB")
        print(f"    错误次数: {health.error_count}")

        if health.last_decision_time:
            print(f"    最后决策时间: {health.last_decision_time}")

        # 查看性能指标
        print("\n[3] 性能指标...")
        metrics = sdk.get_metrics()
        print(f"    总决策次数: {metrics.total_decisions}")
        print(f"    成功决策:   {metrics.successful_decisions}")
        print(f"    失败决策:   {metrics.failed_decisions}")

        # 演示手动调用
        print("\n[4] 手动调用演示...")
        print("    生产模式支持通过消息队列自动接收数据")
        print("    也支持手动调用 step() 方法进行决策")

        state = {
            "XML_CNL": {
                "cameraState": {},
                "sensor_status": {},
                "recognitionSnap[road_1]": {
                    "timestamp": 1700000000,
                    "vehicles": [
                        {"id": "v1", "lane": "XML_CNL_N_0", "speed": [5.0]}
                    ]
                }
            }
        }

        env_state = {
            "phases": [1, 2],
            "currentPhase": 1,
            "phaseTime": 30,
            "currentPlan": "1"
        }

        result = sdk.step(state, env_state)
        print(f"    决策结果: {result.action.phase}")
        print(f"    推理时间: {result.inference_time_ms:.2f}ms")

        # 关闭
        print("\n[5] 关闭连接...")
        sdk.close()

        print("\n" + "=" * 60)
        print("生产环境演示完成！")
        print("=" * 60)

    except Exception as e:
        print(f"\n错误: {e}")
        print("\n提示: 生产模式需要:")
        print("      1. Redis 服务器运行")
        print("      2. RabbitMQ/Kafka 服务器运行")
        print("      3. 硬件配置正确加载")
        import traceback
        traceback.print_exc()


def connect_and_listen():
    """
    连接消息中间件并监听数据流

    这是一个占位函数，演示如何实现持续监听
    """
    print("=" * 60)
    print("消息监听模式（待实现）")
    print("=" * 60)
    print("\n在生产环境中，SDK会自动：")
    print("  1. 连接Redis订阅路口数据")
    print("  2. 接收传感器数据")
    print("  3. 执行算法决策")
    print("  4. 发布控制指令到MQ")
    print("\n示例代码：")
    print("""
    sdk = AlgorithmSDK(
        mode="production",
        mq_config_path="config/mq_config.json",
        config_path="config/路口配置.json"
    )

    # SDK会在后台线程中自动处理数据流
    # 主线程可以继续执行其他任务

    import time
    while True:
        time.sleep(1)
        # 检查状态
        health = sdk.get_health_status()
        print(f"运行中... 健康: {health.is_healthy}")
    """)


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Algorithm SDK 生产环境示例")
    parser.add_argument("--check", action="store_true", help="仅检查环境配置")
    parser.add_argument("--listen", action="store_true", help="监听模式")
    args = parser.parse_args()

    if args.listen:
        connect_and_listen()
    elif args.check:
        check_production_environment()
    else:
        run_production_demo()
