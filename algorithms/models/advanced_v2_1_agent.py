import torch
import torch.nn as nn
import numpy as np
from algorithms.models import *
from algorithms.utils.util import index_to_actionlist
from algorithms_sdk.mq_utils.redis.redis_stream import RedisStreamReader
class Network(nn.Module):
    def __init__(self,len_feature=24,out_dim=2):
        """
        功能: 初始化神经网络结构,包含MLP和全连接层。
        输入:
            len_feature: 特征长度,默认为24
            out_dim: 输出维度,默认为2
        输出:
            无
        """
        super(Network,self).__init__()
        self.MLP = MLP(len_feature)
        self.fc = nn.Linear(32,out_dim)
        
    def forward(self,feats):
        """
        功能: 前向传播,输出网络预测结果。
        输入:
            feats: 输入特征张量
        输出:
            网络输出张量
        """
        feats = feats.to(torch.float32)
        out  = self.MLP(feats)
        out = self.fc(out)
        return out


class MLP(nn.Module):
    def __init__(self,dim):
        """
        功能: 初始化多层感知机结构。
        输入:
            dim: 输入特征维度
        输出:
            无
        """
        super(MLP,self).__init__()
        self.lay1 = torch.nn.Linear(dim,64)
        self.lay2 = torch.nn.Linear(64,32)
    def forward(self,ins):
        """
        功能: 前向传播,输出MLP处理结果。
        输入:
            ins: 输入特征张量
        输出:
            MLP输出张量
        """
        ins = ins.to(torch.float32)
        h = self.lay1(ins)
        h = nn.ReLU()(h)
        h = self.lay2(h)
        h = nn.ReLU()(h)
        return h

####仅适用于两相位tsc
class AdvancedV2_1(Agent):
    def __init__(self, config, redis_stream=None):
        """
        功能: 初始化AdvancedMLP算法模型,加载模型参数,设置优化器等。
        输入:
            config: 配置对象,包含算法运行所需的参数
        输出:
            无
        """
        super().__init__(config)
        self.config = config
        self.log_collector = LogCollector(enable_print=True)
        self.TSC_model = Network(out_dim=len(self.config.PHASES))
        self.target_network = Network(out_dim=len(self.config.PHASES))
        self.TSC_model.load_state_dict(torch.load(self.config.MODEL_PATH))
        self.target_network.load_state_dict(self.TSC_model.state_dict())
        self.optimizer = torch.optim.Adam(self.TSC_model.parameters(), lr=self.config.LEARNING_RATE)
        self.target_update_count = 0
        self.redis_stream = redis_stream
        self.replay_buffer = ReplayBuffer(self.config.REPLAYBUFFER_CAPACITY, self.config.BATCH_SIZE, config)
        self.config.LOGGER(5, "Advanced_alg",  f"Advanced control version is 2.0.0")
        
    def _sum_q(self,out_q,rl_phases,current_phases):
        """
        功能: 计算每个相位的Q值总和。
        输入:
            out_q: Q值列表
            rl_phases: RL模型训练的相位列表
            current_phases: 当前相位列表
        输出:
            action_q: 每个相位的Q值总和列表
        """
        ### rl_phases = self.config.TRAINED_RL_MODEL_PHASE
        ###  current_phases = self.config.PHASES
        cps = []
        for i in range(len(current_phases)):
            cp_t=[]
            for j in range(len(rl_phases)):
                if rl_phases[j] in current_phases[i]:
                    cp_t.append(j)
            cps.append(cp_t)
        action_q = []
        for cp in cps:
            q_t = 0.0
            for i in cp:
                q_t = q_t + out_q[i]
            action_q.append(q_t)
        return action_q
    
    def take_one_layer_action(self, curr_action, combine_phases):
        """
        功能: 针对单层相位,选择压力最大的相位。
        输入:
            curr_action: 当前相位索引
            combine_phases: 当前层可选相位组合
        输出:
            action: 选中的相位索引
        """
        q_values =self.TSC_model(self.one_state)[0].detach().cpu().numpy()
        action_q = self._sum_q(q_values,self.config.TRAINED_RL_MODEL_PHASE,combine_phases)
        action = action_q.index(max(action_q))
        return action
    
    #对每一层进行相位选择
    #new_layers_action_result要返回的action list， branch_flag该层选择是否已经和current phase不在一颗子树上了
    def layers_action(self, bind_phases, old_action_list, new_layers_action_result, branch_flag, layers_flag):
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
        list_t = np.array(bind_phases)
        #获得该层的相位列表，在其中进行选择
        for i in list_t:
            a = i.flatten()
            l = np.array(self.config.PHASES)[a]
            t = "_".join(l)
            combine_phases.append(t)

        if branch_flag == True:
            current_phase = -1
        else:
            current_phase = old_action_list[0]
        action = self.take_one_layer_action(current_phase,combine_phases)
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
 
    def algorithm_control(self, curr_action,state, env_state):
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
        state_lane = ["WN","WE","WS","ES","EW","EN","NE","NS","NW","SW","SN","SE"]
        rl_state = {"running_vehicle":[], "waiting_vehicle":[]}
        for lane in state_lane:
            if lane in state['running_vehicle'].keys():
                rl_state["running_vehicle"].append(state["running_vehicle"][lane])
                rl_state["waiting_vehicle"].append(state["waiting_vehicle"][lane])
            else:
                rl_state["running_vehicle"].append(0)
                rl_state["waiting_vehicle"].append(0)
        run_vehicle = rl_state["running_vehicle"]
        wait_vehicle = rl_state["waiting_vehicle"]

        self.one_state = []
        self.one_state.extend(run_vehicle)
        self.one_state.extend(wait_vehicle)
        self.one_state = torch.tensor(self.one_state)
        self.one_state = self.one_state.reshape(-1, self.one_state.shape[0])
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
        #if self.config.CITYFLOW_TEST == 0:
        action = self.take_follow_action(state, env_state)
        # else:
        #     action = self.take_follow_action_cityflow(state, env_state)
        self.set_cur_input_and_output(action, state, env_state)
        if self.config.DEBUG:
            msg = f"DEBUG: advanced_v2_1 env_state is {env_state}, algorithm output phase is {self.cur_action}, \
                                                running vehicle is {self.cur_running_vehicle_roads}, waiting vehicle is {self.cur_waiting_vehicle_roads} \
                                                phase_history is {self.config.ACTION_HISTORY}"
            self.config.LOGGER(5,"Advanced_alg", msg)
            self.log_collector.log(logging.INFO, f'Advanced_alg, {msg}' )
        return action
    def get_sample(self):
        """
        功能: 从Redis中获取样本数据。
        输入:
            无
        输出:
            无
        """
        datas = self.redis_stream.get_neighbors_data(2, self.config.NEIGHBOUR_INTERSECTION, self.config.BATCH_SIZE)
        
        
        
    def train(self):
        """
        功能: 训练模型。
        输入:
            无
        输出:
            无
        """
        for inter in self.config.NEIGHBOUR_INTERSECTION:
            if self.redis_stream.get_stream_length(2, "lane_to_phase:" + inter) < self.config.BATCH_SIZE:
                return
        # if len(self.replay_buffer) < self.config.BATCH_SIZE:
        #     return
        
        for _ in range(self.config.EPOCH):
            # 从经验回放缓冲区获取训练数据
            states, actions, rewards, next_states = self.replay_buffer.sample()
            
            # 转换为tensor
            states = torch.FloatTensor(states)
            next_states = torch.FloatTensor(next_states)
            actions = torch.LongTensor(actions)
            rewards = torch.FloatTensor(rewards)
            
            # 计算当前Q值
            current_q_values = self.TSC_model(states)
            current_q_values = current_q_values.gather(1, actions.unsqueeze(1))
            
            # 计算目标Q值
            with torch.no_grad():
                next_q_values = self.target_network(next_states)
                max_next_q_values = next_q_values.max(1)[0]
                target_q_values = rewards + self.config.GAMMA * max_next_q_values
            
            # 计算损失
            loss = nn.MSELoss()(current_q_values.squeeze(), target_q_values)
            
            # 反向传播和优化
            self.optimizer.zero_grad()
            loss.backward()
            self.optimizer.step()

            # 记录训练信息
            if self.config.DEBUG:
                msg = f"Training loss: {loss.item()}"
                self.config.LOGGER(5, "Advanced_alg", msg)
                self.log_collector.log(logging.INFO, f'Advanced_alg, {msg}')

        if self.target_update_count % self.config.TARGET_UPDATE_FREQ == 0:
            self.target_network.load_state_dict(self.TSC_model.state_dict())
        self.target_update_count += 1

        
   
AdvancedV2 = AdvancedV2_1   # backward-compatible alias
AdvancedMLP = AdvancedV2_1  # backward-compatible alias
