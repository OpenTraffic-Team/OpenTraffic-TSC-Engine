import json
from algorithms.enums.algorithm_status_enum import AlgorithmStatus
from algorithms.enums.signal_status_enum import SignalControllerStatus
from .util import *
import traceback
from collections import deque
import threading
import time
import yaml
import os

class Config:
    """交通信号灯配置管理类
    
    负责从Redis或本地文件加载配置，并提供配置热重载功能。
    配置包括：硬件配置、传感器配置、信号灯配置、算法配置等。
    """
    
    # 默认配置值
    DEFAULT_SENSOR_CONF = {
        "id": "ANXL_XFL",
        "roads": [
            {
                "id": "ANXL_XFL_S",
                "lanes": "[]",
                "radars": {
                    "id": "XD_8",
                    "ip": "10.1.10.78",
                    "type": "XD",
                    "position": [2.35198998, 28.0431995]
                },
                "cameras": []
            }
        ],
        "crosswalks": [
            {
                "id": "ANXL_XFL_SCW",
                "cameras": [
                    {
                        "id": "YS_10",
                        "ip": "62.241.145.198",
                        "window": [780, 904, 1443, 1053],
                        "localUrl": "rtsp://10.1.10.123:8554/cw1"
                    }
                ]
            },
            {
                "id": "ANXL_XFL_NCW",
                "cameras": [
                    {
                        "id": "YS_12",
                        "ip": "62.241.145.199",
                        "window": [900, 717, 1547, 913],
                        "localUrl": "rtsp://10.1.10.123:8554/cw3"
                    }
                ]
            },
            {
                "id": "ANXL_XFL_ECW",
                "cameras": [
                    {
                        "id": "YS_13",
                        "ip": "62.241.145.200",
                        "window": [703, 749, 1651, 985],
                        "localUrl": "rtsp://10.1.10.123:8554/cw2"
                    }
                ]
            }
        ]
    }

    _DEFAULT_KEYS = {
        "hardware_config": "intersection_device",
        "sensor_config": "sensorConfig",
        "signal_config": "signalConfig",
        "alg_config": "algConfig",
    }

    def __init__(self, redis=None, test=False, config_path=None, sensor_cnf={}, mq_config=None):
        """初始化配置管理器
        
        Args:
            redis: Redis连接对象
            test: 是否为测试模式
            config_path: 测试模式下的配置文件路径
            sensor_cnf: 传感器配置
            mq_config: MQConfig实例，提供intersection及可配置的Redis key前缀
        """
        self.redis = redis
        self.mq_config = mq_config
        
        if test:
            self._load_test_config(config_path, sensor_cnf)
        else:
            self._load_config()
            self._start_hot_reload()

    def _init_common_vars(self):
        """初始化通用变量"""
        self.START_ANOMALY_DETECT = False
        self.LOGGER = print
        self.CITYFLOW_TEST = 0
        self.PHASES = []
        self.PHASE_NUMBER = 0
        self.SIGNAL_IN_CONTROL = 0
        self.ACTION_HISTORY = deque(maxlen=60)
        self.OVERFLOW_HISTORY = deque(maxlen=60)
        self.DEBUG = False
        self.MIN_RUNNING_SPEED = 0
        self.LANE_TO_PHASE = ""
        self.NEIGHBOUR_TO_PHASE = ""
        self._stop_config_monitor = False
        self.MAX_TRANSITION_DURATION = 0
        self.INIT_TIME = 0
    def _init_algorithm_vars(self):
        """初始化算法相关变量"""
        self.ALGO_VERSION = "v1"
        self.ALGO_STATUS = AlgorithmStatus.PHASE
        self.MODEL_PATH = ""
        self.ADVANCED_WEIGHT = 0
        self.HIGH_LEVEL_WEIGHT_MINSPEED = 0
        self.PHASES_LIST = []
        self.FOLLOW_PHASES = [] 
        self.MASTER_PHASES = []       
        self.MASTER_FOLLOW_PHASE_DICT = {}
        self.FOLLOW_MASTER_PHASE_DICT = {}


    def _init_safety_rules(self):
        """初始化安全规则相关变量"""
        self.DELAY_TIME = 0
        self.MIN_GREEN_TIME = []
        self.MIN_GREEN_TIME_LEVEL = []
        self.ADVANCED_TAKE_COUNT = 0    
        self.MAX_KEEP_TIME = {}
        self.PERSON_MIN_TIME = 0
        self.PERSON_FACTOR = 3
        self.MAX_KEEP_NUM = 0
        self.PERSON_RECONGNIZE_PLAN = 0
        self.PHASE_INDEX_DIFF = {}
        self.MEDIAN_TIME = 900
        self.REPLAYBUFFER_CAPACITY = 3600
        self.BATCH_SIZE = 64
        self.GAMMA = 0.99
        self.LEARNING_RATE = 0.001  
        self.EPOCH = 100
        self.TARGET_UPDATE_FREQ = 10

    def _init_overflow_vars(self):
        """初始化溢出相关变量"""
        self.OVERFLOW_PHASE_TO_ROAD = {}
        self.CYCLE_CONTROL = False

    def _redis_key(self, name):
        """返回可配置的Redis key前缀，优先使用mq_config中的值，否则使用默认值"""
        if self.mq_config is not None:
            attr = "KEY_" + name.upper()
            return getattr(self.mq_config, attr, self._DEFAULT_KEYS.get(name, name))
        return self._DEFAULT_KEYS.get(name, name)

    def _load_config(self):
        """从Redis加载配置"""
        if not (self.mq_config and self.mq_config.INTERSECTION):
            raise ValueError("mq_config中未配置intersection字段，请在mq_config.json中指定路口编号")
        self.INTERSECTION = self.mq_config.INTERSECTION
        
        # 加载传感器配置
        _sensor_raw = self.redis.get_value_by_key(self.mq_config.DB_SENSOR_CONFIG, self._redis_key("sensor_config") + ":" + str(self.INTERSECTION))
        self.SENSOR_CONF = json.loads(_sensor_raw) if _sensor_raw else self.DEFAULT_SENSOR_CONF
            
        # 加载信号灯配置
        signal_config = json.loads(self.redis.get_value_by_key(self.mq_config.DB_SIGNAL_CONFIG, self._redis_key("signal_config") + ":" + str(self.INTERSECTION)))
        self.STAGE_PHASE = signal_config["signalCtl"].get("stagePhase")
        
        # 初始化相位映射
        self.CURRENT_PLAN_STAGE_PHASE = {}
        self.CURRENT_PLAN_PHASE_TO_NUMBER = {}
        
        # 加载算法配置
        config = json.loads(self.redis.get_value_by_key(self.mq_config.DB_ALG_CONFIG, self._redis_key("alg_config") + ":" + str(self.INTERSECTION)))
        
        # 初始化各类变量
        self._init_common_vars()
        self._init_algorithm_vars()
        self._init_safety_rules()
        self._init_overflow_vars()
        self.LANE_TO_PHASE = {key.replace("{intersection_id}", self.INTERSECTION): value for key, value in config["lane_to_phase"].items()}
        # 设置算法配置
        self._set_algorithm_config(config)
        
        # 设置溢出配置
        if 'overflow_phase_to_road' in config:
            self._set_overflow_config(config)

    def _set_algorithm_config(self, config):
        """设置算法相关配置"""
        self.ALGO_VERSION = config['algo_version']
        self.DEBUG = config['debug']
        self.PHASES =  config['phases']
        self.PRE_FOLLOW_PHASE = None
        if "bind_phases" in config:
            self.BIND_PHASES = config['bind_phases']
            self.LAYERS_ORDER_FLAG = config['layers_order_flag']

        if self.ALGO_VERSION == 'v1':
            
            self.ADVANCED_WEIGHT = config['advanced_weight']
            self.HIGH_LEVEL_ADVANCED_WEIGHT_MINSPEED = config['high_level_weight_minspeed']
            self.MIN_GREEN_TIME_HIGH_LEVEL = config["phase_min_change_time_high_level"]
            self.MIN_GREEN_TIME_HIGH_MORNING_LEVEL = config["phase_min_change_time_high_morning_level"]
            self.MIN_GREEN_TIME_HIGH_EVENING_LEVEL = config["phase_min_change_time_high_evening_level"]
            self.MAX_KEEP_TIME_HIGH_MORNING_LEVEL = config["max_keep_time_high_morning_level"]
            self.MAX_KEEP_TIME_HIGH_EVENING_LEVEL = config["max_keep_time_high_evening_level"]
            self.MAX_KEEP_TIME_HIGH_LEVEL = config["max_keep_time_high_level"]
            self.MORNING_RUSH = config['morning_rush']
            self.EVENING_RUSH = config['evening_rush']
            self.CUSTOM_PEAK_HOURS = config['custom_peak_hours']
            if 'phase_preference' in config:
                self.PHASE_PREFERENCE = config["phase_preference"]
        elif self.ALGO_VERSION == 'v2':
            self.TRAINED_RL_MODEL_PHASE = config['trained_rl_model_phase']
            self.MODEL_PATH = config['model_path']
        elif self.ALGO_VERSION == 'v3':
            self.MODEL_PATH = config['model_path']
            self.FIXED_ORDER_LANES = ["W", "E", "N", "S"]
            self.SORT_ENTERING_LANES= self._sort_entering_lanes()
            self.OBS_LENGTH = 10
            self.MAX_LANE_LENGTH = 400
            self.IS_NOISE = False
            self.NOISE_TYPE = -1
            self.NOISE_SCALE = 1
            #train arguments
            self.MAX_MEMORY_LEN = 12000
            self.SAMPLE_SIZE = 3000
            self.EPOCHS = 30
        elif self.ALGO_VERSION == 'v4':
            # AttendLight 推理所需字段: MODEL_PATH + FIXED_ORDER_LANES
            self.MODEL_PATH = config['model_path']
            self.FIXED_ORDER_LANES = ["W", "E", "N", "S"]
            # ReplayBuffer 中位速计算使用该字段(保持和 v1 行为一致)
            self.HIGH_LEVEL_ADVANCED_WEIGHT_MINSPEED = config.get("high_level_weight_minspeed", [0, 0])

        self.MAX_TRANSITION_DURATION = config['max_transition_duration']    
        self.PERSON_RECONGNIZE_PLAN = config['person_recongnize_plan']
        self.DELAY_TIME = config['delay_time']
        self.MIN_GREEN_TIME = config["phase_min_change_time"]
        self.SIGNAL_CONTROLLER_STATUS = SignalControllerStatus.PHASE
        self.CYCLE_CONTROL = config['is_cycle_control']
        self.MAX_KEEP_TIME = config["phase_max_keep_time"]
        self.PERSON_MIN_TIME = config["person_min_time"]
        self.PERSON_FACTOR = config['person_factor']
        self.MAX_KEEP_NUM = config['phase_max_keep_num']
        self.INIT_TIME = config['init_time']
        
        if 'cityflowTest' in config:
            self.CITYFLOW_TEST = config['cityflowTest']
            
        self.MIN_RUNNING_SPEED = config['min_running_speed']
        self.ROAD_TO_LANE = get_road_by_lane(self.INTERSECTION, self.LANE_TO_PHASE)

    def _set_overflow_config(self, config):
        """设置溢出相关配置"""
        self.OVERFLOW_PHASE = config["overflow_phase"]
        self.OVERFLOW_PHASE_TO_ROAD = config['overflow_phase_to_road']
        self.OVERFLOW_MIN_GREEN_TIME = 6
        self.OVERFLOW_RULE_MASTER_TIME = 8
        self.OVERFLOW_VEHICLE_COUNT = config["overflow_vehicle_count"]
        self.ROAD_TO_OVERFLOW_VEHICLE_COUNT = config["road_to_overflow_vehicle_count"]
        self.OVERFLOW_TIMES = config["overflow_times"]
        self.MIN_OVERFLOW_DIS_SPEED = config["min_overflow_dis_speed"]
        self.MIN_OVERFLOW_DIS_SPEED_REALX = config["min_overflow_dis_speed_relax"]
        self.ALL_PHASES = list(self.OVERFLOW_PHASE_TO_ROAD.keys())
        self.PHASE_TO_OVERFLOW_PHASE = get_phase_to_overflow_phase(self.OVERFLOW_PHASE, self.PHASES)

    def reload_config(self):
        """重新加载配置"""
        print("Config 发生变化，重新加载")
        self._load_config()
        print("Config加载完成")

    def _start_hot_reload(self):
        """启动配置热重载功能
        
        开启一个守护线程，每秒检查配置是否发生变化
        """
        alg_db = self.mq_config.DB_ALG_CONFIG
        alg_config_key = self._redis_key("alg_config") + ":" + str(self.INTERSECTION)
        last_config = json.loads(self.redis.get_value_by_key(alg_db, alg_config_key))
        
        def monitor():
            nonlocal last_config
            while not self._stop_config_monitor:
                try:
                    current_config = json.loads(self.redis.get_value_by_key(alg_db, alg_config_key))
                    if last_config is not None and not is_equal(last_config, current_config):
                        print("配置变化，重新加载")
                        self.reload_config()
                        last_config = current_config
                except Exception as e:
                    print("配置检测失败")
                    traceback.print_exc()
                time.sleep(1)
                
        threading.Thread(target=monitor, daemon=True).start()

    def _load_test_config(self, config_path, sensor_cnf):
        """加载测试配置
        
        Args:
            config_path: 配置文件路径
            sensor_cnf: 传感器配置
        """
        with open(config_path) as f:
            config = yaml.safe_load(f.read())
            
        # 初始化各类变量
        self._init_common_vars()
        self._init_algorithm_vars()
        self._init_safety_rules()
        self._init_overflow_vars()
        self.INTERSECTION = config['cur_inter_id']
        self.LANE_TO_PHASE = {key.replace("{intersection_id}", self.INTERSECTION): value for key, value in config["lane_to_phase"].items()}
        self.STAGE_PHASE = config["stagePhase"]
        # 设置传感器配置
        self.SENSOR_CONF = sensor_cnf if sensor_cnf else self.DEFAULT_SENSOR_CONF
        
        # 设置算法配置
        self._set_algorithm_config(config)
        
        # 设置溢出配置
        if 'overflow_phase_to_road' in config:
            self._set_overflow_config(config)
    
    def stop_hot_reload(self):
        """停止配置热重载监控线程"""
        self._stop_config_monitor = True

    # 兼容旧接口，避免外部调用报错
    def stop_config_monitor(self):
        return self.stop_hot_reload()
    
    def _sort_entering_lanes(self):
        """
        功能：将入度车道按固定顺序排序
        """
        sorted_list_entering_lanes = []
        for approach in self.FIXED_ORDER_LANES:
            for k,v in self.LANE_TO_PHASE.items():
                if approach  in k :
                    sorted_list_entering_lanes.append(k)
        return sorted_list_entering_lanes
    
    def _generate_lane_length(self, length):
        lane_length = {lane: length for lane in self.SORT_ENTERING_LANES}
        return lane_length
