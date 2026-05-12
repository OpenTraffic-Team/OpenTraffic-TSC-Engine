from algorithms_sdk.advanced_control import AdvancedControl
import time
import signal
import os

def _get_version():
    """启动时打版本/构建号到日志，便于排查。生产环境无 git，用 VERSION 文件或环境变量。"""
    root = os.path.dirname(os.path.abspath(__file__))
    version_file = os.path.join(root, "VERSION")
    if os.path.isfile(version_file):
        try:
            with open(version_file) as f:
                return f.read().strip() or "unknown"
        except Exception:
            pass
    return os.environ.get("ALGO_VERSION", "unknown")

print(f"[算法启动] version/build: {_get_version()}")

stop_flag = False

def handle_exit(signum, frame):
    global stop_flag
    print(f"\n收到系统信号 {signum}，正在准备退出...")
    stop_flag = True

# 先注册信号处理器，确保初始化阶段也能响应 SIGINT/SIGTERM
signal.signal(signal.SIGINT, handle_exit)
signal.signal(signal.SIGTERM, handle_exit)

# 支持环境变量指定配置文件路径，便于统一部署路径
path = os.environ.get("MQ_CONFIG", "config/mq_config.json")

try:
    algo_to_start = AdvancedControl(mq_path=path)
except Exception as e:
    print(f"[算法启动失败] 初始化异常，请检查 mq_config.json 及 Redis 连接: {e}")
    raise

try:
    while not stop_flag:
        z_time = time.time()
        result = algo_to_start.take_action_to_redis()
        elapsed = time.time() - z_time

        if result is None or result == 0:
            print(f"算法选择相位为none")
            time.sleep(0.1)  # 失败时稍作等待，避免 CPU 100% 占用
        else:
            print(f"推送数据id为：{result}")
            print(f"算法运行消耗时间：{elapsed:.3f}秒")
            # 如果执行很快，sleep 到至少 0.05 秒，避免 CPU 空转
            if elapsed < 0.05:
                time.sleep(0.05 - elapsed)
except KeyboardInterrupt:
    print("\n正在退出程序...")
finally:
    try:
        algo_to_start.stop()
    except Exception as e:
        print(f"关闭时出现异常: {e}")

print("程序退出")
