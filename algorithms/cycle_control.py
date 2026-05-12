
from algorithms.models.advanced_v1_agent import AdvancedMaxPressure
from algorithms.saferules.pre_safe_manager import PreSafeRules
import setup_path
from typing import Dict
import random 
import json 
import time


class CycleControl:
    def __init__(self, config_path):
        with open(config_path) as f:
            config = json.load(f)
            self.lane_to_phase = config['lane_to_phase']
            self.neighbour_to_phase = config['neighbour_to_phase']
            self.is_four = config['is_four']
            self.cur_inter_id = config['cur_inter_id']
            self.changeTime = config["changeTime"]
            self.maxKeepTime = config["maxKeepTime"]
            self.delay_time = config['delayTime']
            self.lastTurnStartTime = None
            if self.config.ALGO_VERSION == 'v1':
                self.algo = AdvancedMaxPressure(self.config)
            else:
                self.algo = None

        self.safe_rules = PreSafeRules(self.algo)

    
    def take_action(self, state: Dict[str, Dict[str, int]], env_state) -> int:
        if(self.lastTurnStartTime is None):
            self.lastTurnStartTime = env_state['timestamp']
            return 1
        elif(env_state['timestamp']-self.lastTurnStartTime<30):
            return 1
        elif(env_state['timestamp']-self.lastTurnStartTime<73):
            return 2
        else:
            self.lastTurnStartTime = env_state['timestamp']
            return 2
        
        check_result = self.safe_rules.excute_rules_chain(state, env_state)
        if check_result is RuleStatus.ERROR:
            return None
        elif check_result is RuleStatus.CHECK_PASSED:
           
            pass
        else: 
           
            return check_result
        
        # 判断是否达到changeTime
        action = env_state["currentPhase"]
        phase_four = ["WE_EW", "WN_ES", "NS_SN", "NE_SW"]
        phase_eight = ["WE_EW", "WN_ES", "NS_SN", "NE_SW", "WE_WN", "NS_NE", "SN_SW", "EW_ES"]
        phase_p = []
        phase_d = []
        action = env_state["currentPhase"]
        state = state[self.cur_inter_id]
        running_vehicle_roads = state["running_vehicle"]
        waiting_vehicle_roads = state["waiting_vehicle"]
        for i in range(4):
            phase_str = phase_four[i]
            d = running_vehicle_roads[phase_str[0:2]] + running_vehicle_roads[phase_str[3:5]]
            p = waiting_vehicle_roads[phase_str[0:2]] + waiting_vehicle_roads[phase_str[3:5]]
            phase_p.append(d)
            phase_d.append(p)
        # 周期性选择相位
        if self.is_four:
            action = (action) % 4 + 1
        else:
            action = (action) % 8 + 1
        self.safe_rules.action_history.append(action)
        # 生成1-4之间的整数并返回
        return action
    

    def convert_cur_state(self, state: dict):
        
        #j = json.loads(state)
        #print("cur_state:{}".format(state))
        vehicle_map = self.get_vehicle(state, self.lane_to_phase)
        vehicle_map['timestamp'] = state['timestamp']
        vehicle_map['cameraState'] = state['cameraState']
        return vehicle_map
    

    def convert_neighbor_state(self, state: dict):
        # 一个道路有多个方向，使用_分割，XX表示掉头，概率随个数取平均？还是说直行概率大于两者
        # 解析JSON数据
        # Create a sample state
        #j = json.loads(state)
        #print("to neighbor state:{}".format(state))
        vehicle_map = self.get_vehicle(state, self.lane_to_phase)
        vehicle_map['timestamp'] = state['timestamp']
        vehicle_map['cameraState'] = state['cameraState']
        return vehicle_map


    def get_vehicle(self, j, lane_to_phase):
        vehicle_map = {
            "running_vehicle": {
                "WE": 0, "EW": 0, "WN": 0, "ES": 0,
                "NS": 0, "SN": 0, "NE": 0, "SW": 0
            },
            "waiting_vehicle": {
                "WE": 0, "EW": 0, "WN": 0, "ES": 0,
                "NS": 0, "SN": 0, "NE": 0, "SW": 0
            }
        }
        for vehicle in j["vehicles"]:
            speed = vehicle["speed"]
            lane = vehicle["lane"]
            if lane in lane_to_phase:
                phase_str = lane_to_phase[lane]
                if "_" in phase_str:
                    phases = phase_str.split("_")
                    num_phase = phase_str.count("_") + 1
                    if num_phase == 3:
                        probabilities = [0.5, 0.3, 0.2]
                        phase_num = self.generate_vehicle_prob(probabilities)
                        if phase_num == 3:
                            break
                        self.insert_vehicle_map(speed, vehicle_map, phases[phase_num - 1])
                    elif "XX" in phase_str:
                        probabilities = [0.7, 0.3]
                        phase_num = self.generate_vehicle_prob(probabilities)
                        if phase_num == 2:
                            break
                        self.insert_vehicle_map(speed, vehicle_map, phases[phase_num - 1])
                    else:
                        probabilities = [0.7, 0.3]
                        phase_num = self.generate_vehicle_prob(probabilities)
                        self.insert_vehicle_map(speed, vehicle_map, phases[phase_num - 1])
                else:
                    self.insert_vehicle_map(speed, vehicle_map, phase_str)
        return vehicle_map
    

    def insert_vehicle_map(self, speed, vehicle_map, phase_str):
        if abs(float(speed[0])) <= 0.1:
            waiting_vehicle = vehicle_map["waiting_vehicle"][phase_str]
            vehicle_map["waiting_vehicle"][phase_str] = waiting_vehicle + 1
        else:
            running_vehicle = vehicle_map["running_vehicle"][phase_str]
            vehicle_map["running_vehicle"][phase_str] = running_vehicle + 1


    def generate_vehicle_prob(self, probabilities):
        random_num = random.choices(range(1, len(probabilities) + 1), probabilities)[0]
        return random_num

    
