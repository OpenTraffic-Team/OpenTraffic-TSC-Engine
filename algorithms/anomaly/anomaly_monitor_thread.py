# import threading
# import time
# import datetime
# from algorithms.enums.anomaly_status_enum import AnomalyStatus
# from algorithms.anomaly.anomaly_detector_phase import ActionResultChecker

# class AnomalyMonitorThread(threading.Thread):
#     def __init__(self, redis_client, config, logger, interval=2):
#         super().__init__()
#         self.redis = redis_client
#         self.config = config
#         self.logger = logger
#         self.interval = interval
#         self.checker = ActionResultChecker(config, logger)
#         self.running = True

#     def stop(self):
#         self.running = False

#     def run(self):
#         while self.running:
#             try:
#                 origin_state = self.redis.get_json(f"{self.config.INTERSECTION}_origin_state")
#                 env_state = self.redis.get_json(f"{self.config.INTERSECTION}_env_state")
#                 action = self.redis.get_json(f"{self.config.INTERSECTION}_action")

#                 # 检测Redis数据
#                 ok, status, msg = self.checker.analyze_redis_data(origin_state, env_state)
#                 self.checker.report_if_abnormal(ok, status, msg)

#                 # 检测车流
#                 vehicle_map = self.checker.extract_vehicle_map(origin_state)
#                 ok, status, msg = self.checker.anomaly_surge_and_plunge_vehicle(vehicle_map)
#                 self.checker.report_if_abnormal(ok, status, msg)

#                 # 检测take_action输出
#                 if action:
#                     phase = action.get("phase")
#                     ok, status, msg = self.checker.analyze_take_action_result(phase)
#                     self.checker.report_if_abnormal(ok, status, msg)

#             except Exception as e:
#                 self.logger(2, "AnomalyMonitorThread", f"[异常线程崩溃] {str(e)}")
#             time.sleep(self.interval)
