import copy
import json
import threading
import time
import queue
from enum import Enum

class AnomalyStatus(Enum):
    NORMAL = 0
    # error的 staus值统一用 5开头 ，4位数字；normal用2开头吧
    NO_DECREASE_VEH_ERROR = 5
    SURGE_VEH_ERROR = 10
    OTHER_ERROR = 3602

class AnomalyDetector:
    def __init__(self, algorithm):
        self.algorithm = algorithm
        self.config = algorithm.config
        print(self.config)
        self.interval = self.config["no_decrease_interval"]
        self.no_decrease_Threshold = self.config["no_decrease_threshold"]
        self.interval_surge = self.config["surge_interval"]
        self.surge_Threshold = self.config["surge_vehicle_threshold"]
        self.stop_event = threading.Event()
        self.result_queue = queue.Queue()
        self.time_stamp  = 0
        self.alg_running_status = AnomalyStatus.NORMAL
        self.pre_status_timestamp = time.time()
  
        self.cur_waiting_vehicle_roads_before,self.cur_running_vehicle_roads_before, self.algorithm_phase_before, _, _ = self.algorithm.get_cur_input_and_output()
        print("anomalyDetector has been initied")
        
    def is_normal(self,env_state):
        if self.alg_running_status == AnomalyStatus.NORMAL:
            return True
        elif env_state['timestamp'] - self.pre_status_timestamp >= self.alg_running_status.value:
            self.alg_running_status = AnomalyStatus.NORMAL
            print("change to normal")
            self.time_stamp=0
            return True
        else:
            print("waiting to normal time:"+str(time.time() - self.pre_status_timestamp)+"**** the target is"+str(self.alg_running_status.value))
            return False
        

    def monitor_traffic(self):
        anomaly_flag = 0
        while not self.stop_event.is_set():
            try:
                if self.alg_running_status != AnomalyStatus.NORMAL:
                    self.time_stamp = 0
                    print("waiting for the TSC anomaly")
                    time.sleep(1)
                    continue             
                                   
                if self.time_stamp == 0 or self.cur_waiting_vehicle_roads_before == None or self.cur_running_vehicle_roads_before == None:
                    self.cur_waiting_vehicle_roads_before,self.cur_running_vehicle_roads_before, self.algorithm_phase_before, _, _ = self.algorithm.get_cur_input_and_output()

                # 
                #异常轮询检测
                time.sleep(1)
                self.time_stamp = (self.time_stamp+1 ) % (self.interval * self.interval_surge)
                print("anomly:"+str(self.time_stamp))

                #异常判断
                if self.time_stamp!=0 and self.time_stamp % self.interval==0 and self.cur_waiting_vehicle_roads_before != None:
                    print("Detecting:anomly_waiting:"+str(self.time_stamp))
                    
                    cur_waiting_vehicle_roads_after,_, algorithm_phase_after, _, _ = self.algorithm.get_cur_input_and_output()

                    if cur_waiting_vehicle_roads_after == None or algorithm_phase_after == None:
                        continue
                    error_road = self.anomaly_no_decrease_vehicle(algorithm_phase_after,cur_waiting_vehicle_roads_after)
                    if error_road == AnomalyStatus.NORMAL:
                        continue
                    else:
                        anomaly_flag = 1
                        current_time = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime())
                        self.algorithm.logger(0,f"Advanced_alg: anomaly detection NO.{anomaly_flag} occurred on {current_time}, error_road is {error_road} No decrease vehicles under continuous phase")
                        # 这里加上异常log
                        raise Exception                 
                if self.time_stamp!=0 and self.time_stamp%self.interval_surge==0 and self.cur_running_vehicle_roads_before != None:
                    print("Detecting:anomly_surge:"+str(self.time_stamp))
                    _,cur_running_vehicle_roads_after,_,_,_ = self.algorithm.get_cur_input_and_output()

                    if cur_running_vehicle_roads_after == None:
                        continue       
                    error_road = self.anomaly_surge_vehicle(cur_running_vehicle_roads_after)           
                    if error_road == AnomalyStatus.NORMAL:
                        continue
                    else:
                        anomaly_flag = 2
                        current_time = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime())
                        self.algorithm.logger(0,f"Advanced_alg: anomaly detection NO.{anomaly_flag} occurred on {current_time}, error_road is {error_road} Sudden increase vehicle within {self.interval_surge} seconds ")
                        # 这里加上异常log
                        raise Exception
            except Exception as e:
                print("error"+str(anomaly_flag))
                if anomaly_flag == 1:
                    self.result_queue.put(AnomalyStatus.NO_DECREASE_VEH_ERROR)
                if anomaly_flag == 2:
                    self.result_queue.put(AnomalyStatus.SURGE_VEH_ERROR)
    

    def _get_road_vehicle_map(self,cur_lane_vehicle_before,cur_lane_vehicle_after):   #东南西北方向的road上有多少量running or waiting的车
        road_vehicle_map_before = {}
        for direction in self.algorithm.directions:
            road_vehicle_map_before[self.algorithm.cur_inter_id+"_"+direction] = 0
        road_vehicle_map_after = copy.deepcopy(road_vehicle_map_before)
        for lane, vehicle_num in cur_lane_vehicle_before.items():
            road_vehicle_map_before[self.algorithm.cur_inter_id+"_"+lane[0]] += vehicle_num
        for lane, vehicle_num in cur_lane_vehicle_after.items():
            road_vehicle_map_after[self.algorithm.cur_inter_id+"_"+lane[0]] += vehicle_num
        return road_vehicle_map_before,road_vehicle_map_after
    
    def anomaly_no_decrease_vehicle(self,algorithm_phase_after,cur_waiting_vehicle_roads_after):

        if (self.algorithm_phase_before == algorithm_phase_after):

            road_waiting_vehicle_map_before,road_waiting_vehicle_map_after = self._get_road_vehicle_map(self.cur_waiting_vehicle_roads_before,cur_waiting_vehicle_roads_after)

            for road,vehicle_num in road_waiting_vehicle_map_after.items():
               
                if vehicle_num - road_waiting_vehicle_map_before[road] > self.no_decrease_Threshold:
                    print(AnomalyStatus.NO_DECREASE_VEH_ERROR)
                    self.alg_running_status = AnomalyStatus.NO_DECREASE_VEH_ERROR
                    self.pre_status_timestamp = time.time()
                    # return AnomalyStatus.NO_DECREASE_VEH_ERROR
                    return road
        self.cur_waiting_vehicle_roads_before = cur_waiting_vehicle_roads_after    
        return AnomalyStatus.NORMAL
    
    def anomaly_surge_vehicle(self,cur_running_vehicle_roads_after):
        road_running_vehicle_map_before,road_running_vehicle_map_after = self._get_road_vehicle_map(self.cur_running_vehicle_roads_before,cur_running_vehicle_roads_after)
        for road,vehicle_num in road_running_vehicle_map_after.items():
            if vehicle_num - road_running_vehicle_map_before[road] > self.surge_Threshold:
                print(AnomalyStatus.SURGE_VEH_ERROR)
                self.alg_running_status = AnomalyStatus.SURGE_VEH_ERROR
                self.pre_status_timestamp = time.time()
                # return AnomalyStatus.SURGE_VEH_ERROR
                return road
        self.cur_running_vehicle_roads_before = cur_running_vehicle_roads_after
        return AnomalyStatus.NORMAL
            
    def get_result(self):
        try:
            # 从队列中获取结果，设置非阻塞以避免阻塞主线程
            result = self.result_queue.get_nowait()
            return result
        except queue.Empty:
            return None
    
    def start_monitoring(self):
        # 创建并启动监测线程
        monitor_thread = threading.Thread(target=self.monitor_traffic)
        #将子线程设置为守护线程，主线程结束时，子线程自动结束
        monitor_thread.setDaemon(True)  
        monitor_thread.start()
        self.algorithm.logger(5,"Advanced_alg",f"INFO: Start Monitoring") 

    def stop_monitoring(self):
        # 设置停止事件，结束监测线程
        self.stop_event.set()
        self.algorithm.logger(5,"Advanced_alg",f"INFO: Stop Monitoring") 
