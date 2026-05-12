from algorithms.saferules.rules.pre_rules.imports import *
from algorithms.utils.replay_buffer import ReplayBuffer


class CheckIsOverflowRule(BaseRule):
    def __init__(self, algo=None):
        super().__init__(algo)
        self.overflow_road_to_phase = get_overflow_road_to_phase(self.algo.config.OVERFLOW_PHASE_TO_ROAD)
        self.overflow_times_by_road = {}
        self.reset_overflow_times(self.overflow_times_by_road)
        
        
    def inter_of_mul_road_phases(self, overflow_road_to_phase, roads):
        # 提取所有路口对应的相位列表并转换为集合
        phase_sets = []
        for road in roads:
            phases = set(overflow_road_to_phase.get(road, []))
            phase_sets.append(phases)
        
        # 计算所有集合的交集
        if phase_sets:
            intersection = set.intersection(*phase_sets)
        else:
            intersection = set()
        
        return list(intersection)

    def reset_overflow_times(self, overflow_times):
        directions = ['S','W','N','E']
        for d in directions:
            overflow_times[d] = 0
    
    def count_zero_speed(self, vehicles):
        count = 0
        for vehicle in vehicles:
            if vehicle['speed'][0] == 0.0 and abs(vehicle['center'][0]) <= self.algo.config.MIN_OVERFLOW_DIS_SPEED[1]:
                count += 1
        return count
    def count_overflow_vehicle(self, vehicles, distance, speed):
        count = 0
        for vehicle in vehicles:
            if abs(float(vehicle['speed'][0])) <= speed and abs(vehicle['center'][0]) <= distance:
                count += 1
        return count

    def get_road_overflow(self, state):
        overflow_road = []
        for road, lanes in self.algo.config.ROAD_TO_LANE[self.algo.config.INTERSECTION+'_out'].items():
            is_road_overflow = False
            overflow_lane_count = 0
            #overflw_vehicle
            for lane in lanes:
                vehicles = state[self.algo.config.INTERSECTION]['vehicle_lane_to_phase'][lane]
                #检测溢出第一条件，速度为0的车辆数达到一定数
                if self.count_zero_speed(vehicles) >= self.algo.config.MIN_OVERFLOW_DIS_SPEED[0]:
                    is_road_overflow = True
                    break
                #检测溢出第二条件，速度和距离达到条件的车辆数大于一定量，该lane为溢出lane，
                # 溢出lane的总数大于lane总数的2/3，该出口方向为溢出
                if self.count_overflow_vehicle(vehicles, self.algo.config.MIN_OVERFLOW_DIS_SPEED[2], self.algo.config.MIN_OVERFLOW_DIS_SPEED[3]) > self.algo.config.ROAD_TO_OVERFLOW_VEHICLE_COUNT[road]:
                    overflow_lane_count += 1
                    if overflow_lane_count >= math.ceil(len(lanes)/3*2):
                        is_road_overflow = True
                        break
                
                # 溢出放宽条件，三条件保证采集设备不准确仍能判定溢出
                if self.count_overflow_vehicle(vehicles, self.algo.config.MIN_OVERFLOW_DIS_SPEED_REALX[0], self.algo.config.MIN_OVERFLOW_DIS_SPEED_REALX[1]) >= self.algo.config.OVERFLOW_VEHICLE_COUNT:
                    is_road_overflow = True
                    break

            if is_road_overflow:
                self.overflow_times_by_road[road] += 1
            else:
                self.overflow_times_by_road[road] = 0
            if is_road_overflow and self.overflow_times_by_road[road] >= self.algo.config.OVERFLOW_TIMES:
                overflow_road.append(road)
        return '_'.join(overflow_road)

    def get_phase_to_lane_count(self, phases):
        count = 0
        for p in phases:
            for k, v in self.algo.config.LANE_TO_PHASE.items():
                if k[-1] == 'L':
                    break
                if p in v.split('_'):
                    count += 1
        return count

    def is_continue_overflow_phase(self, state, overflow_phase):
        # 当前溢出相位车辆数是否大于其他方向等待车辆
        max_waiting_vehicle = 0
        cur_waiting_vehicle = self.get_phase_waiting_vehicles(state, overflow_phase)
        #cur_father_phase = self.algo.config.PHASES[self.get_father_phase(overflow_phase) - 1]
        directions = overflow_phase.split('_')
        # 溢出相位车辆权重，需要和其他方向车道数保持平衡
        alpha = 0
        for father_phase in self.algo.config.PHASES:
            father_directions = father_phase.split('_')
            inter_phase = list(set(father_directions) - set(directions))
            if len(inter_phase) == 0:
                continue
            alpha += self.get_phase_to_lane_count(inter_phase)
            inter_phase = '_'.join(inter_phase) 
            max_waiting_vehicle += self.get_phase_waiting_vehicles(state, inter_phase)
        return cur_waiting_vehicle * 2.5 >= max_waiting_vehicle
    #获取相位行驶车辆
    def get_phase_running_vehicles(self, state, phase):
        vehicle_count = 0
        for p in phase.split('_'):
            vehicle_count += state[self.algo.config.INTERSECTION]['running_vehicle'][p]
        return vehicle_count 
        
    #获取相位等待车辆数
    def get_phase_waiting_vehicles(self, state, phase):
        vehicle_count = 0
        for p in phase.split('_'):
            vehicle_count += state[self.algo.config.INTERSECTION]['waiting_vehicle'][p]
        return vehicle_count
    #判断相位是否是溢出相位
    def is_overflow_phase(self, action):
        if self.algo.config.CURRENT_PLAN_STAGE_PHASE[int(action)] in self.algo.config.OVERFLOW_PHASE:
            return True
        else:
            return False

    #获取溢出相位父相位,如果不是溢出相位返回0
    def get_father_phase(self, phase):
        father_action = -1
        for father, child in self.algo.config.PHASE_TO_OVERFLOW_PHASE.items():
            if phase in child:
                father_action = self.algo.config.CURRENT_PLAN_PHASE_TO_NUMBER[father]
                break
        return father_action


    def is_excute_hostile_phase(self, pre_action, after_action):
        pre = self.is_overflow_phase(pre_action)
        after = self.is_overflow_phase(after_action)
        if pre and after:
            # 判断父相位是否相同，若相同则必须切父相位的敌对相位
            if self.get_father_phase(self.algo.config.CURRENT_PLAN_STAGE_PHASE[int(after_action)]) == self.get_father_phase(self.algo.config.CURRENT_PLAN_PHASE_TO_NUMBER[pre_action]):
                return True
            else:
                return False

        else:
            return False

    def get_max_wait_phase(self, phases, state):
        phase_vehicles = []
        for p in phases:
            phase_vehicles.append(self.get_phase_waiting_vehicles(state, p))
        max_value = max(phase_vehicles)
        indices_of_max = [index for index, value in enumerate(phase_vehicles) if value == max_value]
        overflow_phase = max(phases[index] for index in indices_of_max)
        return overflow_phase
    
    
    def execute(self, state: Dict, env_state: Dict) -> RuleResult:
        try:
            if self.algo.config.CITYFLOW_TEST or self.algo.config.OVERFLOW_PHASE_TO_ROAD == {} \
                or self.algo.config.SIGNAL_CONTROLLER_STATUS is SignalControllerStatus.FOLLOW_PHASE \
                    or self.algo.config.ALGO_STATUS is AlgorithmStatus.FOLLOW_PHASE:
                return RuleResult.SUCCESS

            self.algo.config.ADVANCED_TAKE_COUNT += 1
            #当前相位和上一个相位是否是父子关系，如果是则phaseTime叠加
            action = env_state['currentPhase']
            cur_phase = self.algo.config.CURRENT_PLAN_STAGE_PHASE[int(action)]
            phase_keep = env_state['phaseTime']
            if self.algo.replay_buffer.size > 2:
                pre_action = self.algo.replay_buffer.buffer[-2][2]['currentPhase']
                pre_phase = self.algo.config.CURRENT_PLAN_STAGE_PHASE[int(pre_action)]
                #父子相位的phase_time需要加在一起
                if action != pre_action and is_contains_relation(cur_phase ,pre_phase):
                    phase_keep = phase_keep + self.algo.replay_buffer.buffer[-2][2]['phaseTime']
                           
            if self.algo.config.SIGNAL_CONTROLLER_STATUS is SignalControllerStatus.OVERFLOW_PHASE:
                if phase_keep < self.algo.config.OVERFLOW_MIN_GREEN_TIME:
                    self.algo.config.AlgorithmStatus = AlgorithmStatus.OVERFLOW_PHASE
                    RuleResult.DATA = action
                    return RuleResult.DATA
            #给与matser相位单独最短时间，防止车祸
            if self.algo.config.SIGNAL_CONTROLLER_STATUS is SignalControllerStatus.PHASE:
                if phase_keep < self.algo.config.OVERFLOW_RULE_MASTER_TIME:
                    #self.algo.config.AlgorithmStatus = AlgorithmStatus.PHASE                
                    return RuleResult.SUCCESS
            if int(self.algo.config.SIGNAL_IN_CONTROL) == 0:
                pass
            else:
                #保证信号机和溢出相位同步
                prev_action = -1 
                if len(self.algo.config.OVERFLOW_HISTORY) > 0:
                    prev_action = self.algo.config.OVERFLOW_HISTORY[-1]
                if prev_action != -1 and prev_action != action:
                    RuleResult.DATA = prev_action 
                    return RuleResult.DATA 
                elif prev_action != -1 and prev_action == action:
                    self.algo.config.OVERFLOW_HISTORY.clear()

            
            # 1.判断哪个路口溢出
            overflow_roads = self.get_road_overflow(state)
            if overflow_roads == '':
                # 1-2,1-3切
                # 北口堵，切了北向南，北口恢复，则切东西
                if self.algo.config.SIGNAL_CONTROLLER_STATUS is SignalControllerStatus.OVERFLOW_PHASE:
                    overflow_phase = self.algo.config.CURRENT_PLAN_STAGE_PHASE[int(action)]
                    if self.is_continue_overflow_phase(state, overflow_phase):
                        phase = action
                    # 这里本应该选择waiting最大的相位，但是由于可能选到溢出相位父相位，phase_keep又清零，
                    # 会产生频繁的切溢出和其父相位，需要中间件配合，累加上去
                    else:
                        max_phase = self.get_max_wait_phase(self.algo.config.PHASES, state)
                        phase = self.algo.config.CURRENT_PLAN_STAGE_PHASE(max_phase)
                    if not self.is_overflow_phase(phase):
                        self.algo.config.AlgorithmStatus = AlgorithmStatus.PHASE    
                    RuleResult.DATA = phase
                    return RuleResult.DATA
                return RuleResult.SUCCESS

            # 2.获取溢出相位
            overflow_phase = None
            overflow_phases = self.inter_of_mul_road_phases(self.overflow_road_to_phase, overflow_roads.split('_'))
            if len(overflow_phases) == 0:
                self.algo.config.LOGGER(5,"Advanced_alg", f"Exception occurred: no overflow phases to choose, overflow road is {overflow_roads}") 
                self.algo.log_collector.log(logging.DEBUG, f"Advanced_alg, Exception occurred: no overflow phases to choose, overflow road is {overflow_roads}") 
                return None

            # 检测当前相位所对应的溢出路口，且路口的溢出时间大于160s，无法决策
            if max(self.overflow_times_by_road.values()) > self.algo.config.MAX_KEEP_TIME[self.algo.config.CURRENT_PLAN_STAGE_PHASE[action]] * 2:
                self.algo.config.LOGGER(0,"Advanced_alg",f"Exception occurred: check_is_overflow is great than maxkeeptime is {self.overflow_times_by_road}") 
                self.algo.log_collector.log(logging.DEBUG, f"Advanced_alg, Exception occurred: check_is_overflow is great than maxkeeptime is {self.overflow_times_by_road}") 
                return None

            # 若北口堵，放了东西最短绿，又开始放北口，北口导致南口堵，怎么办？
            # 若南北堵，又检测发现北口堵怎么办?
            if max(self.overflow_times_by_road.values()) >= 3:
                # 判断可用的相位中是否有当前相位的溢出相位   
                is_overflow_phase_in_action = False
                if self.algo.config.CURRENT_PLAN_STAGE_PHASE[int(action)] in self.algo.config.OVERFLOW_PHASE:
                    is_overflow_phase_in_action = True
                    overflow_phase = self.algo.config.CURRENT_PLAN_STAGE_PHASE[int(action)]
                else:
                    avaliable_overflow_phases = []
                    
                    for p in overflow_phases:
                        if self.get_father_phase(p) == action:
                            is_overflow_phase_in_action = True
                            avaliable_overflow_phases.append(p)
                    if len(avaliable_overflow_phases) != 0:
                        overflow_phase = self.get_max_wait_phase(avaliable_overflow_phases, state)

                # 若有，且溢出相位等待车辆大于车道数量的车辆，
                # 则根据车流量放一段时间，小于一定阈值  -- 可能存在北口一直有车的情况
                # 此溢出相位需满足最大绿的限制，上一个相位是不是溢出相位，需要加上
                #当前相位是溢出相位或当前相位有溢出相位，且继续溢出相位
                if is_overflow_phase_in_action and self.is_continue_overflow_phase(state, overflow_phase): 
                    self.algo.config.OVERFLOW_MIN_GREEN_TIME = 6
                    overflow_phase_index = self.algo.config.CURRENT_PLAN_PHASE_TO_NUMBER[overflow_phase]
           
                # 若没有，放可用相位车辆最大的相位，当前相位需要满足最                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                   短绿
                # 北口持续溢出，切东西，东西放了一段时间后，等待车辆下降
                # 选择北向南，保证最短绿
                else:
                    
                    if self.algo.config.SIGNAL_CONTROLLER_STATUS is SignalControllerStatus.PHASE:
                        if phase_keep < self.algo.config.MIN_GREEN_TIME[self.algo.config.PHASES[action-1]]:
                            self.algo.config.AlgorithmStatus = AlgorithmStatus.PHASE
                            RuleResult.DATA = action
                            return RuleResult.DATA

                    overflow_phase = self.get_max_wait_phase(overflow_phases, state)
                    overflow_phase_index = self.algo.config.CURRENT_PLAN_PHASE_TO_NUMBER[overflow_phase]

                    # 若可用相位是溢出相位，则保证行人最短绿
                    if overflow_phase in self.algo.config.OVERFLOW_PHASE:
                        overflow_min_green_time = 20 
                        # 获取父相位的最短绿
                        for k,v in self.algo.config.PHASE_TO_OVERFLOW_PHASE.items():
                            if overflow_phase in v:
                                overflow_min_green_time = self.algo.config.MIN_GREEN_TIME[k]
                        self.algo.config.OVERFLOW_MIN_GREEN_TIME = overflow_min_green_time
                    
                if self.algo.config.DEBUG:
                    self.algo.config.LOGGER(5,"Advanced_alg", f"DEBUG: check_is_overflow overflow times {self.overflow_times_by_road},\
                                                                        overflow roads {overflow_roads}, overflow avaliable phases {overflow_phases}, overflow phase {overflow_phase}") 
                    self.algo.log_collector.log(logging.DEBUG, f"Advanced_alg, DEBUG: check_is_overflow overflow times {self.overflow_times_by_road},\
                                                                        overflow roads {overflow_roads}, overflow avaliable phases {overflow_phases}, overflow phase {overflow_phase}") 
                                                                      
                # 考虑司机驾驶习惯，先切当前相位的其他相位，--- 要保证saferules的运行逻辑不能有bug,考虑最短绿，过渡 
                # 都是溢出相位比如北口堵，切北向南， 南口堵，北口不溢出， 不能切南向，考虑到东西可能有司机驾驶习惯问题   
                if self.is_excute_hostile_phase(action, overflow_phase_index) and action != overflow_phase_index:  
                    phase = self._cycle_control(self.get_father_phase(self.algo.config.CURRENT_PLAN_PHASE_TO_NUMBER[action]))
                    self.algo.config.OVERFLOW_HISTORY.append(phase)
                    self.algo.config.AlgorithmStatus = AlgorithmStatus.PHASE
                    RuleResult.DATA = phase
                    return RuleResult.DATA
                else:
                    RuleResult.DATA = overflow_phase_index
                    # action_history保持所有父相位
                    if self.algo.config.CURRENT_PLAN_STAGE_PHASE[int(overflow_phase_index)] in  self.algo.config.PHASES:
                        self.algo.config.ACTION_HISTORY.append(overflow_phase_index)
                    else:
                        self.algo.config.ACTION_HISTORY.append(self.get_father_phase(self.algo.config.CURRENT_PLAN_STAGE_PHASE[int(overflow_phase_index)]))
                    # overflow_action_his保持所有溢出相位，包括父相位
                    if action != overflow_phase_index:
                        self.algo.config.OVERFLOW_HISTORY.append(overflow_phase_index)
                    self.algo.config.AlgorithmStatus = AlgorithmStatus.OVERFLOW_PHASE
                    return RuleResult.DATA
            else:
                return RuleResult.SUCCESS

        except:
            self.algo.config.LOGGER(0,"Advanced_alg",f"Exception occurred: check_is_overflow error message is {traceback.format_exc()}") 
            self.algo.log_collector.log(logging.ERROR, f"Advanced_alg, Exception occurred: check_is_overflow error message is {traceback.format_exc()}") 
            return RuleResult.FAILURE