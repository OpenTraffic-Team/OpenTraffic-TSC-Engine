from typing import Dict
import random 
import json 
from algorithms.utils.config import Config
import numpy as np
import copy
from sklearn.linear_model import Lasso


class FeatureExtract:
    def __init__(self, algo=None):
        self.lastTurnStartTime = None
        self.algo = algo
        self.sensors, self.recID_sensor_lut = self.parser_sensor_cnf(self.algo.config.SENSOR_CONF)
        self.paras_rec = "log/alg_paras.log"    
        
    def save_paras(self,paras,paras_name):
        parastr = paras_name+"="+ json.dumps(obj=paras, ensure_ascii=False,indent=4)+",\n"
        with open(self.paras_rec, 'a',encoding='utf-8') as file:            
            file.write(parastr)


    def parser_sensor_cnf(self,sensor_cnf):
        #解析归类路口所有传感器
        sensors = {} 
        recID_sensor_lut = {}
        def rec_id2lut(rec_id,sensor_id,sensor_fullid):
            if recID_sensor_lut.get(rec_id):
                recID_sensor_lut[rec_id][sensor_id] = sensor_fullid
            else:
                recID_sensor_lut[rec_id] = {sensor_id:sensor_fullid}

        intersection = sensor_cnf
        if(intersection.get("id") == self.algo.config.INTERSECTION):
            #遍历行车道路传感器
            for road in intersection["roads"]:
                radar_cnf = road.get("radars")
                if radar_cnf:
                    radar_fullid = road["id"]+"_RADAR_"+radar_cnf["id"]
                    radar_id = radar_cnf["id"]
                    recID = "recognitionSnap["+road["id"]+"]"
                    sensors[radar_fullid] = {
                        "type":"radar",
                        "area":road["id"],
                        "statusID":"tirStatus["+road["id"]+"]",
                        "recID":recID,
                        "capturedObj":"vehicles"
                    }
                    rec_id2lut(recID,radar_id,radar_fullid)
                cameras_cnf = road.get("cameras")
                if cameras_cnf:
                    for camera_cnf in cameras_cnf:                    
                        cam_id = camera_cnf["id"]
                        cam_fullid = road["id"]+"_CAM_"+camera_cnf["id"]
                        recID = "recognitionSnap["+road["id"]+"]"
                        sensors[cam_fullid] = {
                            "type":"camera",
                            "area":road["id"],
                            "statusID":"tirStatus["+road["id"]+"]",
                            "recID":recID,                       
                            "capturedObj":"vehicles"
                        }
                        rec_id2lut(recID,cam_id,cam_fullid)
            #遍历行人道路传感器
            for cw in intersection["crosswalks"]:
                cameras_cnf = cw.get("cameras")
                if cameras_cnf:
                    for camera_cnf in cameras_cnf: 
                        cam_id = camera_cnf["id"]
                        cam_fullid = cw["id"]+"_CAM_"+camera_cnf["id"]
                        recID = "recognitionSnap["+cw["id"]+"]"
                        sensors[cam_fullid] = {
                            "type":"camera",
                            "area":cw["id"],
                            "statusID":"tirStatus["+cw["id"]+"]",
                            "recID":"recognitionSnap["+cw["id"]+"]",
                            "capturedObj":"persons"
                        }
                        rec_id2lut(recID,cam_id,cam_fullid)
        else:
            self.log(2,"算法配置文件与硬件配置不匹配")
        return sensors,recID_sensor_lut

    def convert_cur_state(self, localLaneInfo):
        
        vehicle_map = self.__get_feature(localLaneInfo, self.algo.config.LANE_TO_PHASE)
        return vehicle_map
    
    def convert_cur_state_cf(self, interLocalInfo: dict,interVehicles:dict):
        
        vehicle_map = self.__get_feature_cityflow(interLocalInfo,interVehicles, self.algo.config.LANE_TO_PHASE)
        #vehicle_map["lane_queue_vehicle_in"], vehicle_map["num_in_deg"] = get_fuzzy_feature_cf(self)
        return vehicle_map
    
    def __get_feature_cityflow(self, interInfo,interVehicles, lane_to_phase):  #{lane:[v1,v2,v3]}
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
        for lane , vehicles in interInfo.items():
            lane2phase = lane_to_phase[lane]
            movements = lane2phase.split('_')
            for m in movements:
                if m in ["WS","SE","EN","NW"]:
                    continue
                for vehicle in vehicles:
                    vInfo = interVehicles[vehicle]
                    if vInfo['running']=='0':
                        vehicle_map["waiting_vehicle"][m]+=1
                    else:
                        if float(vInfo['speed'])<1.0:
                            vehicle_map["waiting_vehicle"][m]+=1
                        else:
                            vehicle_map['running_vehicle'][m]+=1
        return vehicle_map
   
    def __get_feature(self, LaneInfo, lane_to_phase):
        vehicle_map = {
            "running_vehicle": {
                "WE": 0, "EW": 0, "WN": 0, "ES": 0,
                "NS": 0, "SN": 0, "NE": 0, "SW": 0,
                "WW": 0, "EE": 0, "NN": 0, "SS": 0
            },
            "waiting_vehicle": {
                "WE": 0, "EW": 0, "WN": 0, "ES": 0,
                "NS": 0, "SN": 0, "NE": 0, "SW": 0,
                "WW": 0, "EE": 0, "NN": 0, "SS": 0
            },
            "running_person": {
              "S":0,  "W":0, "N":0, "E":0
            },
            "lane_queue_length":{},
            "num_in_deg":{},
            "vehicle_lane_to_phase": {
          
            }
        }
        for key in self.algo.config.LANE_TO_PHASE:
            vehicle_map['vehicle_lane_to_phase'][key] = []
        sensor_status = {}
        vrecs_min_ts = 0

        for rec_id in LaneInfo:
            if rec_id == "sensor_status":
                continue
            # 跳过元数据字段（视觉数据中的 code/name 等非感知记录）
            if not rec_id.startswith("recognitionSnap"):
                continue
            sensors_id = self.recID_sensor_lut.get(rec_id)
            if sensors_id is None:
                self.log(2, f"发现未定义的记录：{rec_id}")
                continue
            else:
                sensor_id = list(sensors_id.values())[0]
                statusID = self.sensors[sensor_id]["statusID"]
                # 视觉数据中没有 sensor_status 字段，默认传感器正常（状态=0）
                raw_status = LaneInfo.get("sensor_status")
                if raw_status is None or statusID not in raw_status:
                    sensor_status[sensor_id] = 0
                elif all(raw_status[statusID][id] == 0 for id in sensors_id):
                    sensor_status[sensor_id] = 0
                else:
                    sensor_status[sensor_id] = 1
                    self.log(2, f'出现传感器故障: {sensors_id}:{raw_status}')  

                    if self.sensors[sensor_id]["capturedObj"] == "persons":
                        #TBD：行人处理
                        # 根据行人个数分摊到对应的东西相位，直接乘上权重添加到对应车辆
                        person_E, person_S, person_N, person_W = 0,0,0,0
                        person_count =  len(LaneInfo[rec_id]['persons'])
                        if person_count > 1:
                            if rec_id[-4] == "E":
                                person_S += person_count  
                            elif rec_id[-4] == "S":
                                person_E += person_count  
                            elif rec_id[-4] == "W":
                                person_N += person_count  
                            else:
                                person_W += person_count

                            vehicle_map["running_person"]["E"] += person_E
                            vehicle_map["running_person"]["W"] += person_W
                            vehicle_map["running_person"]["S"] += person_S
                            vehicle_map["running_person"]["N"] += person_N

                    elif self.sensors[sensor_id]["capturedObj"] == "vehicles":
                        #TBD: localLaneInfo[rec_id]["timestamp"]
                        if vrecs_min_ts < LaneInfo[rec_id]["timestamp"]:
                            vrecs_min_ts = LaneInfo[rec_id]["timestamp"]
                        vehicle_map = self.__get_vehicle(vehicle_map, LaneInfo[rec_id], lane_to_phase)
                    else:
                        raise ValueError(f"未定义的对象类型: {self.sensors[sensor_id]}:{sensor_id}")
        if self.algo.config.ALGO_VERSION == "v3":
            self.__get_fuzzy_feature(vehicle_map)
        vehicle_map['timestamp'] = vrecs_min_ts   #什么
        vehicle_map['cameraState'] = sensor_status
        return vehicle_map
    
    def __get_vehicle(self, vehicle_map, state, lane_to_phase):
        
        for vehicle in state["vehicles"]:
            if vehicle["type"] == "vehicle":
                speed = vehicle["speed"]
                lane = vehicle["lane"]
                if lane in lane_to_phase:
                    
                    vehicle_map['vehicle_lane_to_phase'][lane].append(vehicle)
                    if lane.endswith('L') is True:
                        continue
                    phase_str = lane_to_phase[lane]
                    if "_" in phase_str:
                        phases = phase_str.split("_")
                        num_phase = phase_str.count("_") + 1
                        if num_phase == 3:
                            probabilities = [0.5, 0.3, 0.2]
                            phase_num = self.__generate_vehicle_prob(probabilities)
                            if phase_num == 3:
                                break
                            self.__insert_vehicle_map(speed, vehicle_map, phases[phase_num - 1])
                        #elif "XX" in phase_str:
                        elif phases[-1][0] == phases[-1][-1]:  # xx_EE  掉头以后定义均放在最后一个_后，掉头概率0.3
                            probabilities = [0.7, 0.3]
                            phase_num = self.__generate_vehicle_prob(probabilities)
                            if phase_num == 1:
                                break
                            self.__insert_vehicle_map(speed, vehicle_map, phases[phase_num - 1])
                        else:
                            # 定义左转和右转相位
                            left_turn_phases = {'NE', 'SW', 'WN', 'ES'}  # 左转相位
                            right_turn_phases = {'NW', 'SE', 'WS', 'EN'}  # 右转相位
                            straight_phases = {'NS', 'SN', 'WE', 'EW'}  # 直行相位
                            
                            # 判断是否是左转_右转的组合
                            if phases[0] in left_turn_phases and phases[-1] in right_turn_phases:
                                # 左转_右转，概率分配：左转0.7，右转0.3
                                probabilities = [0.7, 0.3]
                                phase_num = self.__generate_vehicle_prob(probabilities)
                                if phase_num == 1:          
                                    self.__insert_vehicle_map(speed, vehicle_map, phases[phase_num - 1])
                            else:
                                # 判断是否是直行_右转
                                right_map = {'E':'S','N':'E','W':'N','S':'W'}   #配置中要定义为  直行_右拐
                                if right_map[phases[0][-1]] == phases[-1][-1]:   #例如SN_SE  判断N与E对应可以判别为直行和右拐
                                    probabilities = [0.7, 0.3]
                                    phase_num = self.__generate_vehicle_prob(probabilities)
                                    if phase_num == 1:
                                        self.__insert_vehicle_map(speed, vehicle_map, phases[phase_num - 1])
                                else:
                                    # 默认按直行_左转处理
                                    probabilities = [0.7, 0.3]
                                    phase_num = self.__generate_vehicle_prob(probabilities)
                                    self.__insert_vehicle_map(speed, vehicle_map, phases[phase_num - 1])
                    else:
                        self.__insert_vehicle_map(speed, vehicle_map, phase_str)
            else:
                continue
        return vehicle_map
    

    def __insert_vehicle_map(self, speed, vehicle_map, phase_str):
        if abs(float(speed[0])) <= self.algo.config.MIN_RUNNING_SPEED:
            waiting_vehicle = vehicle_map["waiting_vehicle"][phase_str]
            vehicle_map["waiting_vehicle"][phase_str] = waiting_vehicle + 1
        else:
            running_vehicle = vehicle_map["running_vehicle"][phase_str]
            vehicle_map["running_vehicle"][phase_str] = running_vehicle + 1

    
    def convert_neighbor_state(self, neighbourLaneInfo: dict):
        vehicle_map = self.__get_feature(neighbourLaneInfo, self.algo.config.NEIGHBOUR_TO_PHASE)
        return vehicle_map

    def __generate_vehicle_prob(self, probabilities):
        random_num = random.choices(range(1, len(probabilities) + 1), probabilities)[0]
        return random_num
    
    #level 取值0-5
    def log(self,level, event):
        #self.logger(level,"Advanced_alg", event)
        pass

    def __get_fuzzy_feature(self, vehicle_map):
        """
        功能: 按观测步长将每条进口道划分为若干等长区段, 统计处于等待状态(速度<=0.1)的车辆数量,
             并将所有区段按车道长度四等分聚合, 最终返回四个部分的等待车数(按车道顺序排列),
             最后从车流数据中得到fuzzylight预测所需的两个特征。
        输出：lane_queue_vehicle_in:每个车道的等待车俩数
             num_in_deg:按长度将车道均分为4份，每一截中等待车辆数
        """
        obs_length = self.algo.config.OBS_LENGTH
        max_lane_length = self.algo.config.MAX_LANE_LENGTH
        is_noise = self.algo.config.IS_NOISE
        noise_type = self.algo.config.NOISE_TYPE
        noise_scale = self.algo.config.NOISE_SCALE
        sorted_entering_lanes = self.algo.config.SORT_ENTERING_LANES
        #这里取最大的车道长度/观测长度 为分段数
        inter_count = int(max_lane_length / obs_length )
        segments = [{} for i in range(inter_count)]
        #1. 将车辆分到每个路段块中
        for lane in self.algo.config.SORT_ENTERING_LANES:
            for k in range(inter_count):
                segments[k][lane] = []
            for vehicle in vehicle_map['vehicle_lane_to_phase'][lane]:
                temp_v_distance = vehicle['center'][0]
                for i in range(inter_count):
                    if i == 0:
                        if temp_v_distance < obs_length:
                            if abs(vehicle['speed'][0]) <= 0.1:
                                segments[i][lane].append(vehicle) 
                    else:
                        if i * obs_length < temp_v_distance <= (i+1) * obs_length:
                            if abs(vehicle['speed'][0]) <= 0.1:
                                segments[i][lane].append(vehicle)
                        elif temp_v_distance > max_lane_length:
                            print("车辆距离到停止线到距离大于车道长度")

        seg_in_part = np.zeros((inter_count, len(sorted_entering_lanes)))
        #下面保证了特征中车道的顺序，与后续预测代码的车道顺序保持一致
        for i in range(inter_count):
            seg_in_part[i] = np.array([len(segments[i][lane]) for lane in sorted_entering_lanes])
        original = copy.deepcopy(seg_in_part)
        #2.加入噪声后，压缩感知去噪
        if is_noise is False:
            if noise_type != -1:
                noise = noise_scale * np.random.randn(seg_in_part.shape[1])
                seg_in_part += noise
        else:
            noisy_matrix = np.zeros((20, 20))
            Phi = np.random.randn(20, original.shape[1])
            if noise_type != -1:
                for i in range(inter_count):
                    noise = noise_scale * np.random.randn(seg_in_part.shape[0])
                    noisy_matrix[i] = Phi @ seg_in_part[i] + noise
        if  is_noise:
            denoised_image = self.__compressive_sensing_denoise(noisy_matrix, Phi)
            denoised_image[denoised_image < 0] = 0
            mid = np.mean(denoised_image)
            denoised_image[denoised_image < mid] = 0
            denoised_image=np.round(denoised_image)
            seg_in_part = denoised_image

        #3.将区段沿车道长度方向四等分聚合, 得到四个部分的等待车辆数列表
        num_in_part1 = [0 for i in range(len(segments[0]))]     
        num_in_part2 = [0 for i in range(len(segments[0]))]        
        num_in_part3 = [0 for i in range(len(segments[0]))]        
        num_in_part4 = [0 for i in range(len(segments[0]))]                          
        for i in range(inter_count):
            if i <= int(inter_count/4.0-1):
                num_in_part1 = [x+y for x, y in zip(seg_in_part[i],num_in_part1)]
            elif  i > int(inter_count/4.0-1) and i <= int(inter_count/4.0):
                num_in_part2 = [x+y for x, y in zip(seg_in_part[i],num_in_part2)]
            elif i > int(inter_count/4.0) and i <= int(inter_count/4.0+1):     
                num_in_part3 = [x+y for x, y in zip(seg_in_part[i],num_in_part3)]
            else:
                num_in_part4 = [x+y for x, y in zip(seg_in_part[i],num_in_part4)]

        #4. 得到fuzzylight预测所需特征
        lane_queue_length = []
        num_in_deg = []
        for i in range(len(sorted_entering_lanes)):
            lane_queue_length.append(sum([num_in_part1[i], num_in_part2[i], num_in_part3[i], num_in_part4[i]]))
        for i in range(len(sorted_entering_lanes)):
            num_in_deg.extend([num_in_part1[i], num_in_part2[i], num_in_part3[i], num_in_part4[i]])
        
        vehicle_map['lane_queue_length'] = lane_queue_length
        vehicle_map['num_in_deg'] = num_in_deg

    
    def get_fuzzy_feature_cf(self, list_entering_lanes, lane_vehicles, vehicle_distance, vehicle_speed,
                              lane_length, list_lanes, noise_type=-1, noise_scale=1,
                              obs_length=8, is_nosie=False):
        """
        功能：从车流数据中得到fuzzylight预测所需的state，共有两个
        输出：lane_queue_vehicle_in:每个车道的等待车俩数
             num_in_deg:按长度将车道均分为4份，每一截中等待车辆数
        """
        dic_lane_vehicle_current_step = {}
        for lane in list_lanes:
            dic_lane_vehicle_current_step[lane] = lane_vehicles[lane]
        num_in_part1, num_in_part2, num_in_part3, num_in_part4 = self.__get_waiting_several_segments_cf(dic_lane_vehicle_current_step, vehicle_distance, vehicle_speed,
                                                                lane_length, list_entering_lanes, noise_type, noise_scale,
                                                                obs_length, is_nosie)
        lane_queue_vehicle_in = []
        num_in_deg = []
        for i in range(len(list_entering_lanes)):
            lane_queue_vehicle_in.append(sum([num_in_part1[i], num_in_part2[i], num_in_part3[i], num_in_part4[i]]))
        for i in range(len(list_entering_lanes)):
            num_in_deg.extend([num_in_part1[i], num_in_part2[i], num_in_part3[i], num_in_part4[i]])
        #if self.padding:
        #    num_in_deg = num_in_deg + self.padding1
        return lane_queue_vehicle_in, num_in_deg

    def __get_waiting_several_segments_cf(self, lane_vehicles, vehicle_distance, vehicle_speed,
                              lane_length, list_entering_lanes, noise_type=-1, noise_scale=1,
                              obs_length=8, is_nosie=False):
        """
        功能: 按观测步长将每条进口道划分为若干等长区段, 统计处于等待状态(速度<=0.1)的车辆数量,
        并将所有区段按车道长度四等分聚合, 最终返回四个部分的等待车数(按车道顺序排列)。

        处理流程:
        1) 以 `inter_count = max(lane_length) / obs_length` 计算区段数量, 对每条进口道构建同等数量的区段桶。
        2) 遍历车道内车辆, 依据 `vehicle_distance` 将车辆落入对应区段, 若 `vehicle_speed<=0.1` 计为等待车。
        3) 可选噪声: 当 `noise_type != -1` 时对区段计数加入高斯噪声(`noise_scale`控制幅度)。
           当 `is_nosie` 为 True 时, 先通过随机投影构造噪声观测, 再调用压缩感知重建进行去噪。
        4) 将区段沿车道长度方向四等分聚合, 得到四个部分的等待车辆数列表。

        参数:
        - lane_vehicles: dict[str, list[str]]  车道→车辆ID列表。
        - vehicle_distance: dict[str, float]   车辆到车道起点的距离(与 `lane_length`/`obs_length`同量纲)。
        - vehicle_speed: dict[str, float]      车辆瞬时速度。
        - lane_length: dict[str, float]        每条车道长度。
        - list_entering_lanes: list[str]       需要统计的进口道列表(顺序决定输出顺序)。
        - noise_type: int                      噪声类型标志, -1 表示不加噪声, 其他值时加入噪声。
        - noise_scale: float                   噪声幅度系数。
        - obs_length: int                      区段长度, 用于划分车道区段数。
        - is_nosie: bool                       是否启用压缩感知噪声与去噪流程。

        返回:
        - (num_in_part1, num_in_part2, num_in_part3, num_in_part4):
          四个列表, 每个列表长度等于 `list_entering_lanes` 的长度, 对应四等分部分内的等待车辆数(按车道顺序)。
        """
        
        # get four segments [100, 200, 300, 400] for segment
        inter_count = int(max(lane_length.values())/ obs_length)#这里取最大的车道长度/观测长度 为分段数
        segments = [{} for i in range(inter_count)]
        #part1, part2, part3, part4 = [], [], [], []
        for lane in list_entering_lanes:
            for k in range(inter_count):
                segments[k][lane] = []
            for vehicle in lane_vehicles[lane]:
                # set as num_vehicle
                if "shadow" in vehicle:  # remove the shadow
                    vehicle = vehicle[:-7]
                    continue
                temp_v_distance = vehicle_distance[vehicle]
                for i in range(inter_count):
                    if i == 0:
                        if temp_v_distance > lane_length[lane] - obs_length:
                            if vehicle_speed[vehicle] <= 0.1:
                                segments[i][lane].append(vehicle) 
                    else:
                        if lane_length[lane] - (1+i) * obs_length < temp_v_distance <= lane_length[lane] - i * obs_length:
                            if vehicle_speed[vehicle] <= 0.1:
                                segments[i][lane].append(vehicle)
                          
        seg_in_part = np.zeros((inter_count, len(list_entering_lanes)))
        for i in range(inter_count):
            seg_in_part[i] = np.array([len(segments[i][lane]) for lane in list_entering_lanes])
        original = copy.deepcopy(seg_in_part)
        
        if is_nosie is False:
            if noise_type != -1:
                noise = noise_scale * np.random.randn(seg_in_part.shape[1])
                seg_in_part += noise
        else:
            noisy_matrix = np.zeros((20, 20))
            Phi = np.random.randn(20, original.shape[1])
            if noise_type != -1:
                for i in range(inter_count):
                    noise = noise_scale * np.random.randn(seg_in_part.shape[0])
                    noisy_matrix[i] = Phi @ seg_in_part[i] + noise
    
        if  is_nosie:
            denoised_image = self.__compressive_sensing_denoise(noisy_matrix, Phi)
            denoised_image[denoised_image < 0] = 0
            mid = np.mean(denoised_image)
            denoised_image[denoised_image < mid] = 0
            denoised_image=np.round(denoised_image)
            seg_in_part = denoised_image
        num_in_part1 = [0 for i in range(len(segments[0]))]     
        num_in_part2 = [0 for i in range(len(segments[0]))]        
        num_in_part3 = [0 for i in range(len(segments[0]))]        
        num_in_part4 = [0 for i in range(len(segments[0]))]                          
        for i in range(inter_count):
            if i <= int(inter_count/4.0-1):
                num_in_part1 = [x+y for x, y in zip(seg_in_part[i],num_in_part1)]
            elif  i > int(inter_count/4.0-1) and i <= int(inter_count/4.0):
                num_in_part2 = [x+y for x, y in zip(seg_in_part[i],num_in_part2)]
            elif i > int(inter_count/4.0) and i <= int(inter_count/4.0+1):     
                num_in_part3 = [x+y for x, y in zip(seg_in_part[i],num_in_part3)]
            else:
                num_in_part4 = [x+y for x, y in zip(seg_in_part[i],num_in_part4)]
   
        return num_in_part1, num_in_part2, num_in_part3, num_in_part4

    def __compressive_sensing_denoise(self, noisy_matrix, Phi):
        #TBD: 压缩感知去噪
        alpha = 0.1  # 正则化参数
        lasso = Lasso(alpha=alpha, fit_intercept=False)
        xr = []
        for i in range(noisy_matrix.shape[0]):
            lasso.fit(Phi, noisy_matrix[i])
            x_recovered = lasso.coef_
            xr.append(x_recovered)
        xr = np.array(xr)
        return xr

    