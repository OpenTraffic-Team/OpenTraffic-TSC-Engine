"""
真实算法快速启动入口

行为 (跟仓库根目录的 run_algorithms_real.py 等价, 仅做了一点点工程化):
  1. 起 AdvancedControl, 从 redis 拉 signal_env_state, 往 redis 推 alg_return.
  2. 主循环目标 ~20Hz: 单 tick < 50ms 就补 sleep; 选不出相位 (None/0) sleep 100ms,
     避免空转打满 CPU.
  3. SIGINT / SIGTERM 优雅退出, finally 里调 algo.stop().

用法:
  python algorithms_sdk/examples/real_algo_runner.py
  python algorithms_sdk/examples/real_algo_runner.py --mq-config config/mq_config.json
  MQ_CONFIG=/abs/path/mq_config.json python algorithms_sdk/examples/real_algo_runner.py

配合 signal_env_simulator.py 在本地起一个假信号机, 就可以不连真路口跑通整个链路.
"""
import argparse
import os
import signal
import sys
import time


# ============================================================
# 路径 / 常量
# ============================================================
# examples/ 在 algorithms_sdk/examples/, 往上三级到仓库根
ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, ROOT)

from algorithms_sdk.advanced_control import AdvancedControl  # noqa: E402

DEFAULT_MQ_CONFIG = "config/mq_config.json"
TICK_TARGET_SEC   = 0.05    # 单 tick 至少这么久, 避免 CPU 100%
EMPTY_SLEEP_SEC   = 0.10    # take_action 返回 None/0 时的退避
ERROR_SLEEP_SEC   = 0.50    # 异常退避, 给中间件一点恢复时间


# ============================================================
# 工具
# ============================================================
def get_version() -> str:
    """读 VERSION 文件 / ALGO_VERSION 环境变量, 现场排查发版用."""
    vfile = os.path.join(ROOT, "VERSION")
    if os.path.isfile(vfile):
        try:
            with open(vfile) as f:
                v = f.read().strip()
                if v:
                    return v
        except Exception:
            pass
    return os.environ.get("ALGO_VERSION", "unknown")


def parse_args():
    p = argparse.ArgumentParser(description="真实算法快速启动入口")
    p.add_argument(
        "--mq-config",
        default=os.environ.get("MQ_CONFIG", DEFAULT_MQ_CONFIG),
        help=f"中间件配置文件路径 (默认 {DEFAULT_MQ_CONFIG}, 也可用 MQ_CONFIG 环境变量)",
    )
    p.add_argument(
        "--no-tick-sleep",
        action="store_true",
        help="关掉 50ms 节流, 只保留空相位/异常退避; 压测时用",
    )
    return p.parse_args()


# ============================================================
# 主循环
# ============================================================
def main() -> int:
    args = parse_args()

    # cd 到仓库根, 这样 mq_config.json 的相对路径以及算法内部用到的相对路径都对得上
    os.chdir(ROOT)

    print("=" * 60)
    print(f"[init] real-algo runner | version={get_version()}")
    print(f"[init] mq_config={args.mq_config}")
    print(f"[init] cwd={os.getcwd()}")
    print("=" * 60)

    if not os.path.isfile(args.mq_config):
        print(f"[init] mq_config 不存在: {args.mq_config}")
        return 1

    algo = AdvancedControl(mq_path=args.mq_config)

    stop = {"flag": False}
    def handle_signal(signum, _frame):
        print(f"\n[main] 收到信号 {signum}, 准备退出 ...")
        stop["flag"] = True
    signal.signal(signal.SIGINT, handle_signal)
    signal.signal(signal.SIGTERM, handle_signal)

    push_n = 0
    empty_n = 0
    try:
        while not stop["flag"]:
            t0 = time.time()
            try:
                eid = algo.take_action_to_redis()
            except Exception as e:
                # 算法 / 中间件偶发异常: 不能让进程挂掉, 打日志退避一下继续
                print(f"[loop] take_action 异常: {e}, sleep {ERROR_SLEEP_SEC}s")
                time.sleep(ERROR_SLEEP_SEC)
                continue
            elapsed = time.time() - t0

            if eid in (None, 0):
                empty_n += 1
                # 没必要每次都刷, 第一次和每 10 次打一条
                if empty_n == 1 or empty_n % 10 == 0:
                    print(f"[loop] 选不出相位 (累计 {empty_n} 次), elapsed={elapsed:.3f}s")
                time.sleep(EMPTY_SLEEP_SEC)
                continue

            push_n += 1
            print(f"[loop #{push_n}] id={eid} elapsed={elapsed:.3f}s")

            if not args.no_tick_sleep and elapsed < TICK_TARGET_SEC:
                time.sleep(TICK_TARGET_SEC - elapsed)
    except KeyboardInterrupt:
        # SIGINT 已经走 handle_signal 了, 这里兜底
        print("\n[main] KeyboardInterrupt, 退出 ...")
    finally:
        try:
            algo.stop()
        except Exception as e:
            print(f"[main] algo.stop 异常: {e}")
        print(f"[main] 已退出 | push={push_n} empty={empty_n}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
