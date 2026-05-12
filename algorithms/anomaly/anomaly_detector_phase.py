# from algorithms.enums.anomaly_status_enum import AnomalyStatus
# from datetime import datetime
# from algorithms.utils.replay_buffer import ReplayBuffer
# class ActionResultChecker:
#     def __init__(self, config, logger):
#         self.config = config
#         self.logger = logger
#         self.last_phase = None
#         self.repeated_count = 0
#         self.last_vehicle_count = None  # 用于激增骤减判断

#     def is_valid_phase(self, phase):
#         if phase is None:
#             return False
#         if phase not in self.config.PHASES_LIST:
#             self.logger(1, "TakeActionResultChecker", f"非法相位输出：{phase}")
#             return False
#         return True

#     def check_repeated_phase(self, phase):
#         if phase == self.last_phase:
#             self.repeated_count += 1
#             if self.repeated_count >= self.repeated_threshold:
#                 self.logger(1, "TakeActionResultChecker", f"[异常] 相位 {phase} 连续重复 {self.repeated_count} 次")
#                 return False
#         else:
#             self.repeated_count = 1
#             self.last_phase = phase
#         return True
#     def anomaly_surge_and_plunge_vehicle(self, cur_running_vehicle_roads_after):
#         # 获取replay_buffer实例
#         replay_buffer = getattr(self.algorithm, "replay_buffer", None)
#         if replay_buffer is None:
#             replay_buffer = ReplayBuffer(self.config.REPLAYBUFFER_CAPACITY, self.config.BATCH_SIZE, self.config)

#         window_size = 300  # 5分钟窗口，1秒采样
#         surge_coef = 1.3
#         plunge_coef = 0.7
#         surge_buffer = 2

#         # 统计窗口内每条road的车辆数历史
#         road_histories = {road: [] for road in cur_running_vehicle_roads_after.keys()}
#         with replay_buffer.lock:
#             buffer_list = list(replay_buffer.buffer)[-window_size:]
#             for item in buffer_list:
#                 state = item[0]
#                 if self.config.INTERSECTION not in state:
#                     continue
#                 lane_map = state[self.config.INTERSECTION]['vehicle_lane_to_phase']
#                 # 累加每个road的车辆数
#                 for lane, vehicles in lane_map.items():
#                     road = self.algorithm.cur_inter_id + "_" + lane[0]
#                     if road in road_histories:
#                         road_histories[road].append(len(vehicles))

#         # 检测激增/骤减
#         for road, vehicle_num in cur_running_vehicle_roads_after.items():
#             history = road_histories.get(road, [])
#             if len(history) < window_size:
#                 continue  # 历史不足
#             ma = sum(history) / len(history)
#             dynamic_high = ma * surge_coef + surge_buffer
#             dynamic_low = ma * plunge_coef - surge_buffer

#             if vehicle_num > dynamic_high:
#                 print(f"{AnomalyStatus.SURGE_VEH_ERROR} {road} surge: current={vehicle_num}, threshold={dynamic_high:.2f}, MA={ma:.2f}")
#                 self.alg_running_status = AnomalyStatus.SURGE_VEH_ERROR
#                 self.pre_status_timestamp = time.time()
#                 return AnomalyStatus.SURGE_VEH_ERROR, road
#             if vehicle_num < dynamic_low:
#                 print(f"{AnomalyStatus.OTHER_ERROR} {road} drop: current={vehicle_num}, lower bound={dynamic_low:.2f}, MA={ma:.2f}")
#                 self.alg_running_status = AnomalyStatus.OTHER_ERROR
#                 self.pre_status_timestamp = time.time()
#                 return AnomalyStatus.PLUNGE_VEH_ERROR, road
#         self.cur_running_vehicle_roads_before = cur_running_vehicle_roads_after
#         return AnomalyStatus.NORMAL, None
#     def check(self, phase):
#         if not self.is_valid_phase(phase):
#             return False
#         if not self.check_repeated_phase(phase):
#             return False
#         return True
    
#     def analyze_redis_data(self, origin_state, env_state):
#         if origin_state is None or env_state is None:
#             return False, AnomalyStatus.OTHER_ERROR, "Redis 数据为空或超时"
#         if "phases" not in env_state or "currentPhase" not in env_state:
#             return False, AnomalyStatus.OTHER_ERROR, "Redis 数据结构异常"
#         return True, AnomalyStatus.NORMAL, "Redis 数据正常"

#     def analyze_take_action_result(self, phase):
#         if phase is None:
#             return False, AnomalyStatus.ALGO_EXCEPTION, "算法输出为 None"
#         if phase not in self.config.PHASES_LIST:
#             return False, AnomalyStatus.ALGO_ERROR, f"非法相位输出：{phase}"
#         return True, AnomalyStatus.NORMAL, "相位输出正常"

#     def report_if_abnormal(self, is_ok, status_enum, msg):
#         if is_ok or status_enum == AnomalyStatus.NORMAL:
#             return
#         self.logger(1, "FullAnomalyChecker", f"[{status_enum.name}] {msg}")