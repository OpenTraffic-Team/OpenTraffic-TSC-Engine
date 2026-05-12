"""
HHL_QHDD signal_env_state 流模拟器

行为:
  1. 以 1Hz 节奏向 Redis Stream `signal_env_state:HHL_QHDD` 推送 env_state。
  2. 启动初期: currentPhase 在 [1, 2] 间循环, 每相位固定运行 40 秒。
  3. 同时监听 `algorithm_control:HHL_QHDD` 流, 一旦读到非空的 alg_return,
     currentPhase 立即切换为该值, 并从此跟随算法输出 (放弃 40s 自动循环)。

数据格式 (与项目 redis_stream.push_data 一致):
  XADD <stream_key> * data <json_string>
  其中 json_string =
    {"currentPhase":1,"currentPlan":"1","phaseTime":31,"phases":[1,2],
     "signalCtlStatus":false,"timestamp":1760167576.309}
"""
import json
import signal
import threading
import time
from typing import Optional

import redis


# ============================================================
# 配置 (有疑问改这里)
# ============================================================
INTERSECTION_ID = "HHL_QHDD"   # 用户原文写的是 HLH_QHDD/HLH_QHHDD, 看上去是 HHL_QHDD 的笔误

ENV_STREAM_KEY  = f"signal_env_state:{INTERSECTION_ID}"
ALGO_STREAM_KEY = f"algorithm_control:{INTERSECTION_ID}"   # 算法 push 用的就是冒号分隔, 见 advanced_control.py L184

# Redis 连接
REDIS_HOST     = "47.110.91.222"
REDIS_PORT     = 6390
REDIS_USERNAME = "default"
REDIS_PASSWORD = "TempRedis_2026_LinkOnly_9f3K"
ENV_DB         = 0   # signal_env_state 推送目标 db (与 mq_config.json env_state.db 对齐)
ALGO_DB        = 0   # algorithm_control 监听 db (与 mq_config.json algorithm_control.db 对齐)

# 推送 / 相位调度
PUSH_INTERVAL_SEC = 1.0
PHASE_DURATION    = 40       # 每个相位固定持续 (秒); 收到 alg_return 后失效
PHASES            = [1, 2]   # 自动循环用的相位池
INITIAL_PHASE     = 1
INITIAL_PLAN      = "1"
STREAM_MAXLEN     = 10000


# ============================================================
# 共享状态
# ============================================================
class SharedState:
    """主线程 / 监听线程之间共享的相位状态."""

    def __init__(self):
        self.lock = threading.Lock()
        self.current_phase: int = INITIAL_PHASE
        self.phase_time: int = 1                # 1-indexed (用户示例里 phaseTime=31 是这种风格)
        self.algo_taken_over: bool = False

    def step_one_second_auto(self):
        """40s 循环模式下, 每秒自动推进 phase_time, 到点切相位."""
        with self.lock:
            if self.algo_taken_over:
                self.phase_time += 1
                return
            if self.phase_time >= PHASE_DURATION:
                idx = PHASES.index(self.current_phase) if self.current_phase in PHASES else 0
                self.current_phase = PHASES[(idx + 1) % len(PHASES)]
                self.phase_time = 1
            else:
                self.phase_time += 1

    def apply_algo_return(self, alg_return: int) -> bool:
        """收到一个有效的 alg_return, 返回是否真的发生了相位切换."""
        with self.lock:
            switched = (not self.algo_taken_over) or (alg_return != self.current_phase)
            self.algo_taken_over = True
            if alg_return != self.current_phase:
                self.current_phase = alg_return
                self.phase_time = 1
            return switched

    def snapshot(self):
        with self.lock:
            return self.current_phase, self.phase_time, self.algo_taken_over


# ============================================================
# Redis 工具
# ============================================================
def make_redis_client(db: int) -> redis.Redis:
    return redis.Redis(
        host=REDIS_HOST,
        port=REDIS_PORT,
        username=REDIS_USERNAME,
        password=REDIS_PASSWORD,
        db=db,
        socket_connect_timeout=10,
        max_connections=5,
        decode_responses=False,
    )


def decode_entry_payload(entry_data: dict) -> Optional[dict]:
    """xread 返回的 entry_data, 把 bytes 解码 + 解析里面的 data JSON."""
    decoded = {}
    for k, v in entry_data.items():
        if isinstance(k, bytes):
            k = k.decode("utf-8")
        if isinstance(v, bytes):
            v = v.decode("utf-8")
        decoded[k] = v
    raw = decoded.get("data")
    if raw is None:
        return None
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        return {"_raw": raw}


# ============================================================
# 监听线程: 跟踪 algorithm_control 流
# ============================================================
def algo_listener(state: SharedState, stop_event: threading.Event):
    client = make_redis_client(ALGO_DB)
    last_id = "$"   # 只关心从启动后新 push 的数据, 不回看历史
    print(f"[listener] 监听 {ALGO_STREAM_KEY} (db={ALGO_DB}), 起始 id={last_id}")

    while not stop_event.is_set():
        try:
            result = client.xread({ALGO_STREAM_KEY: last_id}, count=10, block=2000)
        except redis.exceptions.RedisError as e:
            print(f"[listener] xread 异常: {e}, 2s 后重试")
            stop_event.wait(2.0)
            continue
        except Exception as e:
            print(f"[listener] 未预期异常: {e}, 2s 后重试")
            stop_event.wait(2.0)
            continue

        if not result:
            continue

        for _stream_key_bytes, entries in result:
            for entry_id, entry_data in entries:
                if isinstance(entry_id, bytes):
                    entry_id = entry_id.decode("utf-8")
                last_id = entry_id

                payload = decode_entry_payload(entry_data)
                if payload is None:
                    print(f"[listener] {entry_id}: 无 data 字段, 忽略")
                    continue

                alg_return = payload.get("alg_return")
                ts = payload.get("timestamp")

                if alg_return in (None, "None", "null", ""):
                    print(f"[listener] {entry_id}: alg_return=None (ts={ts}), 不切相位")
                    continue

                try:
                    alg_return_int = int(float(alg_return))
                except (TypeError, ValueError):
                    print(f"[listener] {entry_id}: alg_return={alg_return!r} 无法转 int, 忽略")
                    continue

                switched = state.apply_algo_return(alg_return_int)
                tag = "切相位" if switched else "保持"
                print(f"[listener] {entry_id}: alg_return={alg_return_int} ({tag}), ts={ts}")

    try:
        client.close()
    except Exception:
        pass


# ============================================================
# 主线程: 推送 signal_env_state
# ============================================================
def env_publisher(state: SharedState, stop_event: threading.Event):
    client = make_redis_client(ENV_DB)
    print(f"[publisher] 开始推送 {ENV_STREAM_KEY} (db={ENV_DB}), 间隔 {PUSH_INTERVAL_SEC}s")

    next_tick = time.monotonic()
    push_count = 0
    while not stop_event.is_set():
        cur_phase, phase_time, taken = state.snapshot()

        env_state = {
            "currentPhase":    cur_phase,
            "currentPlan":     INITIAL_PLAN,
            "phaseTime":       phase_time,
            "phases":          PHASES,
            "signalCtlStatus": False,
            "timestamp":       round(time.time(), 3),
        }
        payload = {"data": json.dumps(env_state, ensure_ascii=False)}

        try:
            entry_id = client.xadd(ENV_STREAM_KEY, payload, maxlen=STREAM_MAXLEN)
            push_count += 1
            mode_tag = "ALGO" if taken else "AUTO"
            if push_count == 1 or push_count % 5 == 0 or phase_time == 1:
                print(
                    f"[publisher] #{push_count} mode={mode_tag} "
                    f"phase={cur_phase} phaseTime={phase_time} "
                    f"id={entry_id.decode() if isinstance(entry_id, bytes) else entry_id}"
                )
        except redis.exceptions.RedisError as e:
            print(f"[publisher] xadd 异常: {e}, 不计数, 1s 后重试")

        state.step_one_second_auto()

        next_tick += PUSH_INTERVAL_SEC
        sleep_for = max(0.0, next_tick - time.monotonic())
        stop_event.wait(sleep_for)

    try:
        client.close()
    except Exception:
        pass


# ============================================================
# 入口
# ============================================================
def main():
    print("=" * 70)
    print(f"signal_env_state 流模拟器 - {INTERSECTION_ID}")
    print(f"  Redis:   {REDIS_HOST}:{REDIS_PORT} (user={REDIS_USERNAME})")
    print(f"  push:    {ENV_STREAM_KEY} -> db {ENV_DB} ({PUSH_INTERVAL_SEC}s/次)")
    print(f"  listen:  {ALGO_STREAM_KEY} -> db {ALGO_DB}")
    print(f"  规则:     初始 [1,2] 各 {PHASE_DURATION}s 循环;")
    print(f"           收到非空 alg_return 后跟随算法相位")
    print("=" * 70)

    # 连通性自检
    try:
        client = make_redis_client(ENV_DB)
        client.ping()
        print("[init] Redis ping OK")
        client.close()
    except Exception as e:
        print(f"[init] Redis 连接失败: {e}")
        return 1

    state = SharedState()
    stop_event = threading.Event()

    def handle_signal(signum, _frame):
        print(f"\n[main] 收到信号 {signum}, 准备退出 ...")
        stop_event.set()

    signal.signal(signal.SIGINT, handle_signal)
    signal.signal(signal.SIGTERM, handle_signal)

    listener_thread = threading.Thread(
        target=algo_listener, args=(state, stop_event),
        name="algo-listener", daemon=True,
    )
    listener_thread.start()

    try:
        env_publisher(state, stop_event)
    finally:
        stop_event.set()
        listener_thread.join(timeout=3.0)
        print("[main] 已退出")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
