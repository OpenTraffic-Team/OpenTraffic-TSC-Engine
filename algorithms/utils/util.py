import numpy as np
import hashlib
import time
#分析整理路口数据，得到形如ANLX_WXL_in[W]:  
def get_road_by_lane(cur_inter_id, lanes):
    road_to_lane = {cur_inter_id + '_in':{}, cur_inter_id + '_out':{}}
    direction = ["W","E","S","N"]
    for d in direction:
        road_to_lane[cur_inter_id + '_in'][d] = []
        road_to_lane[cur_inter_id + '_out'][d] = []

    for lane in lanes:
        for d in direction:
            if d not in lane.split('_'):
                continue
            if lane[-1] != 'L':
                road_to_lane[cur_inter_id + '_in'][d].append(lane)
            else:
                road_to_lane[cur_inter_id + '_out'][d].append(lane)
    return road_to_lane


def get_overflow_road_to_phase(overflow_phase_to_road):
    overflow_road_to_phase = {}

    # 遍历原始配置字典中的每一个相位和对应的溢出路口列表
    for phase, roads in overflow_phase_to_road.items():
        # 遍历每个相位对应的溢出路口
        for road in roads:
            # 拆分复合的溢出路口（如 'S_W'），将其拆分成单独的路口
            individual_roads = road.split('_')
            for individual_road in individual_roads:
                # 如果单独的溢出路口在新字典中已存在，追加当前相位到对应列表中
                if individual_road in overflow_road_to_phase:
                    if phase not in overflow_road_to_phase[individual_road]:
                        overflow_road_to_phase[individual_road].append(phase)
                # 如果单独的溢出路口在新字典中不存在，创建一个新的列表并添加当前相位
                else:
                    overflow_road_to_phase[individual_road] = [phase]
    return overflow_road_to_phase


def get_phase_to_overflow_phase(overflow_phase, phases):
    phase_to_overflow_phase = {}
    for phase in phases:
        phase_to_overflow_phase[phase] = []

    for overflow_phase in overflow_phase:
        for phase in phases:
            phase_direc = phase.split('_')
            is_contain = True
            for overflow_phase_direc in overflow_phase.split('_'):
                if overflow_phase_direc not in phase_direc:
                    is_contain = False
            if is_contain:
                phase_to_overflow_phase[phase].append(overflow_phase)
    return phase_to_overflow_phase

def is_contains_relation(str1, str2):
    if str1 in str2 or str2 in str1:
        return True
    else:
        return False

def is_subset(a, b):  #a相位拆分成movement后是不是b相位拆分成movement的子集
    a_s = set(a.split('_'))
    b_s = set(b.split('_'))    
    return a_s.issubset(b_s)

#将action list表示的phase转为其phase下标
def actionlist_to_index(action_lis:list,  bind_phases:list):
    for i in range(len(action_lis)):
        if i == len(action_lis) - 1:
            return bind_phases[action_lis[i]]
        bind_phases = bind_phases[action_lis[i]]
        
#与上述方法相反
def index_to_actionlist(index:int, bind_phases:list, action_list:list):

    if type(bind_phases[0]) == int:
        action_list.append(index)
        return
    sum_t = 0
    for i in range(len(bind_phases)):
        
        bind_phases_t = bind_phases[i]
        if len(bind_phases_t) + sum_t <= index:
            sum_t += len(bind_phases[i])
            continue
        action_list.append(i)
        index_to_actionlist(index - sum_t, bind_phases[i], action_list)
        return 

#dfs数一下某一个节点作为根节点，其树的叶子节点，赋值给pre_phases
def count_add_phase(bind_phases,pre_phases,index,layers_flag):
    if type(bind_phases) == int:
        pre_phases.append(bind_phases)
        return
    if layers_flag[index] == True:
        for i in range(len(bind_phases)):
            count_add_phase(bind_phases[i],pre_phases,index+1,layers_flag)

#执行某一相位前需要执行的相位都有哪些
def need_pre_to_exe_for_remain(bind_phases,remain_action_list,layers_flag):
    need_pre_to_exe = []
    for i in range(len(remain_action_list)):
        if layers_flag[i] == True:
            for j in range(remain_action_list[i]):
                pre_phases = []
                count_add_phase(bind_phases[j],pre_phases,i,layers_flag)
                need_pre_to_exe.append(pre_phases)
        else:
            bind_phases = bind_phases[remain_action_list[i]]
            
    return list(np.array(need_pre_to_exe).flatten())

#根据master相位拿到相位编号
def master_index_2_signal_index(master_index, master_phases, all_roadnet_phases):
    master_phase = master_phases[master_index]
    signal_index = all_roadnet_phases[master_phase]
    return signal_index

#与上述相反
def signal_index_2_master_index(signal_index, master_phases, all_roadnet_phases):
    signal_phase = all_roadnet_phases[signal_index]
    master_index = master_phases.index(signal_phase)
    return master_index

#TODO 目前方法仅针对于无捆绑和二相位捆绑 通用的对其内部实现即可
# curr_p, tar_p都是signal_index
def return_next_action_index(master_phases, all_roadnet_phases_to_phases, all_roadnet_phases_to_number, curr_p, tar_p, layers_flag):
    #先都转为master_index
    m_cur_p = signal_index_2_master_index(curr_p, master_phases, all_roadnet_phases_to_phases)
    m_tar_p = signal_index_2_master_index(tar_p, master_phases, all_roadnet_phases_to_phases)
    if layers_flag[-1] == True:
        if m_cur_p != m_tar_p:
            next_action = (m_cur_p + 1) % len(master_phases)
        else:
            next_action = m_cur_p
    else:
        next_action = m_tar_p
    #再转为ac index
    next_action_index = master_index_2_signal_index(next_action, master_phases, all_roadnet_phases_to_number)
    return next_action_index

def is_equal(object_one, object_two):
    """ 比较两对象值是否相等
    Args:
        object_one: 比较对象
    Returns:
        相等返回True
    """
    #比较内存地址是否相等
    if id(object_one) == id(object_two):
        return True
    hash_a = hashlib.md5(str(object_one).encode()).hexdigest()
    hash_b = hashlib.md5(str(object_two).encode()).hexdigest()
    return hash_a == hash_b

def sort_phases(phases, stage_phase):
    '''
    将列表按照字典映射排序
        Args:
        phases: 被排序的相位列表
        stage_phase: 相位与相位编码的映射
    Returns: 
        sorted_phases 排好序的列表
    '''
    # 将 stagePhase 的 key 转换为整数并排序
    sorted_keys = sorted(stage_phase.keys(), key=int)
    
    # 根据排序后的 key 提取对应的 phase
    sorted_phases = []
    for k in sorted_keys:
        phase = stage_phase[k]
        if phase in phases:
            sorted_phases.append(phase)
    
    return sorted_phases


def update_phases_by_stage(phases, stagePhase):
    """映射envstate传过来的相位列表，根据stagephase修改成字符串形式的相位数组，并且根据stagephase编号从小到大排序      
    Args:
        stagePhase: 编号对应相位字符串的字典
        phases: 当前可用的相位编号数组
    Returns:
        phaseslist：当前可用相位字符串数组
        current_plan_stagephases：当前可用相位的相位编号与字符串的字典
        current_plan_phases_number：当前可用相位的相位字符串与编号的反转字典
        """
    # 创建一个空字典来存放有效的相位编号及对应的阶段
    valid_phases = {}
    
    # 遍历phases，筛选有效的编号和非空的阶段
    for phase in phases:
        phase_str = str(phase)
        if phase_str in stagePhase and stagePhase[phase_str]:
            valid_phases[phase] = stagePhase[phase_str]

    # 根据字符串值进行排序
    value_order = [stagePhase[k] for k in stagePhase if int(k) in phases]

    # 按照 value_order 的顺序排列 valid_phases
    sorted_phases = sorted(valid_phases.items(), key=lambda x: value_order.index(x[1]))

    # 生成phaseslist，包含按编号排序的阶段值
    phaseslist = []
    for _, phase_value in sorted_phases:
        phaseslist.append(phase_value)

    # 生成current_plan_stagephases，按编号从小到大排序的映射字典
    current_plan_stagephases = dict(sorted_phases)
    #反转字典
    current_plan_phases_number = {v: k for k, v in current_plan_stagephases.items()}
    

    return phaseslist, current_plan_stagephases, current_plan_phases_number

# 定义一个装饰器来计算函数执行时间
def timing_decorator(func):
    def wrapper(self, *args, **kwargs):
        start_time = time.time()  # 记录开始时间
        result = func(self, *args, **kwargs)  # 执行原函数
        end_time = time.time()  # 记录结束时间
        print(f"Function {func.__name__} executed in {end_time - start_time:.4f} seconds")
        return result
    return wrapper