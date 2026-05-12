"""
Algorithm SDK - 数据格式转换工具
提供不同数据格式之间的转换功能
"""


class StateConverter:
    """
    状态数据格式转换器

    支持的数据格式：
    - 传感器格式 (recognitionSnap)
    - CityFlow格式 ({lane: [vehicle_ids]})
    - 算法内部格式
    """

    @staticmethod
    def sensor_to_cityflow(sensor_state: dict) -> dict:
        """
        将传感器格式转换为CityFlow格式

        Args:
            sensor_state: 传感器格式状态
                {
                    "路口ID": {
                        "recognitionSnap[xxx]": {
                            "timestamp": xxx,
                            "vehicles": [{"id": "v1", "lane": "xxx", ...}]
                        }
                    }
                }

        Returns:
            CityFlow格式
                {
                    "路口ID": {
                        "lane1": [{"id": "v1", ...}],
                        "lane2": []
                    }
                }
        """
        result = {}

        for intersection_id, data in sensor_state.items():
            lanes = {}

            # 遍历所有recognitionSnap
            for key, value in data.items():
                if key.startswith("recognitionSnap"):
                    vehicles = value.get("vehicles", [])
                    for vehicle in vehicles:
                        lane = vehicle.get("lane")
                        if lane:
                            if lane not in lanes:
                                lanes[lane] = []
                            lanes[lane].append(vehicle)

            result[intersection_id] = lanes

        return result

    @staticmethod
    def cityflow_to_sensor(cityflow_state: dict) -> dict:
        """
        将CityFlow格式转换为传感器格式

        Args:
            cityflow_state: CityFlow格式状态

        Returns:
            传感器格式
        """
        result = {}

        for intersection_id, lanes in cityflow_state.items():
            data = {
                "cameraState": {},
                "sensor_status": {}
            }

            # 为每个车道创建recognitionSnap
            rec_index = 0
            for lane, vehicles in lanes.items():
                rec_id = f"road_{rec_index}"
                data[f"recognitionSnap[{rec_id}]"] = {
                    "timestamp": 0,
                    "vehicles": vehicles
                }
                data[f"tirStatus[{rec_id}]"] = {}
                rec_index += 1

            result[intersection_id] = data

        return result

    @staticmethod
    def cityflow_to_algorithm(cityflow_state: dict, vehicles: dict) -> dict:
        """
        将CityFlow格式转换为算法内部格式

        Args:
            cityflow_state: CityFlow格式 (lane -> [vehicle_ids])
            vehicles: 车辆详情 (vehicle_id -> {speed, running, ...})

        Returns:
            算法内部格式 {lane -> {running: count, waiting: count}}
        """
        result = {
            "running_vehicle": {},
            "waiting_vehicle": {}
        }

        for lane, vehicle_ids in cityflow_state.items():
            running_count = 0
            waiting_count = 0

            for vid in vehicle_ids:
                v_info = vehicles.get(vid, {})
                running = v_info.get("running", "0")
                speed = v_info.get("speed", 0)

                if running == "0" or float(speed) < 1.0:
                    waiting_count += 1
                else:
                    running_count += 1

            # 从lane名称推断movement
            movement = lane.split("_")[-1] if "_" in lane else lane

            result["running_vehicle"][movement] = result["running_vehicle"].get(movement, 0) + running_count
            result["waiting_vehicle"][movement] = result["waiting_vehicle"].get(movement, 0) + waiting_count

        return result


class VehicleConverter:
    """车辆数据格式转换"""

    @staticmethod
    def cityflow_vehicles_to_map(vehicles: list) -> dict:
        """
        将CityFlow车辆列表转换为字典

        Args:
            vehicles: CityFlow车辆列表
                [{"id": "v1", "speed": 5.0, "lane": "lane1"}, ...]

        Returns:
            车辆字典 {vehicle_id: vehicle_info}
        """
        return {v["id"]: v for v in vehicles}

    @staticmethod
    def map_to_cityflow_vehicles(vehicle_map: dict) -> list:
        """
        将车辆字典转换为CityFlow列表格式

        Args:
            vehicle_map: {vehicle_id: vehicle_info}

        Returns:
            车辆列表
        """
        return [
            {**info, "id": vid}
            for vid, info in vehicle_map.items()
        ]


class EnvStateConverter:
    """环境状态格式转换"""

    @staticmethod
    def normalize_env_state(env_state: dict) -> dict:
        """
        规范化环境状态格式

        确保所有必需字段存在且格式正确
        """
        normalized = {
            "phases": env_state.get("phases", []),
            "currentPhase": env_state.get("currentPhase", env_state.get("current_phase", 0)),
            "phaseTime": env_state.get("phaseTime", env_state.get("phase_time", 0)),
            "currentPlan": env_state.get("currentPlan", env_state.get("current_plan", "")),
        }

        # 如果有timestamp也保留
        if "timestamp" in env_state:
            normalized["timestamp"] = env_state["timestamp"]

        return normalized

    @staticmethod
    def extract_phase_info(env_state: dict) -> dict:
        """
        提取相位相关信息

        Returns:
            {
                "current_phase": int,
                "phase_time": float,
                "phase_index": int
            }
        """
        current = env_state.get("currentPhase", 0)
        phases = env_state.get("phases", [])

        phase_index = 0
        if phases and current in phases:
            phase_index = phases.index(current)

        return {
            "current_phase": current,
            "phase_time": env_state.get("phaseTime", 0),
            "phase_index": phase_index,
            "phase_name": env_state.get("currentPlan", "")
        }


__all__ = [
    "StateConverter",
    "VehicleConverter",
    "EnvStateConverter"
]
