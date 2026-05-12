import numpy as np
from algorithms.models import *
from algorithms.models.fuzzylight_network import ActorNet, CriticNet
from algorithms.utils.util import actionlist_to_index, master_index_2_signal_index
from algorithms.utils.util import index_to_actionlist
import traceback
import os
from typing import List, Optional
import torch
import torch.nn.functional as F
"""
@File      : advanced_v2_2_agent.py
@Desc      : fuzzylight算法
@Author    : lizhuojun
@Date      : 2025-09-04
"""

class OrnsteinUhlenbeckProcess(object):
    """ Ornstein-Uhlenbeck Noise (original code by @slowbull)
    """
    def __init__(self, mean, std_deviation, theta=0.15, dt=1e-2, x_initial=None):
        self.theta = theta
        self.mean = mean
        self.std_dev = std_deviation
        self.dt = dt
        self.x_initial = x_initial
        self.reset()
        
    def generate(self):
        x = (
            self.x_prev
            + self.theta * (self.mean - self.x_prev) * self.dt
            + self.std_dev * np.sqrt(self.dt) * np.random.normal(size=self.mean.shape)
        )
        self.x_prev = x
        return x

    def reset(self):
        if self.x_initial is not None:
            self.x_prev = self.x_initial
        else:
            self.x_prev = np.zeros_like(self.mean)

class AdvancedV2_2(Agent):
    def __init__(self, config):
        super().__init__(config)
        self.config = config
        self.log_collector = LogCollector(enable_print=True)
        #记录算法预测相位的持续时长
        self.duration = 0 
        #self.fixed_order_lanes = ["W", "E", "N", "S"]
        self.num_lane = len(self.config.LANE_TO_PHASE)
        self.max_lane = len(self.config.LANE_TO_PHASE)
        #self.index_to_phase = {}
        #下面俩个是Fuzzylight预测所需的输入信息
        self.lane_queue_length = []
        self.num_in_deg = []
        self.phase_map, self.index_to_phase = self.get_phase_map()
        #predict预测所需参数
        self.low = 1 #最短预测持续时长
        self.high = 40 #最长预测持续时长
        self.std_dev = 2
        self.ou_noise = OrnsteinUhlenbeckProcess(mean=np.zeros(1), std_deviation=float(self.std_dev) * np.ones(1))
        # training用到的参数
        self.Xs, self.Y = None, None
        self.memory = self.build_memory()
        self.epochs = 30
        self.batch_size = 64
        self.tau = 0.1
        self.critic_lr = 2e-3
        self.actor_lr = 1e-5
        # self.critic_optimizer = Adam(self.critic_lr)
        # self.actor_optimizer = Adam(self.actor_lr)
        #先设为None，在build_network中初始化
        self.critic_optimizer = None
        self.actor_optimizer = None
        self.discount_factor = 0.8
        if torch.cuda.is_available():
            self.device = torch.device("cuda")
        else:
            self.device = torch.device("cpu")
        # Build model layers and optimizers/targets
        self._build_network()
        self._build_optimizers()
        self._build_targets()
        self._move_all_modules_to_device()
        self.replay_buffer = ReplayBuffer(self.config.REPLAYBUFFER_CAPACITY, self.config.BATCH_SIZE, config)
        print(self.config.MODEL_PATH)
        if os.path.exists(self.config.MODEL_PATH) and os.listdir(self.config.MODEL_PATH):
            try:
                self.load_network("round_99_inter_0")
                print("load network success")
            except Exception as e:
                print(f"加载预训练模型失败: {e}")
                print("将使用随机初始化的网络继续运行")
        else:
            print("模型路径不存在，将使用随机初始化的网络")
        
        self.config.LOGGER(5, "Advanced_alg",  f"Advanced control version is 3.0.0")



    @staticmethod
    def build_memory():
        return []
    
    # -----------------------------
    # Network definition
    # -----------------------------
    def _build_network(self) -> None:
        # Factor networks into dedicated modules matching TF structure
        self.actor_net = ActorNet(self.max_lane, self.config.PHASE_NUMBER, self.phase_map, high=self.high)
        self.critic_net = CriticNet(self.max_lane, self.config.PHASE_NUMBER, self.phase_map)

    def _build_optimizers(self) -> None:
        self.critic_optimizer = torch.optim.Adam(self.critic_net.parameters(), lr=self.critic_lr)
        self.actor_optimizer = torch.optim.Adam(self.actor_net.parameters(), lr=self.actor_lr)

    def _build_targets(self) -> None:
        # For function-style forward, we do not need module clones; we soft-update parameters directly
        # Create shallow copies of modules for target networks
        import copy
        self.actor_net_t = copy.deepcopy(self.actor_net)
        self.critic_net_t = copy.deepcopy(self.critic_net)
        # Move targets to device
        self._move_targets_to_device()

    def _modules_list(self):
        return [self.actor_net, self.critic_net]

    def _targets_list(self):
        return [self.actor_net_t, self.critic_net_t]

    def _move_all_modules_to_device(self) -> None:
        for m in self._modules_list():
            m.to(self.device)

    def _move_targets_to_device(self) -> None:
        for m in self._targets_list():
            m.to(self.device)

    # -----------------------------
    # Embedding utilities (no training logic yet)
    # -----------------------------
    def _actor_forward(self, ins0: torch.Tensor, ins1: torch.Tensor) -> torch.Tensor:
        return self.actor_net(ins0, ins1)

    def _critic_forward(self, ins0: torch.Tensor, ins1: torch.Tensor, action_input: torch.Tensor) -> torch.Tensor:
        return self.critic_net(ins0, ins1, action_input)

    # Target forwards use target parameters
    def _actor_forward_t(self, ins0: torch.Tensor, ins1: torch.Tensor) -> torch.Tensor:
        return self.actor_net_t(ins0, ins1)

    def _critic_forward_t(self, ins0: torch.Tensor, ins1: torch.Tensor, action_input: torch.Tensor) -> torch.Tensor:
        return self.critic_net_t(ins0, ins1, action_input)
    
    # -----------------------------
    # Action selection and utilities
    # -----------------------------
    def take_one_layer_action(self, current_phase, combine_phases):
        """
        功能: 在单层候选相位集合 `combine_phases` 中选择一个相位索引。
        逻辑: 将每个候选相位拆分为若干基本相位, 映射到对应车道索引集合, 用 `self.lane_queue_length`
        统计这些车道的等待车辆数总和, 选择总和最大的候选相位返回其索引。

        参数:
        - current_phase: int 当前相位索引(若不生效可为 -1)。
        - combine_phases: list[str] 该层候选相位字符串(如 "SN_SE").

        返回:
        - int: 选择的候选相位在 `combine_phases` 中的索引。
        """
        phase_VN = []#每个相位下，相位对应所有车道中等待车辆数总和
        for i in range(len(combine_phases)):
            phase_str = combine_phases[i].split('_')
            num_vehicle = 0
            for phase in phase_str:
                indexs = [k for k,v in self.index_to_phase.items() if phase in v]#查找相位对应的车道序号
                num_vehicle = sum([self.lane_queue_length[i] for i in  indexs ],num_vehicle)#获取车道中数量总和
                #print(phase, indexs, num_vehicle)
            phase_VN.append(num_vehicle)
        
        idx = np.argmax(phase_VN)
        #print(idx,phase_VN)
        return idx
        
    def layers_action(self, bind_phases, old_action_list, new_layers_action_result, branch_flag, layers_flag):
        """
        功能: 递归地在多层绑定相位结构 `bind_phases` 中逐层选择动作, 生成新的层级动作序列。

        参数:
        - bind_phases: 嵌套数组/树形结构, 描述层级相位绑定关系。
        - old_action_list: list[int] 历史动作序列(用于起始层定位当前相位)。
        - new_layers_action_result: list[int] 输出容器, 逐层追加新的动作索引。
        - branch_flag: bool 标记是否已发生分支切换, 用于控制首层特殊处理。
        - layers_flag: list[bool] 与层对应的标记, 控制是否强制从序列起点或相邻项切换。

        返回: None, 结果写入 `new_layers_action_result`。
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

    def algorithm_control(self, curr_action, state, env_state):
        """
        功能: 根据当前外部动作 `curr_action` 与环境状态选择信号机相位索引。
        过程:
        1) 从 `state` 读取 `lane_queue_length` 与 `num_in_deg` 作为模型输入缓存。
        2) 将 `curr_action` 映射到层级动作列表, 递归选择得到新的层级动作, 并映射为信号相位索引。
        3) 若当前相位尚未达到上次预测的持续时长 `self.duration`, 则保持相位不变; 否则按模型预测更新 `duration` 并允许切换。

        参数:
        - curr_action: int 外部给定的主索引/动作。
        - state: dict 含路口状态(按 `self.config.INTERSECTION` 键索引)。
        - env_state: dict 环境状态, 含 `currentPhase` 与 `phaseTime`。

        返回:
        - int: 要下发的信号相位索引。
        """
        state = state[self.config.INTERSECTION]
        self.lane_queue_length = state["lane_queue_length"]
        self.num_in_deg = state["num_in_deg"]
        #self.phase_map = state["phase_map"]
        #self.index_to_phase = state["index_to_phase"]
        old_action_list = []
        
        index_to_actionlist(curr_action - 1, self.config.BIND_PHASES, old_action_list)
        new_layers_action_result = []
        self.layers_action(self.config.BIND_PHASES, old_action_list, new_layers_action_result, False, self.config.LAYERS_ORDER_FLAG)
        master_action = actionlist_to_index(new_layers_action_result, self.config.BIND_PHASES)
        alg_action_signal_index = master_index_2_signal_index(master_action, self.config.PHASES, self.config.CURRENT_PLAN_PHASE_TO_NUMBER)
        print("alg_action_signal_index:",alg_action_signal_index)
        #master_action = signal_index_2_master_index(action, self.config.PHASES, self.config.CURRENT_PLAN_STAGE_PHASE)
        
        if env_state["phaseTime"] <= self.duration:
            alg_action_signal_index = env_state["currentPhase"]
            phasetime = env_state["phaseTime"]
            if self.config.DEBUG:
                msg = f"DEBUG: phasetime: {phasetime} 小于等于duration:{self.duration}，保持原相位{alg_action_signal_index}"
                self.config.LOGGER(6,"Advanced_alg", msg)
                self.log_collector.log(logging.INFO, f'Advanced_alg, {msg}' )
            print(f"phasetime: {phasetime} 小于等于duration:{self.duration}，保持原相位{alg_action_signal_index}")
        elif alg_action_signal_index != env_state["currentPhase"]:
            self.duration = self.phase_duration(master_action,noise=True)[0]
            print(f"切换相位为：{alg_action_signal_index}(算法相位index), 相位时长uration:{self.duration}")
        else:
            pass

        #return new_layers_action_result
        return alg_action_signal_index
    
    def take_action(self, state, env_state):
        """
        功能: 计算一个可执行的动作并记录当前输入输出, 供外部执行。

        参数:
        - state: dict 当前观测状态。
        - env_state: dict 环境状态。

        返回:
        - int: 选定的动作(信号相位索引)。
        """

        #if self.config.CITYFLOW_TEST == 0:
        action = self.take_follow_action(state, env_state)
        # else:
        #     action = self.take_follow_action_cityflow(state, env_state)
        self.set_cur_input_and_output(action, state, env_state)
        if self.config.DEBUG:
            msg = f"DEBUG: advanced_v2_2 env_state is {env_state}, algorithm output phase is {self.cur_action}, \
                                                running vehicle is {self.cur_running_vehicle_roads}, waiting vehicle is {self.cur_waiting_vehicle_roads} \
                                                phase_history is {self.config.ACTION_HISTORY}"
            self.config.LOGGER(5,"Advanced_alg", msg)
            self.log_collector.log(logging.INFO, f'Advanced_alg, {msg}' )
        return action

    def phase_duration(self,action, noise=True):
        """
        功能: 预测给定主索引 `action` 对应相位的持续时长。
        处理: 将动作索引包装为相位矩阵输入, 与 `self.num_in_deg` 一起送入 actor 网络预测,
        可选地添加噪声, 返回裁剪后的合法时长列表。

        参数:
        - action: int 主相位索引(与相位映射一致)。  
        - noise: bool 是否在预测中加入噪声。

        返回:
        - list[int]: 预测时长(通常长度为1)。
        """
        phase = []
        phase_feat = []
        tmp_idx = action #master_index:0, 1, 2, 3
        phase.append([[tmp_idx]])
        phase_feat.append(self.num_in_deg)
        phase_feat2, phase_idx = np.array(phase_feat), np.array(phase)
        phase_matrix = self.phase_index2matrix(phase_idx)
        duration = self.predict([phase_feat2,phase_matrix], self.ou_noise, noise)
        return duration

    def predict(self, state, noise_object: OrnsteinUhlenbeckProcess, isnoise: bool = True) -> List[int]:
        # Convert inputs to tensors
        """
        功能: 使用 actor 网络对输入状态进行前向预测, 并在需要时注入 OU 噪声, 最终输出裁剪至
        合法范围的整数动作/时长。

        参数:
        - state: list[tensor] actor 的多输入(batch, 特征, 相位矩阵等)。
        - noise_object: OrnsteinUhlenbeckProcess 用于生成时间相关噪声。
        - isnoise: bool 是否添加噪声。

        返回:
        - list[int]: 裁剪到 [self.low, self.high] 的整数列表。
        """
        if not isinstance(state[0], torch.Tensor):
            state_tensor = [torch.FloatTensor(state[0]), torch.FloatTensor(state[1])]
        else:
            state_tensor = state

        with torch.no_grad():
            sampled_actions = self._actor_forward(state_tensor[0].to(self.device), state_tensor[1].to(self.device)).squeeze().cpu()

        if isnoise:
            sampled_actions = sampled_actions.numpy()
            if np.size(sampled_actions) == 1:
                noise = noise_object.generate()
                sampled_actions = sampled_actions + (noise[0] if hasattr(noise, "size") else noise)
            else:
                for i in range(sampled_actions.size):
                    noise = noise_object.generate()
                    sampled_actions[i] += (noise[0] if hasattr(noise, "size") else noise)

        if not hasattr(sampled_actions, 'size') or np.size(sampled_actions) == 1:
            sampled_actions = np.array([sampled_actions])
        legal_action = np.clip(sampled_actions, self.low, self.high).astype(int).tolist()
        return legal_action


    def phase_index2matrix(self, phase_index: np.ndarray) -> np.ndarray:
        # phase_index: ndarray of shape [batch,1,1]
        idx = np.array(phase_index).reshape(-1)
        lab = np.zeros((len(idx), self.config.PHASE_NUMBER), dtype=np.float32)
        lab[np.arange(len(idx)), idx] = 1.0
        return lab.reshape(-1, 1, self.config.PHASE_NUMBER)
    
    def train_network(self) -> None:
        if not hasattr(self, 'Xs') or self.Xs is None or len(self.Xs) == 0:
            return
        epochs = self.config.EPOCHS
        batch_size = min(self.config.BATCH_SIZE, len(self.Xs))
        for _ in range(epochs):
            import random
            sample_batch = random.sample(self.Xs, batch_size)
            state, phase, n_state = [], [], []
            for item in sample_batch:
                state.append(item[0])
                phase.append(item[6])
                n_state.append(item[3])
            state = np.array(state, dtype=np.float32)
            phase = np.array(phase, dtype=np.float32)
            n_state = np.array(n_state, dtype=np.float32)

            state_batch = [torch.FloatTensor(state).to(self.device), torch.FloatTensor(phase).to(self.device)]
            next_state_batch = [torch.FloatTensor(n_state).to(self.device), torch.FloatTensor(phase).to(self.device)]
            action_batch = torch.FloatTensor([[i[2]] for i in sample_batch]).to(self.device)
            reward_batch = torch.FloatTensor([[i[4]] for i in sample_batch]).to(self.device)

            # Train critic
            self.critic_optimizer.zero_grad()
            with torch.no_grad():
                target_actions = self._actor_forward_t(next_state_batch[0], next_state_batch[1])
                y = reward_batch + self.discount_factor * self._critic_forward_t(
                    next_state_batch[0], next_state_batch[1], target_actions
                )
            critic_value = self._critic_forward(state_batch[0], state_batch[1], action_batch)
            critic_loss = F.mse_loss(critic_value, y)
            critic_loss.backward()
            self.critic_optimizer.step()

            # Train actor
            self.actor_optimizer.zero_grad()
            actions = self._actor_forward(state_batch[0], state_batch[1])
            actor_q = self._critic_forward(state_batch[0], state_batch[1], actions)
            actor_loss = -torch.mean(actor_q)
            actor_loss.backward()
            self.actor_optimizer.step()

            # Soft update targets
            self._soft_update_targets(self.tau)

    def _soft_update_targets(self, tau: float) -> None:
        for (tgt, src) in [
            (self.actor_net_t, self.actor_net),
            (self.critic_net_t, self.critic_net),
        ]:
            for tparam, sparam in zip(tgt.parameters(), src.parameters()):
                tparam.data.copy_(tau * sparam.data + (1 - tau) * tparam.data)
    
    def prepare_Xs_Y(self, memory: List) -> None:
        ind_end = len(memory)
        ind_sta = max(0, ind_end - self.config.MAX_MEMORY_LEN) if ind_end > 0 else 0
        memory_after_forget = memory[ind_sta: ind_end]
        sample_size = min(self.config.SAMPLE_SIZE, len(memory_after_forget))
        sample_slice = []
        if sample_size > 0:
            import random
            sample_slice = random.sample(memory_after_forget, sample_size)
            for i in range(len(sample_slice)):
                state, action1, action2, next_state, reward, _ = sample_slice[i]
                phase_matrix = self.phase_index2matrix(np.array([action1]))
                sample_slice[i].append(phase_matrix)
        self.Xs = sample_slice
    # -----------------------------
    # Save / Load APIs
    # -----------------------------
    def save_network(self, file_name_base: str) -> None:
        """
        Persist model weights. We store all relevant submodules inside a single
        file named `<base>_actor.pth` for simplicity and compatibility with
        existing loader sites. Additional files are created empty to match names.
        """
        os.makedirs(os.path.dirname(file_name_base), exist_ok=True)

        state = {
            'actor': self.actor_net.state_dict(),
            'critic': self.critic_net.state_dict(),
            'actor_t': self.actor_net_t.state_dict(),
            'critic_t': self.critic_net_t.state_dict(),
        }
        torch.save(state, file_name_base + '.pth')

    def load_network(self, file_name: str, file_path: Optional[str] = None) -> None:
        if file_path is None:
            file_path = self.config.MODEL_PATH
        path = os.path.join(file_path, file_name)
        try:
            state = torch.load(path + '.pth', map_location='cpu')
            self.actor_net.load_state_dict(state['actor'])
            self.critic_net.load_state_dict(state['critic'])
            if 'actor_t' in state:
                self.actor_net_t.load_state_dict(state['actor_t'])
            if 'critic_t' in state:
                self.critic_net_t.load_state_dict(state['critic_t'])
        except Exception:
            print('traceback.format_exc():\n%s' % traceback.format_exc())
        print("succeed in loading model %s" % file_name)    

    def get_phase_map(self):
        """
        功能：生成相位选择所需变量
            1. 把lane_to_phase转换为按照固定顺序的lane_index_to_phase
                固定顺序为：self.config.FIXED_ORDER_LANES        
            2. 输出每个相位对应的放行车道phase_map
        输出：
            lane_index_to_phase:{0: 'WN', 1: 'WE',...... 11: 'SN', 12: 'SN_SE'}
            phase_map：[[7, 8, 10, 11, 12], [6, 9, 10], [1, 2, 4, 5], [0, 3]]
        """
        phases = self.config.PHASES
        index = 0
        lane_index_to_phase = {}
        for approach in self.config.FIXED_ORDER_LANES:
            for k,v in self.config.LANE_TO_PHASE.items():
                if approach  in k :
                    lane_index_to_phase[index] = v
                    index += 1
        phase_map = []
        for phase in phases:
            phase_str = phase.split("_")
            phase_map1 = []
            for movement in phase_str:
                phase_map1.extend( [k for  k,v in lane_index_to_phase.items() if movement in v])
            phase_map.append(sorted(set(phase_map1)))
        return phase_map, lane_index_to_phase

    

AdvancedV3 = AdvancedV2_2        # backward-compatible alias
AdvancedFuzzylight = AdvancedV2_2  # backward-compatible alias
