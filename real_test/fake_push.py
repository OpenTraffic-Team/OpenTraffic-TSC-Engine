"""
algorithm_control:HHL_QHDD 假数据推送器

用途: 配合 signal_env_simulator.py 验证监听 + 模式切换是否生效.
推送格式 (与 algorithms/advanced_control.py L168 一致):
    {"alg_return": <int>, "timestamp": <float>}
落盘到 stream 时再包成 {"data": json.dumps(...)} (与 redis_stream.push_data 一致).

用法:
    python fake_algo_publisher.py                 # 默认每 1s 推 1 条, alg_return 每 15s 换一次
    python fake_algo_publisher.py --phase 2       # 一次性推 alg_return=2 后退出
    python fake_algo_publisher.py --interval 1 --change-interval 30 --phases 1,2,None
"""
import argparse
import json
import random
import signal
import time

import redis


# ============================================================
# 配置 (跟 signal_env_simulator.py 保持一致)
# ============================================================
INTERSECTION_ID = "HHL_QHDD"
ALGO_STREAM_KEY = f"algorithm_control:{INTERSECTION_ID}"

REDIS_HOST     = "47.110.91.222"
REDIS_PORT     = 6390
REDIS_USERNAME = "default"
REDIS_PASSWORD = "TempRedis_2026_LinkOnly_9f3K"
ALGO_DB        = 0
STREAM_MAXLEN  = 10000


def make_client():
    return redis.Redis(
        host=REDIS_HOST,
        port=REDIS_PORT,
        username=REDIS_USERNAME,
        password=REDIS_PASSWORD,
        db=ALGO_DB,
        socket_connect_timeout=10,
        decode_responses=False,
    )


def push_one(client, phase):
    payload = {"alg_return": phase, "timestamp": round(time.time(), 3)}
    decorate = {"data": json.dumps(payload, ensure_ascii=False)}
    return client.xadd(ALGO_STREAM_KEY, decorate, maxlen=STREAM_MAXLEN)


def parse_phase_pool(s: str):
    pool = []
    for x in s.split(","):
        x = x.strip()
        if not x:
            continue
        if x.lower() == "none":
            pool.append(None)
        else:
            pool.append(int(x))
    if not pool:
        raise ValueError("phases 池为空")
    return pool


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--phase", type=int, default=None,
                        help="一次性推送指定相位后退出 (与 --interval/--phases 互斥)")
    parser.add_argument("--interval", type=float, default=1.0,
                        help="循环模式下两次 push 间隔(秒), 默认 1")
    parser.add_argument("--change-interval", type=float, default=15.0,
                        help="alg_return 重新随机的间隔(秒), 默认 15; 同一窗口内每次 push 的值都一样")
    parser.add_argument("--phases", type=str, default="1,2",
                        help="循环模式可选相位池, 逗号分隔; 加 'None' 测试 listener 是否会跳过")
    args = parser.parse_args()

    client = make_client()
    try:
        client.ping()
    except Exception as e:
        print(f"[init] Redis 连接失败: {e}")
        return 1
    print(f"[init] connected, push -> {ALGO_STREAM_KEY} (db={ALGO_DB})")

    if args.phase is not None:
        eid = push_one(client, args.phase)
        eid_str = eid.decode() if isinstance(eid, bytes) else eid
        print(f"[once] alg_return={args.phase} id={eid_str}")
        return 0

    pool = parse_phase_pool(args.phases)

    stop = {"flag": False}
    def handle_signal(signum, _frame):
        print(f"\n[main] 收到信号 {signum}, 退出 ...")
        stop["flag"] = True
    signal.signal(signal.SIGINT, handle_signal)
    signal.signal(signal.SIGTERM, handle_signal)

    print(f"[loop] 每 {args.interval}s 推一条, alg_return 每 {args.change_interval}s 换一次, "
          f"池={pool}, Ctrl+C 退出")

    n = 0
    cur_phase = random.choice(pool)
    last_change = time.monotonic()
    print(f"[loop] 初始 alg_return={cur_phase}")

    while not stop["flag"]:
        now = time.monotonic()
        if now - last_change >= args.change_interval:
            new_phase = random.choice(pool)
            if new_phase != cur_phase:
                print(f"[loop] alg_return 换值: {cur_phase} -> {new_phase}")
            cur_phase = new_phase
            last_change = now

        try:
            eid = push_one(client, cur_phase)
            eid_str = eid.decode() if isinstance(eid, bytes) else eid
            n += 1
            print(f"[loop #{n}] alg_return={cur_phase} id={eid_str}")
        except redis.exceptions.RedisError as e:
            print(f"[loop] xadd 异常: {e}")

        steps = max(1, int(args.interval * 10))
        for _ in range(steps):
            if stop["flag"]:
                break
            time.sleep(0.1)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
