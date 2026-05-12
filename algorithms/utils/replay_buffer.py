import numpy as np
import random
from collections import deque
import threading
import time
from itertools import islice

class ReplayBuffer:
    instance = None
    # 单例, 调用instance保证只存在一个ReplayBuffer
    def __new__(cls, capacity=None, batch_size=None, config=None):
        if not cls.instance:
            cls.instance = super(ReplayBuffer, cls).__new__(cls)  
            cls.instance.__init__(capacity, batch_size, config)
        return cls.instance  

    def __init__(self, capacity, batch_size, config):
        # 避免多次初始化
        if not hasattr(self, 'initialized'):
            self.capacity = capacity  # Buffer的最大容量 
            self.batch_size = batch_size  # 每次训练采样的批次大小
            self.buffer = deque(maxlen=capacity)  # 环形队列
            self.size = 0  # 当前存储的样本数量
            self.config = config
            self.median_speed = None  # 存储计算出的中位数
            self.import_lanes = [lane for lane in self.config.LANE_TO_PHASE if not lane.endswith('L')]
            self.lock = threading.Lock()  # 用于线程同步的锁
            self.initialized = True
            self._start_median_thread()  # 启动计算中位数的线程

    def _start_median_thread(self):
        """启动一个后台线程每秒计算一次中位数"""
        self._stop_thread = False  # 控制线程的停止标志
        def median_thread():
            while not self._stop_thread:
                time.sleep(1)  # 每秒计算一次
                self._update_median_speed()
        
        self.thread = threading.Thread(target=median_thread, daemon=True)
        self.thread.start()

    def _update_median_speed(self):
        """更新当前的中位数"""
        # 先获取buffer的快照，减少锁的持有时间
        with self.lock:
            if len(self.buffer) <= self.config.MEDIAN_TIME:
                return
            # 使用 islice ，避免复制整个列表
            buffer_size = len(self.buffer)
            start_idx = max(0, buffer_size - self.config.MEDIAN_TIME)
            recent_items = list(islice(self.buffer, start_idx, buffer_size))
        # 在锁外处理数据，提高性能
        speed_queue = []    
        # 预计算车道列表，避免重复计算
        
        
        for item in recent_items:
            # 统计所有进口车道上的车辆
            for lane in self.import_lanes:
                try:
                    vehicles = item[0][self.config.INTERSECTION]['vehicle_lane_to_phase'][lane]
                    for vehicle in vehicles:
                        if abs(vehicle['speed'][0]) > 0:
                            speed_queue.append(abs(vehicle['speed'][0]))
                except (KeyError, IndexError, TypeError):
                    # 处理数据异常，避免程序崩溃
                    continue

            if speed_queue:
                median = np.median(speed_queue)
                with self.lock:
                    self.median_speed = median
            else:
                with self.lock:
                    self.median_speed = self.config.HIGH_LEVEL_ADVANCED_WEIGHT_MINSPEED[1]

        # with self.lock:  # 确保线程安全
        #     if len(self.buffer) > self.config.MEDIAN_TIME:
        #         speed_queue = []
        #         for item in list(self.buffer)[-self.config.MEDIAN_TIME:]:
        #             # 统计所有进口车道上的车辆
        #             for lane in (lane for lane in self.config.LANE_TO_PHASE if not lane.endswith('L')):
        #                 vehicles = item[0][self.config.INTERSECTION]['vehicle_lane_to_phase'][lane]
        #                 for vehicle in vehicles:
        #                     if abs(vehicle['speed'][0]) > 0:
        #                         speed_queue.append(abs(vehicle['speed'][0]))
        #         # 求中位数
        #         if speed_queue:
        #             self.median_speed = np.median(speed_queue)
        #         else:
        #             self.median_speed = self.config.HIGH_LEVEL_ADVANCED_WEIGHT_MINSPEED[1]

    def store(self, state, env_state, action, action_type):
        """存储每秒的值, action_type 0表示算法model生成的action, 1表示溢出生成的action, 2表示saferules其他方法生成的action, training只选择 action_type为0的"""
        
        with self.lock:  # 确保线程安全
            self.buffer.append((state, action, env_state, action_type))
            if self.size < self.capacity:
                self.size += 1        
            if self.size > 2:
                # reward可以根据配置来变化, 可以是max waiting queue
                reward = self.buffer[self.size - 1][0][self.config.INTERSECTION]['waiting_vehicle']
                next_state = self.buffer[self.size - 1][0]
                self.buffer[self.size - 2] += (reward, next_state)
        # self.buffer.append((state, action, env_state, action_type))
        # if self.size < self.capacity:
        #     self.size += 1        
        # if self.size > 2:
        #     # reward可以根据配置来变化, 可以是max waiting queue
        #     reward = self.buffer[self.size - 1][0][self.config.INTERSECTION]['waiting_vehicle']
        #     next_state = self.buffer[self.size - 1][0]
        #     self.buffer[self.size - 2] += (reward, next_state)

    def sample(self):
        """从Replay Buffer中随机采样一批数据, 且action_type为0"""
        filtered_buffer = [item for item in self.buffer[:-1] if item[2] == 0] 
        batch = random.sample(filtered_buffer, self.batch_size)
        states, actions, _, rewards, next_states = zip(*batch)
        return np.array(states), np.array(actions), np.array(rewards), np.array(next_states)

    def __len__(self):
        """返回Buffer的大小"""
        return self.size

    def clear(self):
        """清空Replay Buffer"""
        self.buffer.clear()
        self.size = 0

    def get_min_speed(self):
        """获取当前计算出的中位数速度"""
        with self.lock:  # 确保线程安全
            if self.median_speed is not None:
                return self.median_speed
            else:
                # 如果中位数还没有计算出来，则返回默认值
                return self.config.HIGH_LEVEL_ADVANCED_WEIGHT_MINSPEED[1]

    def stop_median_thread(self):
        self._stop_thread = True
        self.thread.join()  
