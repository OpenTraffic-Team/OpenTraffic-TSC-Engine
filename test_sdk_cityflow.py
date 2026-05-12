#!/usr/bin/env python3
"""
CityFlow 集成测试
使用算法SDK（AdvancedControl）控制CityFlow交通仿真，并生成回放文件。

运行方法（在 trafficlight 环境下，从项目根目录执行）:
    python test_sdk_cityflow.py                  # 默认 3600 步仿真
    python test_sdk_cityflow.py --steps 600      # 自定义步数
    python test_sdk_cityflow.py --fixed          # 固定配时对比模式

回放查看:
    仿真结束后，replay 文件自动写入 frontend/web/ 目录。
    用浏览器直接打开 frontend/index.html，上传以下两个文件即可：
      frontend/web/roadnet_log.json
      frontend/web/replay.txt
"""
import sys
import os
import time
import argparse
import copy
import json
import random
import math

script_dir = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, script_dir)

try:
    import cityflow
except ImportError:
    print("未找到 CityFlow 库，使用内置 Mock 引擎（仅供算法逻辑验证）")
    from algorithms_sdk.mock.cityflow_mock import Engine as _MockEngine
    import types
    cityflow = types.ModuleType("cityflow")
    cityflow.Engine = _MockEngine

FLOW_PATH = os.path.join(script_dir, "config", "cityflow", "flow.json")

# 所有路由定义：(起始路段, 终止路段, 方向描述)
_ROUTES = [
    ("HHL_QHDD_N", "HHL_QHDD_S_out", "N→S"),
    ("HHL_QHDD_N", "HHL_QHDD_E_out", "N→E"),
    ("HHL_QHDD_S", "HHL_QHDD_N_out", "S→N"),
    ("HHL_QHDD_S", "HHL_QHDD_W_out", "S→W"),
    ("HHL_QHDD_E", "HHL_QHDD_W_out", "E→W"),
    ("HHL_QHDD_E", "HHL_QHDD_S_out", "E→S"),
    ("HHL_QHDD_W", "HHL_QHDD_E_out", "W→E"),
    ("HHL_QHDD_W", "HHL_QHDD_N_out", "W→N"),
]

_VEHICLE_TPL = {
    "length": 5.0, "width": 2.0,
    "maxPosAcc": 2.0, "maxNegAcc": 4.5,
    "usualPosAcc": 2.0, "usualNegAcc": 4.5,
    "minGap": 2.5, "maxSpeed": 16.67, "headwayTime": 1.5
}


def generate_random_flow(total_seconds: int, seed: int = None) -> dict:
    """
    生成随机车流并写入 flow.json。
    每条路由一个 flow entry，interval = 平均发车间隔。
    CityFlow 忽略 endTime 且大 interval 会使 startTime 归零，
    因此用 route 级别 entry + 合理 interval 保证全时段均匀发车。

    返回各路由流量 (veh/h) 的字典。
    """
    if seed is not None:
        random.seed(seed)

    # 单路口容量：300m 道路 + 2 车道，600-1000 veh/h 可稳定运行
    ns_total = random.uniform(200, 500)    # N+S 方向总量
    ew_total = random.uniform(100, 350)    # E+W 方向总量

    rates_vph = {
        "N→S": ns_total * 0.55,
        "N→E": ns_total * 0.20,
        "S→N": ns_total * 0.55,
        "S→W": ns_total * 0.20,
        "E→W": ew_total * 0.55,
        "E→S": ew_total * 0.20,
        "W→E": ew_total * 0.55,
        "W→N": ew_total * 0.20,
    }

    flows = []
    for src, dst, desc in _ROUTES:
        rate_vph = rates_vph[desc]
        if rate_vph < 1:
            continue
        mean_gap = 3600.0 / rate_vph
        # 首车在 [0, mean_gap) 内随机偏移，避免所有路由同时发车
        first_car_offset = random.uniform(0, mean_gap)
        flows.append({
            "vehicle":   _VEHICLE_TPL,
            "route":     [src, dst],
            "interval":  round(mean_gap, 2),
            "startTime": round(first_car_offset, 2),
            "endTime":   round(total_seconds + 10, 2),
        })

    with open(FLOW_PATH, "w") as f:
        json.dump(flows, f, indent=2)

    return rates_vph


from algorithms_sdk.advanced_control import AdvancedControl

# ─── 路口配置 ──────────────────────────────────────────────────────────────
INTERSECTION_ID   = "HHL_QHDD"
CF_CONFIG_PATH    = os.path.join(script_dir, "config", "cityflow", "config.json")
ALGO_CONFIG_PATH  = os.path.join(script_dir, "config", "cityflow", "algo_config.yaml")

# CityFlow lightphases 顺序（与 roadnet.json 中一致，index 0 为全红）:
#   index 0: 全红（过渡用）
#   index 1: WE_EW_WN_ES
#   index 2: NS_SN_NE_SW
CITYFLOW_PHASE_LIST = ["WE_EW_WN_ES", "NS_SN_NE_SW"]  # 不含全红，与 lightphases[1:] 对应

# 信号机相位编号（与 stagePhase / algConfig 一致）
ENV_STATE_PHASES = [1, 2]
INITIAL_PHASE    = 1   # 初始相位编号

# 过渡时间（秒）
TRANSITION_GREEN_TIME  = 3   # 绿闪时长：切相前保持当前相位
TRANSITION_YELLOW_TIME = 3   # 全红时长：完全熄灭后再亮新相位


# ─── 工具函数 ──────────────────────────────────────────────────────────────
def phase_num_to_cf_index(phase_num: int, current_plan_stage_phase: dict) -> int:
    """
    将算法输出的相位编号（整数）转为 CityFlow 信号灯相位下标。
    roadnet.json 中 lightphases[0]=全红，lightphases[1..n]=实际相位，所以结果 +1。
    """
    phase_name = current_plan_stage_phase[phase_num]
    return CITYFLOW_PHASE_LIST.index(phase_name) + 1


def build_env_state(current_phase_num: int, phase_time: float) -> dict:
    """构造算法所需的信号机环境状态（格式与 signal_env_simulator 一致）"""
    return {
        "phases":          ENV_STATE_PHASES,
        "currentPhase":    current_phase_num,
        "phaseTime":       int(phase_time),
        "currentPlan":     str(current_phase_num),
        "signalCtlStatus": True,
        "timestamp":       time.time(),
    }


def get_inter_state(eng, lane_to_phase: dict):
    """
    从 CityFlow 引擎读取当前路口的进场车道状态。
    返回:
        inter_lane_info: {lane_id: [vehicle_id, ...]}  只含 lane_to_phase 定义的进场车道
        inter_vehicles:  {vehicle_id: vehicle_info_dict}
    """
    all_lane_vehicles = eng.get_lane_vehicles()
    inter_lane_info = {
        lane: all_lane_vehicles.get(lane, [])
        for lane in lane_to_phase
    }
    vehicle_ids = {v for vlist in inter_lane_info.values() for v in vlist}
    inter_vehicles = {vid: eng.get_vehicle_info(vid) for vid in vehicle_ids}
    return inter_lane_info, inter_vehicles


# ─── 仿真主函数 ────────────────────────────────────────────────────────────
def run_simulation(total_steps: int = 3600, fixed_timing: bool = False):
    print("=" * 65)
    print("  OpenTraffic × CityFlow 集成仿真测试")
    print("=" * 65)

    # ── 0. 生成随机车流 ──────────────────────────────────────────────
    rng_seed = int(time.time()) % 100000
    rates = generate_random_flow(total_seconds=total_steps, seed=rng_seed)
    ns_vph = rates["N→S"] + rates["S→N"]
    ew_vph = rates["E→W"] + rates["W→E"]
    print(f"\n[0] 随机车流已生成（seed={rng_seed}）")
    print(f"    NS方向: {ns_vph:.0f} veh/h  |  EW方向: {ew_vph:.0f} veh/h  "
          f"|  NS/EW = {ns_vph/max(ew_vph,1):.2f}x")

    # ── 1. 初始化算法（test=True：不连接 Redis，从 yaml 读配置）────
    print("\n[1] 初始化算法（CityFlow 测试模式）...")
    algo = AdvancedControl(config_path=ALGO_CONFIG_PATH, test=True)
    # 测试模式下 SIGNAL_IN_CONTROL 默认为 0（无 Redis），
    # 需置为 1 以启用 CheckTransitionRule，防止 ACTION_HISTORY 交替振荡
    algo.config.SIGNAL_IN_CONTROL = 1
    print(f"    算法版本   : {algo.config.ALGO_VERSION}")
    print(f"    路口编号   : {algo.config.INTERSECTION}")
    print(f"    相位方案   : {algo.config.PHASES}")
    print(f"    进场车道数 : {len(algo.config.LANE_TO_PHASE)}")

    # ── 2. 创建 CityFlow 引擎 ────────────────────────────────────────────
    print(f"\n[2] 启动 CityFlow 引擎...")
    eng = cityflow.Engine(CF_CONFIG_PATH, thread_num=1)
    eng.reset()

    # 将路口初始信号灯设为全红（index 0）
    eng.set_tl_phase(INTERSECTION_ID, 0)
    print(f"    引擎已创建，初始相位：全红")
    print(f"    回放文件输出至: frontend/web/")

    # ── 3. 初始化状态变量 ────────────────────────────────────────────────
    last_phase    = INITIAL_PHASE   # 当前实际执行的相位编号
    last_decision = None            # 上一步算法决策（用于延迟一步应用）
    transition_cnt = 0              # 过渡倒计时（秒）；>0 表示正在过渡
    phase_time     = 0              # 当前相位已保持的秒数

    sim_time    = 0
    interval    = 1.0   # 与 config.json interval 一致

    # 统计用
    all_vehicle_ids = set()
    wait_accum      = 0
    switch_log      = []

    mode_label = "固定配时（对比模式）" if fixed_timing else "自适应算法控制"
    print(f"\n[3] 开始仿真：{mode_label}，共 {total_steps} 步")
    print("-" * 65)

    for step in range(total_steps):
        eng.next_step()
        time.sleep(0.5)  # 放慢仿真速度，方便观察
        sim_time += interval

        # 统计
        all_vehicle_ids |= set(eng.get_vehicles(True))
        wait_accum      += sum(eng.get_lane_waiting_vehicle_count().values())

        # ── 固定配时模式 ──────────────────────────────────────────────
        if fixed_timing:
            phase_time += interval
            if phase_time >= 40:
                last_phase = (last_phase % len(ENV_STATE_PHASES)) + 1
                phase_time = 0
            eng.set_tl_phase(INTERSECTION_ID, last_phase)   # 1 or 2 directly
            if step % 30 == 0:
                _print_status(sim_time, last_phase, phase_time, transition_cnt, eng)
            continue

        # ── 算法控制模式 ──────────────────────────────────────────────
        inter_lane_info, inter_vehicles = get_inter_state(eng, algo.config.LANE_TO_PHASE)
        vehicle_map = algo.convert_cur_state_cf(inter_lane_info, inter_vehicles)

        state     = {INTERSECTION_ID: copy.deepcopy(vehicle_map)}
        env_state = build_env_state(last_phase, phase_time)

        phase = algo.take_action(state, env_state)

        # debug：每10步打印一次算法输入/输出
        if step % 10 == 0:
            run_map  = vehicle_map.get("running_vehicle", {})
            wait_map = vehicle_map.get("waiting_vehicle", {})
            p1_wait = wait_map.get("WE",0)+wait_map.get("EW",0)+wait_map.get("WN",0)+wait_map.get("ES",0)
            p2_wait = wait_map.get("NS",0)+wait_map.get("SN",0)+wait_map.get("NE",0)+wait_map.get("SW",0)
            p1_run  = run_map.get("WE",0)+run_map.get("EW",0)+run_map.get("WN",0)+run_map.get("ES",0)
            p2_run  = run_map.get("NS",0)+run_map.get("SN",0)+run_map.get("NE",0)+run_map.get("SW",0)
            print(f"  [DBG t={sim_time:.0f}s] 当前相位:{last_phase} phaseTime:{phase_time:.0f}s "
                  f"tc:{transition_cnt:.0f} 算法返回:{phase}"
                  f" | WE组 行:{p1_run} 等:{p1_wait}  NS组 行:{p2_run} 等:{p2_wait}")

        # 后置安全规则
        algo.post_safe_rules.excute_rules_chain(state, env_state, phase)

        CURRENT_PLAN_STAGE_PHASE = algo.config.CURRENT_PLAN_STAGE_PHASE

        if transition_cnt <= 0:
            # ── 正常运行：应用上一步决策 ────────────────────────────
            if last_decision is not None and last_decision != last_phase:
                switch_log.append({
                    "time": sim_time, "from": last_phase,
                    "to": last_decision, "held_for": phase_time
                })
                print(f"\n  ★ [t={sim_time:.0f}s] 相位切换: {last_phase} → {last_decision} "
                      f"（已保持 {phase_time:.0f}s）")
                last_phase = last_decision
                phase_time = 1
            else:
                phase_time += interval

            # 本轮决策是否触发新过渡
            if phase is not None and phase != last_phase:
                phase_name = CURRENT_PLAN_STAGE_PHASE.get(phase, "")
                if "follow" in phase_name:
                    last_phase = phase
                    phase_time = 1
                else:
                    transition_cnt = TRANSITION_GREEN_TIME + TRANSITION_YELLOW_TIME

            cf_idx = phase_num_to_cf_index(last_phase, CURRENT_PLAN_STAGE_PHASE)
            eng.set_tl_phase(INTERSECTION_ID, cf_idx)

        else:
            # ── 过渡进行中 ──────────────────────────────────────────
            phase_time += interval
            if phase == last_phase:
                # 算法反悔，取消过渡（CheckTransitionRule 已激活时不会频繁触发）
                transition_cnt = 0
                cf_idx = phase_num_to_cf_index(last_phase, CURRENT_PLAN_STAGE_PHASE)
                eng.set_tl_phase(INTERSECTION_ID, cf_idx)
            elif transition_cnt <= TRANSITION_YELLOW_TIME:
                # 全红阶段
                transition_cnt -= interval
                eng.set_tl_phase(INTERSECTION_ID, 0)
            else:
                # 绿闪阶段
                transition_cnt -= interval
                cf_idx = phase_num_to_cf_index(last_phase, CURRENT_PLAN_STAGE_PHASE)
                eng.set_tl_phase(INTERSECTION_ID, cf_idx)

        last_decision = phase

        # 每 30 步打印一次
        if step % 30 == 0:
            _print_status(sim_time, last_phase, phase_time, transition_cnt, eng)

    # ── 4. 仿真结束统计 ──────────────────────────────────────────────────
    print("-" * 65)
    print(f"\n[4] 仿真结束")
    print(f"    总步数         : {total_steps} 步（{total_steps}s）")
    print(f"    生成车辆总数   : {len(all_vehicle_ids)} 辆")
    print(f"    平均通行时间   : {eng.get_average_travel_time():.1f} 秒/辆")
    print(f"    累计等待车辆次 : {wait_accum}")
    if not fixed_timing:
        print(f"    相位切换次数   : {len(switch_log)} 次")

    # ── 5. 回放说明 ──────────────────────────────────────────────────────
    print(f"\n[5] 回放文件已写入:")
    print(f"    frontend/web/roadnet_log.json")
    print(f"    frontend/web/replay.txt")
    print()
    print("    查看方法：")
    print("      用浏览器打开  frontend/index.html")
    print("      点击 'Roadnet File' 上传  frontend/web/roadnet_log.json")
    print("      点击 'Replay File'  上传  frontend/web/replay.txt")
    print("      点击 'Start' 开始播放")


def _print_status(sim_time, phase_num, phase_time, trans_cnt, eng):
    waiting = sum(eng.get_lane_waiting_vehicle_count().values())
    total   = eng.get_vehicle_count()
    trans_s = f" [过渡中 {trans_cnt:.0f}s]" if trans_cnt > 0 else ""
    print(f"  [t={sim_time:>5.0f}s] 相位:{phase_num}  保持:{phase_time:>4.0f}s{trans_s}"
          f"  等待:{waiting:>3d}辆  总车:{total:>3d}辆")


# ─── 入口 ─────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="CityFlow × OpenTraffic 集成仿真测试")
    parser.add_argument("--steps", type=int,       default=3600, help="仿真步数（秒），默认3600")
    parser.add_argument("--fixed", action="store_true",          help="固定配时对比模式")
    args = parser.parse_args()

    run_simulation(total_steps=args.steps, fixed_timing=args.fixed)
