from algorithms.models import *
import numpy as np
from algorithms.utils.util import index_to_actionlist
import datetime
class AdvancedV1(Agent):
    def __init__(self, config):
        """
        功能: 初始化AdvancedMaxPressure智能体,设置参数、日志收集器等。
        输入:
            config: 配置参数对象,包含算法运行所需的参数。
        输出:
            无
        """
        super().__init__(config)
        self.config = config
        self.log_collector = LogCollector(enable_print=True)
        # 是否车辆连续增加
        self.is_traffic_jam_count = 0 
        self.status = 0 # advanced的模式，有高峰期0，和低峰期 1
        self.high_level_start_time = 0
        # 将行人映射到车辆对应的相位，比如西方向的行人可以映射到  西东，西北两个相位的车
        self.person_phase_map = {'WE':'W', 'WN': 'W', 'EW': 'E', 'ES':'E', 'NS': 'N', 'NE': 'N', 'SN':'S','SW':'S', 'WW':'W','SS':'S','EE':'E','NN':'N'}
        self.advanced_weight = self.config.ADVANCED_WEIGHT
        self.INITIAL_MIN_RUNNING_SPEED = self.config.MIN_RUNNING_SPEED 
        #考虑到MINGREENTIME是一个可变对象，修改为copy
        self.INITIAL_MIN_GREEN_TIME = self.config.MIN_GREEN_TIME.copy()
        self.INITIAL_MAX_KEEP_TIME = self.config.MAX_KEEP_TIME.copy()
        self.config.LOGGER(5, "Advanced_alg",  f"Advanced control version is 1.2.4")
        self.log_collector.log(logging.DEBUG, f'Advanced_alg, Advanced control version is 1.2.4')
        self.peak_hour_active = False  # 是否已激活高峰期
        self.peak_hour_start_time = 0  # 高峰期开始时间  
        self.peak_hour_duration = 0   # 高峰期持续时间（分钟）
        self.peak_hour_type = None  # 高峰期类型: 'morning', 'evening', 'custom'
        self.replay_buffer = ReplayBuffer(self.config.REPLAYBUFFER_CAPACITY, self.config.BATCH_SIZE, config)   
    def peak_weight_change(self, state: Dict, env_state):
        """
        功能: 判断是否为高峰状态并调整权重和相关参数。
        输入:
            state: 当前路口状态，字典格式
            env_state: 环境状态，例如车流等数据
        输出:
            无
        """
        # 保存之前的高峰期状态，用于判断是否刚从高峰期退出
        was_peak_hour = self.peak_hour_active
        previous_peak_type = self.peak_hour_type
        
        # 获取高峰期状态和类型  
        is_peak_hour, current_peak_type = self._is_time_peak_hour(env_state)
        
        if is_peak_hour:
            self.advanced_weight = self.config.HIGH_LEVEL_ADVANCED_WEIGHT_MINSPEED[0]
            if self.peak_hour_type == 'morning':
                # 早高峰特殊处理
                self.config.MIN_GREEN_TIME = self.config.MIN_GREEN_TIME_HIGH_MORNING_LEVEL
                self.config.MAX_KEEP_TIME = self.config.MAX_KEEP_TIME_HIGH_MORNING_LEVEL
            elif self.peak_hour_type == 'evening':
                # 晚高峰特殊处理
                self.config.MIN_GREEN_TIME = self.config.MIN_GREEN_TIME_HIGH_EVENING_LEVEL
                self.config.MAX_KEEP_TIME = self.config.MAX_KEEP_TIME_HIGH_EVENING_LEVEL
            elif self.peak_hour_type == 'custom':
                # 自定义高峰期处理
                self.config.MIN_GREEN_TIME = self.config.MIN_GREEN_TIME_HIGH_LEVEL
                self.config.MAX_KEEP_TIME = self.config.MAX_KEEP_TIME_HIGH_LEVEL
            # 使用返回的高峰期类型，确保获取到最新的类型
            peak_type = current_peak_type if current_peak_type else self.peak_hour_type
            peak_type_name = {'morning': '早高峰', 'evening': '晚高峰', 'custom': '自定义高峰期'}.get(peak_type, '高峰期')
            # 只在刚进入高峰期时记录日志
            if not was_peak_hour:
                self.config.LOGGER(5,'Advanced_alg',f'{peak_type_name}激活: min_running_speed is: {self.config.MIN_RUNNING_SPEED}')
                self.log_collector.log(logging.INFO, f'Advanced_alg, {peak_type_name}激活: min_running_speed is: {self.config.MIN_RUNNING_SPEED}' )
        else:
            # 刚从高峰期退出时记录日志
            if was_peak_hour:
                peak_type_name = {'morning': '早高峰', 'evening': '晚高峰', 'custom': '自定义高峰期'}.get(previous_peak_type, '高峰期')
                self.config.LOGGER(5,'Advanced_alg',f'{peak_type_name}结束，恢复正常模式')
                self.log_collector.log(logging.INFO, f'Advanced_alg, {peak_type_name}结束，恢复正常模式')
            self.advanced_weight = self.config.ADVANCED_WEIGHT
            self.config.MIN_GREEN_TIME = self.INITIAL_MIN_GREEN_TIME.copy()
            self.config.MAX_KEEP_TIME = self.INITIAL_MAX_KEEP_TIME.copy()
            #self.check_phase_vehicle_is_full(state, env_state) 
        # elif (env_state['timestamp'] - self.high_level_start_time) >= 60:
        #     self.high_level_start_time = 0
        #     self.status = 0
        self.config.MIN_RUNNING_SPEED = self.replay_buffer.instance.get_min_speed()
    def get_bind_phases_depth(self, bind_phases):
        '''   
        获取递归的深度
        '''
        if isinstance(bind_phases, int):
            return 0
        if isinstance(bind_phases, (list, np.ndarray)):
            return 1 + self.get_bind_phases_depth(bind_phases[0])
        return 0

    #最基础的相位选择方法
    def take_one_layer_action(self, curr_action, combine_phases, is_outermost=False):
        """
        功能: 针对单层相位,选择压力最大的相位。
        输入:
            curr_action: 当前相位索引
            combine_phases: 当前层可选相位组合
        输出:
            action: 选中的相位索引
        """
        action = curr_action
        phase_p = []
        phase_d = []
        weight = self.advanced_weight
        run_vehicle = self.cur_running_vehicle_roads
        wait_vehicle = self.cur_waiting_vehicle_roads
        for i in range(len(combine_phases)):
            phase_str = combine_phases[i].split('_')
            demand,pressure = 0,0
            for phase in phase_str:
                demand += run_vehicle[phase] 
                pressure += wait_vehicle[phase] 
            phase_p.append(pressure)
            phase_d.append(demand)
        # 判断config中是否有PHASE_PREFERENCE属性，并且只在最外层应用
        if is_outermost and hasattr(self.config, 'PHASE_PREFERENCE'):
            for i in range(len(phase_d)):
                key = str(i)
                if key in self.config.PHASE_PREFERENCE:
                    phase_d[i] *= self.config.PHASE_PREFERENCE[key]
        if action == -1:
            action = phase_p.index(max(phase_p))
        elif phase_d[action] * weight >= max(phase_p):
            pass
        else:
            action = phase_p.index(max(phase_p))
        return action  
    
    #对每一层进行相位选择
    #new_layers_action_result要返回的action list， branch_flag该层选择是否已经和current phase不在一颗子树上了
    def layers_action(self, bind_phases, old_action_list, new_layers_action_result, branch_flag:bool, layers_flag:list):
        """
        功能: 递归地对每一层进行相位选择,生成最终动作（相位）序列。
        输入:
            bind_phases: 当前层可选相位结构
            old_action_list: 上一层相位列表
            new_layers_action_result: 新相位结果列表（递归填充）
            branch_flag: 是否已分支
            layers_flag: 捆绑相位各层是否顺序执行标志
        输出:
            无,结果写入new_layers_action_result
        """
        if type(bind_phases) == int:
            return
        combine_phases = []
        # 兼容多种格式：[[0,1],[2,3]]、[[0,1],[2]]（捆绑+单独）、[0,1]（扁平）
        for i in bind_phases:
            a = np.atleast_1d(i).flatten()
            l = np.array(self.config.PHASES)[a]
            t = "_".join(l)
            combine_phases.append(t)

        if branch_flag == True:
            current_phase = -1
        else:
            current_phase = old_action_list[0]
        # 判断是否最外层
        num_layers = self.get_bind_phases_depth(self.config.BIND_PHASES)
        is_outermost = len(old_action_list) == num_layers
        action = self.take_one_layer_action(current_phase, combine_phases, is_outermost=is_outermost)
        if action != current_phase and branch_flag == True: 
            if layers_flag[0] == True:
                action = 0
        if action != current_phase and branch_flag == False: 
            branch_flag = True
            if layers_flag[0] == True:
                action = (current_phase + 1) % len(combine_phases)
        new_layers_action_result.append(action)
        next_bind_phases = bind_phases[action]
        old_action_list = old_action_list[1:]
        layers_flag = layers_flag[1:]
        self.layers_action(next_bind_phases, old_action_list, new_layers_action_result, branch_flag, layers_flag)

    def algorithm_control(self, curr_action, state, env_state):
        """
        功能: 算法主控流程,生成多层相位序列。
        输入:
            curr_action: 当前相位索引
            state: 当前路口状态，字典格式
            env_state: 环境状态，例如车流等数据
        输出:
            new_layers_action_result: 多层相位序列
        """
        state = state[self.config.INTERSECTION]
        self.cur_waiting_vehicle_roads = state["waiting_vehicle"]
        self.cur_running_vehicle_roads = state["running_vehicle"]
        old_action_list = []
        
        index_to_actionlist(curr_action - 1, self.config.BIND_PHASES, old_action_list)
        new_layers_action_result = []
        self.layers_action(self.config.BIND_PHASES, old_action_list, new_layers_action_result, False, self.config.LAYERS_ORDER_FLAG)
        return new_layers_action_result

    def take_action(self, state: Dict, env_state):
        """
        功能:根据当前状态和环境状态选择相位，需子类具体实现。
        输入:
            state: 当前路口状态，字典格式
            env_state: 环境状态，例如车流等数据
        输出:
            action: 算法得到的相位
        """
        # 若为高峰状态，将权重等参数调整为高峰下的参数
        if self.config.CITYFLOW_TEST == 0:
            self.peak_weight_change(state, env_state)
        # 对于有替换方案的路口
 
        # if self.config.CITYFLOW_TEST == 0:
        action = self.take_follow_action(state, env_state)
        self.set_cur_input_and_output(action, state, env_state)
        if self.config.DEBUG:
            msg = f"DEBUG: advanced_v1 env_state is {env_state}, algorithm output phase is {self.cur_action}, \
                                                running vehicle is {self.cur_running_vehicle_roads}, waiting vehicle is {self.cur_waiting_vehicle_roads} \
                                                phase_history is {self.config.ACTION_HISTORY}, advanced weight is {self.advanced_weight}"
            self.config.LOGGER(5,"Advanced_alg", msg)
            self.log_collector.log(logging.DEBUG, f'Advanced_alg, {msg}')
        return action
    
    #检查高峰态
    def check_phase_vehicle_is_full(self, state: Dict, env_state):
        """
        功能: 检查每个相位的车辆数是否达到上限,判断是否进入高峰态，并设置相关参数。
        输入:
            state: 当前路口状态，字典格式
            env_state: 环境状态，例如车流等数据
        输出:
            无
        """
        running_vehicle = state[self.config.INTERSECTION]['running_vehicle']
        waiting_vehicle = state[self.config.INTERSECTION]['waiting_vehicle']
        phase_vehicle_count = {}
        for phase in self.config.PHASES:
            phase_vehicle_count[phase] = 0
            p_str = phase.split('_')
            for p in p_str:
                phase_vehicle_count[phase] += running_vehicle[p]
                phase_vehicle_count[phase] += waiting_vehicle[p]
        p_to_vehicle_list = list(phase_vehicle_count.values())
        lane_numbers = []
        # 计算每个相位的唯一车道数量
        for phase in self.config.PHASES:
            # 将相位字符串分割为车道列表
            phs = phase.split("_") 
            # 用于存储唯一车道的集合 
            unique_lanes = set()  
            for p in phs:
                for k,v in self.config.LANE_TO_PHASE.items():
                    if k[-1] == 'L':
                        continue
                    # 如果车道在车道数量字典中
                    if p in v: 
                        # 将车道添加到唯一车道集合中
                        unique_lanes.add(k)  
            lane_numbers.append(len(list(unique_lanes)))
        # 检查每条车道是否达到车辆上限 150 / 7
        max_vehicle = max(p_to_vehicle_list)
        max_index = p_to_vehicle_list.index(max_vehicle)
        if max_vehicle > lane_numbers[max_index] * 4:
            self.is_traffic_jam_count += 1
        else:
            self.is_traffic_jam_count = 0
        
        if self.is_traffic_jam_count > 5:
            self.is_traffic_jam_count = 0
            self.status = 1
            self.high_level_start_time = env_state['timestamp']
    def _is_time_peak_hour(self, env_state):
        """
        判断当前时间是否在高峰期
        支持从JSON配置中读取时间格式
        """
        try:
            # 如果已经在高峰期，检查是否超时
            if self.peak_hour_active:
                current_time = datetime.datetime.fromtimestamp(env_state['timestamp'])
                peak_duration_minutes = (current_time - self.peak_hour_start_time).total_seconds() / 60
                
                # 如果超过配置的持续时间，退出高峰期
                if peak_duration_minutes >= self.peak_hour_duration:
                    peak_type_name = {'morning': '早高峰', 'evening': '晚高峰', 'custom': '自定义高峰期'}.get(self.peak_hour_type, '高峰期')
                    self.peak_hour_active = False
                    self.config.LOGGER(5, 'Advanced_alg', f'{peak_type_name}时间结束（持续{self.peak_hour_duration}分钟），退出高峰模式')
                    self.peak_hour_type = None
                    return False,self.peak_hour_type
                else:
                    return True,self.peak_hour_type
            
            timestamp = env_state['timestamp']
            if isinstance(timestamp, (int, float)):
                current_time = datetime.datetime.fromtimestamp(timestamp)
            else:
                current_time = timestamp
            
            current_minutes = current_time.hour * 60 + current_time.minute
            
            # 检查早高峰
            if hasattr(self.config, 'MORNING_RUSH') and self.config.MORNING_RUSH:
                morning_period = self._parse_time_period(self.config.MORNING_RUSH)
                if morning_period and len(morning_period) == 2 and morning_period[0] <= current_minutes <= morning_period[1]:
                    self.peak_hour_active = True
                    self.peak_hour_type = 'morning'
                    self.peak_hour_start_time = current_time
                    self.peak_hour_duration = morning_period[1] - morning_period[0]
                    self.config.LOGGER(5, 'Advanced_alg', f'进入早高峰模式: {self.config.MORNING_RUSH[0]} - {self.config.MORNING_RUSH[1]}')
                    return True,self.peak_hour_type
            
            # 检查晚高峰
            if hasattr(self.config, 'EVENING_RUSH') and self.config.EVENING_RUSH:
                evening_period = self._parse_time_period(self.config.EVENING_RUSH)
                if evening_period and len(evening_period) == 2 and evening_period[0] <= current_minutes <= evening_period[1]:
                    self.peak_hour_active = True
                    self.peak_hour_type = 'evening'
                    self.peak_hour_start_time = current_time
                    self.peak_hour_duration = evening_period[1] - evening_period[0]
                    self.config.LOGGER(5, 'Advanced_alg', f'进入晚高峰模式: {self.config.EVENING_RUSH[0]} - {self.config.EVENING_RUSH[1]}')
                    return True,self.peak_hour_type
            
            # 检查自定义高峰期
            if hasattr(self.config, 'CUSTOM_PEAK_HOURS') and self.config.CUSTOM_PEAK_HOURS:
                custom_period = self._parse_time_period(self.config.CUSTOM_PEAK_HOURS)
                if custom_period and len(custom_period) == 2 and custom_period[0] <= current_minutes <= custom_period[1]:
                    self.peak_hour_active = True
                    self.peak_hour_type = 'custom'
                    self.peak_hour_start_time = current_time
                    self.peak_hour_duration = custom_period[1] - custom_period[0]
                    self.config.LOGGER(5, 'Advanced_alg', f'进入自定义高峰期模式: {self.config.CUSTOM_PEAK_HOURS[0]} - {self.config.CUSTOM_PEAK_HOURS[1]}')
                    return True,self.peak_hour_type
            
            return False,self.peak_hour_type
            
        except Exception as e:
            self.config.LOGGER(0, 'Advanced_alg', f'时间判断错误: {str(e)}')
            return False,self.peak_hour_type
        
    
    def _parse_time_period(self, time_period):
        """
        功能: 解析时间格式字符串为分钟数
            支持格式: ["08:00", "09:00"] 或 ["8:00", "9:00"]
        输入:
            time_period: 开始时间，结束时间的数组如：["08:00", "09:00"] 或 ["8:00", "9:00"]
        输出:
            转换过的分钟数，如：[480, 540]
        """
        try:
            if not time_period or len(time_period) != 2:
                return None
            
            start_time = time_period[0]
            end_time = time_period[1]
            
            # 解析开始时间
            start_hour, start_minute = map(int, start_time.split(':'))
            start_minutes = start_hour * 60 + start_minute
            
            # 解析结束时间
            end_hour, end_minute = map(int, end_time.split(':'))
            end_minutes = end_hour * 60 + end_minute
            
            return [start_minutes, end_minutes]
            
        except Exception as e:
            self.config.LOGGER(0, 'Advanced_alg', f'时间解析错误: {str(e)}')
            return None
AdvancedMaxPressure = AdvancedV1  # backward-compatible alias
