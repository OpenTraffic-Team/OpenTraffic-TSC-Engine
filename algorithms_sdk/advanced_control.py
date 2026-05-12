from algorithms.models.advanced_v1_agent import AdvancedV1
from algorithms.saferules.pre_safe_manager import PreSafeRules
from algorithms.saferules.post_safe_manager import PostSafeRules
from algorithms.anomaly.anomaly_detection import AnomalyDetector
from algorithms.saferules.rules.rule_result import RuleResult
from typing import Dict
from algorithms.utils.config import Config
import json
import asyncio
import traceback
import copy
from algorithms.enums.algorithm_status_enum import *
from algorithms.enums.signal_status_enum import SignalControllerStatus 
from algorithms.utils.replay_buffer import ReplayBuffer
from algorithms.utils.util import *
from algorithms_sdk.mq_utils.mq_config import MQConfig
from algorithms_sdk.mq_utils.redis.redis_stream import RedisStreamReader
#from algorithms.anomaly.anomaly_monitor_thread import AnomalyMonitorThread
import socket
import time as t
import datetime
import logging
import tracemalloc
import psutil
import os
from algorithms.license_check import verify_license          

class AdvancedControl:
    def __init__(self, mq_path=None, logger=print, sensor_cnf={}, config_path=None, test=False):
        # 检查许可证过期时间
        
        verify_license()
        if test:
            # 本地测试：只初始化算法，不连接中间件
            self.config = Config(config_path=config_path, sensor_cnf=sensor_cnf, test=True)
            self.config.LOGGER = logger
        else:
            # 初始化内存监控

            MQ_config = MQConfig(mq_path)
            self.mq_config = MQ_config
            self.local_ip = self.get_local_ip()
            print(f'redis addr:{MQ_config.REDIS_ADDR},local ip:{self.local_ip}')
            print("----------------------")
            self.redis_stream = RedisStreamReader(MQ_config.REDIS_ADDR, MQ_config.REDIS_PORT, MQ_config.REDIS_PASSWORD)
            self.config = Config(redis=self.redis_stream, mq_config=MQ_config)
            self.config.LOGGER = logger
        if self.config.ALGO_VERSION == 'v1':
            self.algo = AdvancedV1(self.config)
        elif self.config.ALGO_VERSION == 'v2_1':
            from algorithms.models.advanced_v2_1_agent import AdvancedV2_1
            self.algo = AdvancedV2_1(self.config)
        elif self.config.ALGO_VERSION == 'v2_2':
            from algorithms.models.advanced_v2_2_agent import AdvancedV2_2
            self.algo = AdvancedV2_2(self.config)
        elif self.config.ALGO_VERSION == 'v2_3':
            from algorithms.models.advanced_v2_3_agent import AdvancedV2_3
            self.algo = AdvancedV2_3(self.config)
        self.pre_safe_rules = PreSafeRules(self.algo)
        self.post_safe_rules = PostSafeRules(self.algo)
        self.call_count = 0
        self.memory_history = []
            # 记录初始内存状态
        self.log_memory_info("系统初始化完成")
        # if self.config.START_ANOMALY_DETECT:
        #     self.algo._prepare_anomaly_data()
        #     self.anomaly_thread = AnomalyMonitorThread(redis_client=self.redis_stream, config=self.config, logger=logger)
        #     self.anomaly_thread.daemon = True
        #     self.anomaly_thread.start()
       #self.replay_buffer = ReplayBuffer(self.config.REPLAYBUFFER_CAPACITY, self.config.BATCH_SIZE, self.config)
    
    def master_follow_phase_config(self, solution_phases):     
        """
        根据方案相位列表，构建：
        - MASTER_FOLLOW_PHASE_DICT: master_phase -> [follow_phase1, follow_phase2, ...]
        - FOLLOW_MASTER_PHASE_DICT: follow_phase -> master_phase
        """
        # 每次重建前先清空，避免残留旧配置
        self.config.MASTER_FOLLOW_PHASE_DICT = {}
        self.config.FOLLOW_MASTER_PHASE_DICT = {}

        master = 0
        for i in range(len(solution_phases)):
            phase_temp = solution_phases[i]
            if 'follow' not in phase_temp:
                # 遇到新的 master 相位
                self.config.MASTER_FOLLOW_PHASE_DICT[phase_temp] = []
                master = i
            else:
                # 跟随相位：添加到当前 master 的列表，并记录反向映射
                master_phase = solution_phases[master]
                self.config.MASTER_FOLLOW_PHASE_DICT[master_phase].append(phase_temp)
                self.config.FOLLOW_MASTER_PHASE_DICT[phase_temp] = master_phase

    
    def take_action_to_redis(self):
        try:
            # 开始监控
            if not hasattr(self, 'call_count'):
                self.call_count = 0
            self.call_count += 1
                        # 在内存监控中调用
            if self.call_count % 1000 == 0:
                self.log_memory_info(f"第{self.call_count}次调用开始")
            
    
            # # 每1000次调用记录一次详细内存信息
            # if self.call_count % 1000 == 0:
            #     self.log_memory_info(f"第{self.call_count}次调用-获取数据后")
            #     self.log_memory_snapshot(f"第{self.call_count}次调用")
                
            # 检查ReplayBuffer状态
            if hasattr(self.algo, 'replay_buffer'):
                buffer_size = len(self.algo.replay_buffer.buffer)
                self.algo.log_collector.log(
                    logging.INFO,
                    f"ReplayBuffer状态 - 大小: {buffer_size}, 容量: {self.algo.replay_buffer.capacity}"
                )
            origin_state_pre_time = t.time()
            self.algo.log_collector.log(logging.DEBUG, "算法启动，开始调用take action")
            phase = None
            origin_state = self.redis_stream.get_latest_data(self.mq_config.DB_ORIGIN_STATE, self.mq_config.KEY_ORIGIN_STATE + ":" + self.config.INTERSECTION, 1, self.mq_config.STREAM_READ_FROM_ORIGIN)
            origin_state_after_time = t.time()
            env_state_pre_time = t.time()
            env_state = self.redis_stream.get_latest_data(self.mq_config.DB_ENV_STATE, self.mq_config.KEY_ENV_STATE + ":" + self.config.INTERSECTION, 1, self.mq_config.STREAM_READ_FROM_ENV)
            env_state_after_time = t.time()   
            print(f"获取采集数据运行时间{origin_state_after_time - origin_state_pre_time}")
            print(f"获取信号机数据运行时间{env_state_after_time - env_state_pre_time}")
            if origin_state is not None and env_state is not None:
                signal_config = json.loads(self.redis_stream.get_value_by_key(self.mq_config.DB_SIGNAL_CONFIG, self.mq_config.KEY_SIGNAL_CONFIG + ":" + str(self.config.INTERSECTION)))
                self.config.SIGNAL_IN_CONTROL = signal_config["signalCtl"].get("isInControl")
                self.algo.log_collector.log(logging.INFO, f"SIGNAL_IN_CONTROL:{self.config.SIGNAL_IN_CONTROL}")
                vehicle_map = self.convert_cur_state(origin_state)
                state = {}
                state[self.config.INTERSECTION] = vehicle_map      
                self.algo.log_collector.log(logging.INFO, f"origin_info_state:{origin_state}")
                self.algo.log_collector.log(logging.INFO, f"lane_info_state:{state}")
                self.redis_stream.push_data(self.mq_config.DB_LANE_TO_PHASE, self.mq_config.KEY_LANE_TO_PHASE + ":" + self.config.INTERSECTION, vehicle_map)
                self.algo.log_collector.log(logging.INFO, f"signal_env_state:{env_state}")     
                phase = self.take_action(state, env_state)
                self.algo.log_collector.log(logging.INFO,f"phase_history :{self.config.ACTION_HISTORY}")
                self.algo.log_collector.log(logging.INFO,f'overflow_history:{self.algo.config.OVERFLOW_HISTORY}')
                self.algo.log_collector.log(logging.INFO, f"algo_return:{phase}")

                #算法计算后进行检查
                self.post_safe_rules.excute_rules_chain(state, env_state, phase)  
            current_time = t.time()           
            redis_dict = {"alg_return": phase, "timestamp":current_time}
            if origin_state_after_time - origin_state_pre_time >= 3 :
                self.algo.log_collector.log(logging.ERROR, f"lane_info_state:{None}")
                self.algo.log_collector.log(logging.ERROR, "采集未传入数据或采集数据超时，算法无法决策")
            if env_state_after_time - env_state_pre_time >= 3 :
                self.algo.log_collector.log(logging.ERROR, f"signal_env_state:{None}")
                self.algo.log_collector.log(logging.ERROR, "信号机 未传入数据或采集数据超时，算法无法决策")
                print("采集未传入数据，算法无法决策")
            # 安全地保存日志
            # 每100次调用记录一次内存信息
            if self.call_count % 100 == 0:
                self.log_memory_info(f"第{self.call_count}次调用结束")
            success, error_msg = self.algo.log_collector.save_latest_log(self.config.INTERSECTION)
            if not success:
                print(f"保存日志失败: {error_msg}")
            if redis_dict['alg_return'] != None:
                return self.redis_stream.push_data(self.mq_config.DB_ALGORITHM_CONTROL, self.mq_config.KEY_ALGORITHM_CONTROL + ":" + self.config.INTERSECTION, redis_dict)           
            else:
                return 0

                    
        except:
            self.config.LOGGER(0, "Advanced_alg",  f"take action to redis exception error: {traceback.format_exc()}")
            self.algo.log_collector.log(logging.ERROR, f"take action to redis exception error: {traceback.format_exc()}")
            self.algo.log_collector.save_latest_log(self.config.INTERSECTION)
            self.log_memory_info("异常处理中")
            return 0
        
    #@timing_decorator
    def take_action(self, state: Dict, env_state_shallow: Dict):
        try:
            # 使用浅拷贝，因为 env_state 在后续代码中只被读取，不会被修改
            env_state = dict(env_state_shallow) if isinstance(env_state_shallow, dict) else env_state_shallow
            self.config.PHASES_LIST, self.config.CURRENT_PLAN_STAGE_PHASE, self.config.CURRENT_PLAN_PHASE_TO_NUMBER = update_phases_by_stage(env_state["phases"], self.config.STAGE_PHASE)
            # 如果PHASES_LIST不为空列表，才执行筛选逻辑
            if self.config.PHASES_LIST:
                self.config.PHASES = [p for p in self.config.PHASES_LIST if p in self.config.PHASES]
            self.config.PHASE_NUMBER = len(self.config.PHASES)
            self.get_signal_status(self.config.CURRENT_PLAN_STAGE_PHASE, env_state)           
            self.config.FOLLOW_PHASES = []
            #如果当前路口存在溢出方案
            if self.config.OVERFLOW_PHASE_TO_ROAD:           
                overflow_list = list(self.config.OVERFLOW_PHASE) 
                
                #从env_state中取出非溢出相位的相位列表
                solution_phases = [item for item in self.config.PHASES_LIST if item not in set(overflow_list)]
            else:
                solution_phases = self.config.PHASES_LIST
            #进行一轮的清空
            self.config.MASTER_PHASES = []
            self.config.FOLLOW_PHASES = []
            for phase in solution_phases:
                if 'follow' not in phase:
                    self.config.MASTER_PHASES.append(phase)
                else:
                    self.config.FOLLOW_PHASES.append(phase.replace('follow_',''))                  
            self.master_follow_phase_config(solution_phases)   
            if self.config.START_ANOMALY_DETECT == True:
                if self.anomaly_detector.is_normal(env_state) == False:
                    return None
            #检查安全规则入口
            check_result = self.pre_safe_rules.excute_rules_chain(state, env_state)
            
            #安全规则返回failure，则表示不通过，action返回none
            if check_result is RuleResult.FAILURE:
                return None

            #安全规则返回success不处理
            elif check_result is RuleResult.SUCCESS:
                pass
            #安全规则返回int值，表示在安全规则中返回的phase
            else: 
                if self.config.ALGO_STATUS is AlgorithmStatus.OVERFLOW_PHASE:
                    #buffer存入溢出时的数据
                    self.algo.replay_buffer.store(state, env_state, check_result, 1)
                else:
                    #buffer存入其他安全规则下的数据
                    self.algo.replay_buffer.store(state, env_state, check_result, 2)
                return check_result

            #通过安全规则，进入核心算法
            action = self.algo.take_action(state, env_state)
            #print(f'phase_history :{self.config.ACTION_HISTORY}')
            self.algo.replay_buffer.store(state, env_state, action, 0)

            if self.config.START_ANOMALY_DETECT:
                # 异常检测模块
                if self.anomaly_detector.get_result() != None:
                    return None
            return action 
        except:
            self.config.LOGGER(0, "Advanced_alg",  f"take action exception error: {traceback.format_exc()}")
            self.algo.log_collector.log(logging.ERROR, f'Advanced_alg, take action to redis exception error: {traceback.format_exc()}')
            raise 
    def convert_cur_state(self, state: Dict):
        return self.algo.feature_extract.convert_cur_state(state)
    
    #获得cityflow的state
    def convert_cur_state_cf(self, state:Dict, inter_vehicles: Dict):
        return self.algo.feature_extract.convert_cur_state_cf(state, inter_vehicles)
    
    def convert_neighbor_state(self, state: Dict):
        return self.algo.feature_extract.convert_neighbor_state(state)
    

            
            
    #获取信号机状态
    def get_signal_status(self, phases_list, env_state: Dict):
        curr_action = env_state['currentPhase']
        if curr_action == 0:
            return
        curr_phase = phases_list[curr_action]
        #判断当前config是否配了溢出
        if hasattr(self.algo.config, 'OVERFLOW_PHASE'):
            overflow_phases = getattr(self.algo.config, 'OVERFLOW_PHASE')
        else:
            overflow_phases = []
        if self.config.CITYFLOW_TEST == 1:
            if phases_list[curr_action].startswith('follow'): 
                self.algo.config.SIGNAL_CONTROLLER_STATUS = SignalControllerStatus.FOLLOW_PHASE
        #其余情况都为普通相位
            else:
                self.algo.config.SIGNAL_CONTROLLER_STATUS = SignalControllerStatus.PHASE
            return 
        #当前相位是溢出相位

        if overflow_phases and curr_phase in overflow_phases:
            self.algo.config.SIGNAL_CONTROLLER_STATUS = SignalControllerStatus.OVERFLOW_PHASE
        #当前相位以follow开头表明为跟随相位
        elif phases_list[curr_action].startswith('follow'): 
            self.algo.config.SIGNAL_CONTROLLER_STATUS = SignalControllerStatus.FOLLOW_PHASE
        #其余情况都为普通相位
        else:
            self.algo.config.SIGNAL_CONTROLLER_STATUS = SignalControllerStatus.PHASE
    

    def stop(self):
        if hasattr(self.config, 'stop_config_monitor'):
            self.config.stop_config_monitor()
        self.algo.replay_buffer.stop_median_thread()
        self.redis_stream.close()
        print('close掉所有线程以及连接')
        
    def get_local_ip(self):
        '''
        获取本机真实ip地址,防止获取127.0.0.1
        '''
        try:
            # 使用 UDP 套接字连接到一个外部地址（不需要真的发出去）
            s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            s.connect(("8.8.8.8", 80))  # Google DNS 作为目标地址
            ip = s.getsockname()[0]
            s.close()
            return ip
        except Exception:
            return "127.0.0.1"




    def log_memory_info(self, context=""):
        """记录内存信息到日志 - 简化版本，避免耗时操作"""
        try:
            # 只记录基本内存信息，不进行耗时操作
            process = psutil.Process(os.getpid())
            memory_mb = process.memory_info().rss / 1024 / 1024
            
            # 记录到日志
            self.algo.log_collector.log(
                logging.INFO, 
                f"内存监控[{context}] - 进程内存: {memory_mb:.2f}MB"
            )
            
            # 如果内存超过阈值，记录详细信息
            if memory_mb > 1000:  # 超过1GB
                self.algo.log_collector.log(
                    logging.WARNING,
                    f"内存使用过高警告: {memory_mb:.2f}MB"
                )
                
        except Exception as e:
            self.algo.log_collector.log(logging.ERROR, f"内存监控失败: {e}")


