from algorithms.models import *
from algorithms.enums.signal_status_enum import SignalControllerStatus
from algorithms.utils.replay_buffer import ReplayBuffer
from algorithms.utils.util import signal_index_2_master_index, actionlist_to_index, master_index_2_signal_index, return_next_action_index

class Agent(ABC):
    def __init__(self, config):
        """
        功能:初始化Agent对象,设置配置参数、特征提取器、异常检测数据、经验回放缓存等。
        输入:
            config: 配置对象，包含算法运行所需的参数。
        输出:
            无
        """
        self.config = config
        self.feature_extract = FeatureExtract(self)
        self._prepare_anomaly_data()
        self.pre_master_phase = None
        self.next_master_phase = None
        
        
    def _prepare_anomaly_data(self):
        """
        功能:为异常检测做数据准备，初始化相关变量。
        输入:无
        输出:无
        """
        # 为异常检测做数据准备
        self.cur_waiting_vehicle_roads = None
        self.cur_running_vehicle_roads = None
        self.cur_action = None
        self.state = None
        self.env_state = None

    @abstractmethod
    def take_action(self, state: Dict, env_state):
        """
        功能:根据当前状态和环境状态选择动作，需子类具体实现。
        输入:
            state: 当前路口状态，字典格式
            env_state: 环境状态，例如车流等数据
        输出:
            action: 算法得到的相位
        """
        pass

    @abstractmethod
    def algorithm_control(self,state: Dict, env_state):
        """
        功能:算法控制主流程（需子类实现）。
        输入:
            state: 当前路口状态，字典格式
            env_state: 环境状态，例如车流等数据
        输出:
            new_layers_action_result: 多层相位序列
        """
        pass

    def get_cur_input_and_output(self):
        """
        功能:获取当前输入输出相关变量。
        输入:无
        输出:
            (cur_waiting_vehicle_roads, cur_running_vehicle_roads, cur_action, state, env_state)
        """
        return self.cur_waiting_vehicle_roads, self.cur_running_vehicle_roads, self.cur_action, self.state, self.env_state
    
    def set_cur_input_and_output(self, action, state, env_state):
        """
        功能:设置当前输入输出相关变量。
        输入:
            action: 当前相位索引
            state: 当前路口状态，字典格式
            env_state: 环境状态，例如车流等数据
        输出:无
        """
        self.cur_action = action
        self.state = state 
        self.env_state = env_state

    def convert_cur_state(self, state: Dict):
        """
        功能:转换当前状态为特征提取器所需格式。
        输入:
            state: 当前状态字典
        输出:
            转换后的状态
        """
        return self.feature_extract.convert_cur_state(state)
    
    #获得cityflow的state
    def convert_cur_state_cf(self, state:Dict, inter_vehicles: Dict):
        """
        功能:从cityflow环境中提取车流数据特征。
        输入:
            state: 当前状态字典
            inter_vehicles: 路口车辆信息字典
        输出:
            转换后的状态(vehicle_map)
        """
        return self.feature_extract.convert_cur_state_cf(state,inter_vehicles)
    
    def convert_neighbor_state(self, state: Dict):
        """
        功能:转换邻居状态为特征提取器所需格式。
        输入:
            state: 邻居状态字典
        输出: 
            转换后的邻居状态(vehicle_map)
        """
        return self.feature_extract.convert_neighbor_state(state)
         
    # TODO:  未来子相位方案模块化，不同城市不同模块进行替换
    # 兰州特有，待优化    
    # 子相位方案

    def take_follow_action(self, state, env_state):
        """
        功能:根据当前状态和环境状态，执行跟随相位的相位决策逻辑。
        输入:
            state: 当前路口状态，字典格式
            env_state: 环境状态，例如车流等数据
        输出:
            跟随相位下的相位索引
        """
        if self.config.ALGO_STATUS.value != self.config.SIGNAL_CONTROLLER_STATUS.value:
            #由于算法的状态肯定领先于信号机状态，只用判别信号机状态就行
             #1.信号机状态不是follow态，继续返回上次算法返回的follow phase
            if self.config.SIGNAL_CONTROLLER_STATUS != SignalControllerStatus.FOLLOW_PHASE:
                return self.config.PRE_FOLLOW_PHASE
            else:
             #2.信号机状态是phase态，返回上次算法返回的另一个父相位
                return self.next_master_phase
        
        curr_action = env_state["currentPhase"]
        if self.config.ALGO_STATUS is AlgorithmStatus.FOLLOW_PHASE:
            if self.pre_master_phase is not None:
                curr_action = self.pre_master_phase
            else:
                curr_action = self.config.ACTION_HISTORY[-1]
        curr_action = signal_index_2_master_index(curr_action, self.config.PHASES, self.config.CURRENT_PLAN_STAGE_PHASE) + 1
        if self.config.ALGO_VERSION == "v3": 
            alg_action_signal_index= self.algorithm_control(curr_action, state, env_state)
        else:
            alg_action_list = self.algorithm_control(curr_action, state, env_state)
            alg_action_index = actionlist_to_index(alg_action_list, self.config.BIND_PHASES)
            #alg_action转为ac index
            alg_action_signal_index = master_index_2_signal_index(alg_action_index, self.config.PHASES, self.config.CURRENT_PLAN_PHASE_TO_NUMBER)
            
        

        #当前不是跟随相位状态 
        if self.config.ALGO_STATUS is AlgorithmStatus.PHASE:
            curr_master_action = env_state["currentPhase"]
            self.pre_master_phase = curr_master_action
            master_phase = self.config.CURRENT_PLAN_STAGE_PHASE[int(self.pre_master_phase)]
            follow_phases = self.config.MASTER_FOLLOW_PHASE_DICT[master_phase]
            #有跟随相位
            if follow_phases: 
                #从PHASES_LIST取到当前相位的下一个相位             
                phase_action = self.config.CURRENT_PLAN_STAGE_PHASE[int(curr_master_action)]
                phase_list_index = self.config.PHASES_LIST.index(phase_action)
                # 有跟随相位就执行跟随相位，跟随相位是在PHASES_LIST紧挨着master的相位
                next_phase = self.config.PHASES_LIST[phase_list_index + 1]
                action = self.config.CURRENT_PLAN_PHASE_TO_NUMBER[next_phase]
                self.config.PRE_FOLLOW_PHASE = action
            else:
                action = return_next_action_index(self.config.PHASES, self.config.CURRENT_PLAN_STAGE_PHASE, self.config.CURRENT_PLAN_PHASE_TO_NUMBER, curr_master_action,\
                                            alg_action_signal_index, self.config.LAYERS_ORDER_FLAG)
            
        elif self.config.ALGO_STATUS is AlgorithmStatus.FOLLOW_PHASE:
            curr_follow_phase = env_state["currentPhase"]
            self.pre_master_phase = self.config.ACTION_HISTORY[-1]
            master_phase = self.config.CURRENT_PLAN_STAGE_PHASE[int(self.pre_master_phase)]

            follow_phases = self.config.MASTER_FOLLOW_PHASE_DICT[master_phase]
            #如果当前跟随相位不是主人相位的最后一个跟随相位      
            if self.config.PHASES_LIST.index(self.config.CURRENT_PLAN_STAGE_PHASE[int(curr_follow_phase)]) != self.config.PHASES_LIST.index(master_phase) + len(follow_phases):
                need_next_follow = self.is_continue(state, 5, self.config.CURRENT_PLAN_STAGE_PHASE[int(curr_follow_phase)])
                if need_next_follow:
                    action = curr_follow_phase + 1
                    self.config.PRE_FOLLOW_PHASE  = action
                else:
                    # 若父相位和算法返回父相位不同，则返回算法父相位
                    if alg_action_signal_index  != self.pre_master_phase:
                        action = return_next_action_index(self.config.PHASES, self.config.CURRENT_PLAN_STAGE_PHASE, self.config.CURRENT_PLAN_PHASE_TO_NUMBER, self.pre_master_phase,\
                                            alg_action_signal_index, self.config.LAYERS_ORDER_FLAG)
                        self.next_master_phase = action
                    else:
                        action = curr_follow_phase
                        self.config.PRE_FOLLOW_PHASE = action
            else:
                # 已经是最后一个跟随相位了，如果算法不等于跟随相位的主人相位
                if alg_action_signal_index  != self.pre_master_phase:
                    action = return_next_action_index(self.config.PHASES, self.config.CURRENT_PLAN_STAGE_PHASE, self.config.CURRENT_PLAN_PHASE_TO_NUMBER, self.pre_master_phase,\
                                            alg_action_signal_index, self.config.LAYERS_ORDER_FLAG)
                    self.next_master_phase = action
                # 继续当前相位
                else:
                    action = env_state["currentPhase"]
                    self.config.PRE_FOLLOW_PHASE = action
                    
        if self.config.CURRENT_PLAN_STAGE_PHASE[int(action)] in self.config.MASTER_PHASES:
            self.config.ACTION_HISTORY.append(action)
        else:
            master = self.config.FOLLOW_MASTER_PHASE_DICT[self.config.CURRENT_PLAN_STAGE_PHASE[int(action)]]
            master_action = self.config.CURRENT_PLAN_PHASE_TO_NUMBER[master]
            self.config.ACTION_HISTORY.append(master_action)      
        return action

    def is_continue(self, vehicle_map, threshold, phase):
        """
        功能:判断当前相位是否需要继续执行（如等待车辆数是否超过阈值）。
        输入:
            vehicle_map: 车辆信息字典
            threshold: 阈值
            phase: 当前相位
        输出:
            是否继续(True/False)
        """
        phase = phase.replace('follow_','')
        waiting_vehicles = 0
        vehicle_map = vehicle_map[self.config.INTERSECTION]
        for direction in phase.split('_'):
            waiting_vehicles += vehicle_map['waiting_vehicle'][direction]
        if waiting_vehicles > threshold:
            return True
        return False 
   