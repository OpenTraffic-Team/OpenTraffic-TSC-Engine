"""
CityFlow 模拟器（Mock）
当真实的 CityFlow 库未安装时，提供相同的 API 接口以供算法测试使用。

注意：此 Mock 仅用于验证算法逻辑，不进行真实物理仿真。
      车辆数量以随机模拟方式生成，结果不可用于性能评估。

安装真实 CityFlow（Python ≤ 3.10）:
    conda create -n cf python=3.10
    conda activate cf
    pip install git+https://github.com/cityflow-project/CityFlow.git
"""

import json
import random
import math
import os


class _Archive:
    """快照存档对象"""
    def __init__(self, state: dict):
        self._state = state

    def dump(self, path: str):
        os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
        with open(path, "w") as f:
            json.dump(self._state, f, indent=2)


class Engine:
    """
    CityFlow Engine Mock
    实现与真实 CityFlow Engine 相同的 Python API，供算法集成测试使用。
    """

    def __init__(self, config_path: str, thread_num: int = 1):
        config_path = os.path.abspath(config_path)
        config_dir  = os.path.dirname(config_path)

        with open(config_path) as f:
            cfg = json.load(f)

        self._interval   = cfg.get("interval", 1.0)
        self._sim_time   = 0.0
        self._step_count = 0
        self._save_replay = cfg.get("saveReplay", False)
        self._rl_tl       = cfg.get("rlTrafficLight", False)

        # 相对路径解析（dir 是相对于当前工作目录的路径）
        data_dir = os.path.join(os.getcwd(), cfg.get("dir", ""))
        roadnet_path = os.path.join(data_dir, cfg["roadnetFile"])
        flow_path    = os.path.join(data_dir, cfg["flowFile"])

        # 加载路网
        with open(roadnet_path) as f:
            roadnet = json.load(f)

        self._intersections = {i["id"]: i for i in roadnet["intersections"]}
        self._roads         = {r["id"]: r for r in roadnet["roads"]}

        # 提取所有进场车道（非 _out 且非 virtual 路口的道路）
        self._incoming_lanes: list[str] = []
        for road_id, road in self._roads.items():
            end_inter = road.get("endIntersection", "")
            if "virtual" not in end_inter and "out" not in road_id:
                num_lanes = len(road.get("lanes", []))
                for i in range(num_lanes):
                    self._incoming_lanes.append(f"{road_id}_{i}")

        self._outgoing_lanes: list[str] = []
        for road_id, road in self._roads.items():
            end_inter = road.get("endIntersection", "")
            if "virtual" in end_inter or "out" in road_id:
                num_lanes = len(road.get("lanes", []))
                for i in range(num_lanes):
                    self._outgoing_lanes.append(f"{road_id}_{i}")

        # 加载车流定义
        with open(flow_path) as f:
            self._flow_defs = json.load(f)

        # 仿真状态
        self._current_phases: dict[str, int] = {}
        self._phase_elapsed:  dict[str, float] = {}
        for inter_id, inter in self._intersections.items():
            if not inter.get("virtual", False):
                self._current_phases[inter_id]  = 0
                self._phase_elapsed[inter_id]   = 0.0

        # 车辆状态  {vehicle_id: {lane, speed, distance, running}}
        self._vehicles:    dict[str, dict] = {}
        self._next_vid     = 0
        self._travel_times: list[float] = []

        # Replay 文件
        if self._save_replay:
            self._replay_dir = data_dir
            replay_file = cfg.get("replayLogFile", "replay/replay.txt")
            roadnet_log = cfg.get("roadnetLogFile", "replay/roadnet_log.json")
            replay_dir  = os.path.join(data_dir, os.path.dirname(replay_file))
            os.makedirs(replay_dir, exist_ok=True)
            self._replay_path    = os.path.join(data_dir, replay_file)
            self._roadnet_log    = os.path.join(data_dir, roadnet_log)
            self._replay_file    = open(self._replay_path, "w")
            self._write_roadnet_log(roadnet)

    def _write_roadnet_log(self, roadnet: dict):
        """写入回放用路网文件（与原始路网文件相同）"""
        with open(self._roadnet_log, "w") as f:
            json.dump(roadnet, f)

    def _write_replay_frame(self):
        """写入一帧回放数据"""
        if not self._save_replay:
            return

        vehicles_data = []
        for vid, info in self._vehicles.items():
            vehicles_data.append({
                "id": vid,
                "lane": info["drivable"],
                "speed": info["speed"],
                "distance": info["distance"],
            })

        tl_data = {}
        for inter_id in self._current_phases:
            phase_idx = self._current_phases[inter_id]
            inter     = self._intersections[inter_id]
            phases    = inter.get("trafficLight", {}).get("lightphases", [])
            phase_obj = phases[phase_idx] if phase_idx < len(phases) else {}
            tl_data[inter_id] = {
                "phase":          phase_idx,
                "availableLinks": phase_obj.get("availableRoadLinks", []),
            }

        frame = {
            "time":     self._sim_time,
            "vehicles": vehicles_data,
            "signals":  tl_data,
        }
        self._replay_file.write(json.dumps(frame) + "\n")

    def next_step(self):
        """推进仿真一步"""
        self._sim_time  += self._interval
        self._step_count += 1

        self._spawn_vehicles()
        self._update_vehicles()
        self._update_signals()

        if self._save_replay:
            self._write_replay_frame()

    def _spawn_vehicles(self):
        """按 flow.json 中的间隔生成新车辆"""
        for flow in self._flow_defs:
            if flow["startTime"] <= self._sim_time <= flow["endTime"]:
                interval = flow["interval"]
                if self._step_count % max(1, int(interval / self._interval)) == 0:
                    route = flow["route"]
                    if not route:
                        continue
                    first_road = route[0]
                    road = self._roads.get(first_road)
                    if not road:
                        continue
                    num_lanes = len(road.get("lanes", []))
                    lane_idx  = random.randint(0, num_lanes - 1)
                    lane_id   = f"{first_road}_{lane_idx}"

                    vid = f"v_{self._next_vid}"
                    self._next_vid += 1
                    max_speed = flow["vehicle"].get("maxSpeed", 16.67)
                    self._vehicles[vid] = {
                        "running":     "1",
                        "speed":       str(random.uniform(5.0, max_speed)),
                        "distance":    "0.0",
                        "drivable":    lane_id,
                        "road":        first_road,
                        "intersection": route[1] if len(route) > 1 else "",
                        "route":       " ".join(route[1:]),
                        "_route_list": route,
                        "_route_idx":  0,
                        "_on_road_dist": 0.0,
                        "_spawn_time": self._sim_time,
                    }

    def _update_vehicles(self):
        """更新车辆位置和状态（简化物理模型）"""
        to_remove = []
        for vid, v in self._vehicles.items():
            # 确定是否在绿灯相位
            road_id  = v["road"] if v["road"] else v["drivable"].rsplit("_", 1)[0]
            end_inter_id = self._roads.get(road_id, {}).get("endIntersection", "")

            is_green = True
            if end_inter_id and end_inter_id in self._current_phases:
                inter      = self._intersections[end_inter_id]
                phase_idx  = self._current_phases[end_inter_id]
                phases     = inter.get("trafficLight", {}).get("lightphases", [])
                phase_obj  = phases[phase_idx] if phase_idx < len(phases) else {}
                # 判断当前车道是否在绿灯路口链路中（简化：随机）
                available  = phase_obj.get("availableRoadLinks", [])
                road_links = inter.get("roadLinks", [])
                for rl_idx in available:
                    if rl_idx < len(road_links):
                        rl = road_links[rl_idx]
                        if rl.get("startRoad") == road_id:
                            is_green = True
                            break
                else:
                    # 检查是否有路口链路以当前道路为起点
                    has_link = any(
                        road_links[idx].get("startRoad") == road_id
                        for idx in range(len(road_links))
                        if idx < len(road_links)
                    )
                    is_green = not has_link  # 如果没有相关链路，不受信号控制

            max_speed = 16.67
            road_info = self._roads.get(road_id, {})
            if road_info.get("lanes"):
                max_speed = road_info["lanes"][0].get("maxSpeed", 16.67)

            road_length = 300.0  # 默认道路长度

            dist_ahead = road_length - v["_on_road_dist"]
            near_stop  = dist_ahead < 30 and not is_green

            if near_stop:
                target_speed = 0.0
            else:
                target_speed = max_speed

            cur_speed = float(v["speed"])
            new_speed = cur_speed + (target_speed - cur_speed) * 0.3 + random.uniform(-0.5, 0.5)
            new_speed = max(0.0, min(new_speed, max_speed))
            v["speed"] = str(round(new_speed, 2))

            new_dist = v["_on_road_dist"] + new_speed * self._interval
            v["_on_road_dist"] = new_dist
            v["distance"] = str(round(new_dist, 2))

            if new_dist >= road_length:
                # 车辆到达路段末端
                route_list = v["_route_list"]
                route_idx  = v["_route_idx"] + 1
                if route_idx < len(route_list) - 1:
                    # 进入下一条路段
                    next_road = route_list[route_idx]
                    next_road_info = self._roads.get(next_road, {})
                    num_lanes = len(next_road_info.get("lanes", []))
                    lane_idx  = random.randint(0, max(0, num_lanes - 1))
                    v["_route_idx"]   = route_idx
                    v["_on_road_dist"] = 0.0
                    v["road"]         = next_road
                    v["drivable"]     = f"{next_road}_{lane_idx}"
                    v["intersection"] = route_list[route_idx + 1] if route_idx + 1 < len(route_list) else ""
                else:
                    # 车辆离开仿真
                    travel_time = self._sim_time - v["_spawn_time"]
                    self._travel_times.append(travel_time)
                    to_remove.append(vid)

        for vid in to_remove:
            del self._vehicles[vid]

    def _update_signals(self):
        """更新信号灯相位（仅在非 RL 模式下自动切换）"""
        if self._rl_tl:
            return  # RL 模式：由外部 set_tl_phase 控制
        for inter_id in self._current_phases:
            self._phase_elapsed[inter_id] += self._interval
            inter  = self._intersections[inter_id]
            phases = inter.get("trafficLight", {}).get("lightphases", [])
            if not phases:
                continue
            cur_idx  = self._current_phases[inter_id]
            cur_time = phases[cur_idx].get("time", 40)
            if self._phase_elapsed[inter_id] >= cur_time:
                self._current_phases[inter_id] = (cur_idx + 1) % len(phases)
                self._phase_elapsed[inter_id]  = 0.0

    # ─── Data Access API ─────────────────────────────────────────
    def get_vehicle_count(self) -> int:
        return len(self._vehicles)

    def get_vehicles(self, include_waiting: bool = False) -> list:
        if include_waiting:
            return list(self._vehicles.keys())
        return [vid for vid, v in self._vehicles.items() if v["running"] == "1"]

    def get_lane_vehicle_count(self) -> dict:
        counts = {lane: 0 for lane in self._incoming_lanes + self._outgoing_lanes}
        for v in self._vehicles.values():
            lane = v["drivable"]
            if lane in counts:
                counts[lane] += 1
        return counts

    def get_lane_waiting_vehicle_count(self) -> dict:
        counts = {lane: 0 for lane in self._incoming_lanes + self._outgoing_lanes}
        for v in self._vehicles.values():
            if float(v["speed"]) < 0.1:
                lane = v["drivable"]
                if lane in counts:
                    counts[lane] += 1
        return counts

    def get_lane_vehicles(self) -> dict:
        result = {lane: [] for lane in self._incoming_lanes + self._outgoing_lanes}
        for vid, v in self._vehicles.items():
            lane = v["drivable"]
            if lane in result:
                result[lane].append(vid)
        return result

    def get_vehicle_info(self, vehicle_id: str) -> dict:
        v = self._vehicles.get(vehicle_id, {})
        return {
            "running":      v.get("running", "0"),
            "speed":        v.get("speed", "0"),
            "distance":     v.get("distance", "0"),
            "drivable":     v.get("drivable", ""),
            "road":         v.get("road", ""),
            "intersection": v.get("intersection", ""),
            "route":        v.get("route", ""),
        }

    def get_vehicle_speed(self) -> dict:
        return {vid: float(v["speed"]) for vid, v in self._vehicles.items()}

    def get_vehicle_distance(self) -> dict:
        return {vid: float(v["distance"]) for vid, v in self._vehicles.items()}

    def get_leader(self, vehicle_id: str) -> str:
        return ""

    def get_current_time(self) -> float:
        return self._sim_time

    def get_average_travel_time(self) -> float:
        if not self._travel_times:
            return 0.0
        return sum(self._travel_times) / len(self._travel_times)

    # ─── Control API ─────────────────────────────────────────────
    def set_tl_phase(self, intersection_id: str, phase_id: int):
        """设置交叉路口的信号灯相位（仅在 rlTrafficLight=true 时有效）"""
        if self._rl_tl and intersection_id in self._current_phases:
            inter  = self._intersections[intersection_id]
            phases = inter.get("trafficLight", {}).get("lightphases", [])
            if 0 <= phase_id < len(phases):
                if self._current_phases[intersection_id] != phase_id:
                    self._phase_elapsed[intersection_id] = 0.0
                self._current_phases[intersection_id] = phase_id

    def set_vehicle_speed(self, vehicle_id: str, speed: float):
        if vehicle_id in self._vehicles:
            self._vehicles[vehicle_id]["speed"] = str(speed)

    def reset(self, seed: bool = False):
        self._vehicles    = {}
        self._sim_time    = 0.0
        self._step_count  = 0
        self._next_vid    = 0
        self._travel_times = []
        for inter_id in self._current_phases:
            self._current_phases[inter_id] = 0
            self._phase_elapsed[inter_id]  = 0.0
        if seed:
            random.seed(random.randint(0, 10000))

    def snapshot(self) -> _Archive:
        import copy
        state = {
            "sim_time":       self._sim_time,
            "step_count":     self._step_count,
            "next_vid":       self._next_vid,
            "vehicles":       copy.deepcopy(self._vehicles),
            "current_phases": copy.deepcopy(self._current_phases),
            "phase_elapsed":  copy.deepcopy(self._phase_elapsed),
            "travel_times":   list(self._travel_times),
        }
        return _Archive(state)

    def load(self, archive: _Archive):
        import copy
        s = archive._state
        self._sim_time       = s["sim_time"]
        self._step_count     = s["step_count"]
        self._next_vid       = s["next_vid"]
        self._vehicles       = copy.deepcopy(s["vehicles"])
        self._current_phases = copy.deepcopy(s["current_phases"])
        self._phase_elapsed  = copy.deepcopy(s["phase_elapsed"])
        self._travel_times   = list(s["travel_times"])

    def load_from_file(self, path: str):
        with open(path) as f:
            state = json.load(f)
        self.load(_Archive(state))

    def set_random_seed(self, seed: int):
        random.seed(seed)

    def set_vehicle_route(self, vehicle_id: str, route: list) -> bool:
        if vehicle_id in self._vehicles:
            self._vehicles[vehicle_id]["route"] = " ".join(route)
            self._vehicles[vehicle_id]["_route_list"] = (
                [self._vehicles[vehicle_id]["road"]] + route
            )
            return True
        return False

    def set_replay_file(self, replay_file: str):
        if self._save_replay and hasattr(self, "_replay_file"):
            self._replay_file.close()
        new_path = os.path.join(self._replay_dir, replay_file)
        os.makedirs(os.path.dirname(new_path), exist_ok=True)
        self._replay_path = new_path
        self._replay_file = open(new_path, "w")

    def set_save_replay(self, open_replay: bool):
        self._save_replay = open_replay

    def __del__(self):
        if hasattr(self, "_replay_file") and not self._replay_file.closed:
            self._replay_file.close()
