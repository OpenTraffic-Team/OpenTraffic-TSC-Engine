import os
from typing import Dict, List, Optional

import numpy as np
import torch
import torch.nn as nn

from algorithms.models import *
from algorithms.utils.util import index_to_actionlist
from algorithms.utils.replay_buffer import ReplayBuffer


class AttendLightQNet(nn.Module):
    """
    功能: 基于 AttendLight 思路的 Q 网络,用于从车道级特征计算各相位的 Q 值。
    说明:
        - 输入: 张量形状为 [B, lane_count * feat_dim], 默认 feat_dim=8。
        - 输出: 张量形状为 [B, num_actions], 默认 num_actions=num_phases。
    """

    def __init__(
        self,
        lane_count: int,
        num_phases: int,
        phase_map: List[List[int]],
        feat_dim: int = 8,
        embed_dim: int = 32,
        mha_heads: int = 4,
    ) -> None:
        super().__init__()
        self.lane_count = int(lane_count)
        self.num_phases = int(num_phases)
        self.num_actions = int(num_phases)
        self.phase_map = phase_map
        self.feat_dim = int(feat_dim)

        self.lane_embed = nn.Linear(self.feat_dim, embed_dim)
        self.act = nn.ReLU()

        # 说明: MultiheadAttention 使用 batch_first=True, 输入形状为 [B, T, C]
        self.mha_lane = nn.MultiheadAttention(embed_dim=embed_dim, num_heads=mha_heads, batch_first=True)
        self.mha_phase = nn.MultiheadAttention(embed_dim=embed_dim, num_heads=mha_heads, batch_first=True)

        self.fc1 = nn.Linear(embed_dim, 20)
        self.fc2 = nn.Linear(20, 20)
        self.out = nn.Linear(20, 1)

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        # 功能: 将一维车道特征向量还原为 [批次, 车道数, 特征维度] 形式,并计算各相位的 Q 值。
        # 形状变化: x: [B, lane_count * feat_dim] -> [B, lane_count, feat_dim]
        b = x.shape[0]
        x = x.view(b, self.lane_count, self.feat_dim).to(torch.float32)

        lane_feat = self.act(self.lane_embed(x))  # 线性映射到嵌入空间,得到 [B, lane_count, E]

        # 基于每个相位所包含的车道集合,构建相位级别的表示(相位对其车道集做注意力聚合)
        phase_reprs: List[torch.Tensor] = []
        for idxs in self.phase_map:
            if not idxs:
                # 若该相位没有对应车道,退化为对所有车道做全局平均
                key = lane_feat
            else:
                key = lane_feat[:, idxs, :]

            query = key.mean(dim=1, keepdim=True)  # 以车道特征均值作为查询向量 [B, 1, E]
            attn_out, _ = self.mha_lane(query=query, key=key, value=key, need_weights=False)
            phase_reprs.append(attn_out)  # 单个相位的聚合表示 [B, 1, E]

        phase_feat_all = torch.cat(phase_reprs, dim=1)  # 拼接得到所有相位特征 [B, num_phases, E]
        phase_attn, _ = self.mha_phase(
            query=phase_feat_all, key=phase_feat_all, value=phase_feat_all, need_weights=False
        )  # [B, num_phases, E]

        h = self.act(self.fc1(phase_attn))
        h = self.act(self.fc2(h))
        q = self.out(h)  # [B, num_phases, 1]
        q = q.view(b, self.num_actions)  # [B, num_actions]
        return q


class AdvancedV2_3(Agent):
    """
    功能: 基于 AttendLight 思路的智能体,根据当前路口状态与信号机状态输出相位决策。
    说明:
        - 输入: 特征提取后的路口状态 state、信号机环境状态 env_state。
        - 输出: 符合当前方案与绑定关系的相位索引(供上层写回信号机或中间件)。
    """

    def __init__(self, config) -> None:
        super().__init__(config)
        self.config = config
        self.log_collector = LogCollector(enable_print=True)

        self.phase_map, self.lane_index_to_phase = self.get_phase_map()
        self.lane_count = len(self.lane_index_to_phase)
        self.num_actions = len(self.config.PHASES)

        self.device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
        self.q_network = AttendLightQNet(
            lane_count=self.lane_count,
            num_phases=self.num_actions,
            phase_map=self.phase_map,
            feat_dim=8,
        ).to(self.device)

        # AdvancedControl 在执行过程中会访问 algo.replay_buffer.store(...)
        # 因此 v4 推理智能体也需要提供一个最小可用的 ReplayBuffer。
        self.replay_buffer = ReplayBuffer(self.config.REPLAYBUFFER_CAPACITY, self.config.BATCH_SIZE, config)

        self._maybe_load_weights()
        self.config.LOGGER(5, "Advanced_alg", "Advanced control version is AttendLight(offline) 0.1.0")

    def _maybe_load_weights(self) -> None:
        """
        功能: 尝试从配置的 MODEL_PATH 中加载 AttendLight 模型权重(可选)。
        输入:
            无(从 self.config.MODEL_PATH 读取路径信息)。
        输出:
            无; 若加载成功,则更新 self.q_network 的参数; 否则采用随机初始化权重继续运行。
        """
        path = getattr(self.config, "MODEL_PATH", None)
        if not path:
            return

        candidate_files: List[str] = []
        if os.path.isfile(path):
            candidate_files.append(path)
        elif os.path.isdir(path):
            candidate_files.extend(
                [
                    os.path.join(path, "attendlight.pth"),
                    os.path.join(path, "advanced_attendlight.pth"),
                ]
            )

        for f in candidate_files:
            if os.path.exists(f) and os.path.isfile(f):
                try:
                    state = torch.load(f, map_location="cpu")
                    # Support either raw state_dict or a wrapped dict
                    if isinstance(state, dict) and "state_dict" in state:
                        state = state["state_dict"]
                    self.q_network.load_state_dict(state, strict=False)
                    self.log_collector.log(logging.INFO, f"AdvancedAttendLight loaded weights from: {f}")
                    return
                except Exception as e:
                    self.log_collector.log(logging.ERROR, f"AdvancedAttendLight load weights failed: {f}, err={e}")

        self.log_collector.log(logging.WARNING, "AdvancedAttendLight: no weights loaded, using random init")

    def get_phase_map(self):
        """
        功能: 构建相位与车道索引的映射关系,供 AttendLight 网络使用。
        输入:
            无(从 self.config 读取 PHASES、FIXED_ORDER_LANES、LANE_TO_PHASE 等配置)。
        输出:
            phase_map: List[List[int]]  每个相位对应的车道索引列表。
            lane_index_to_phase: Dict[int, List[str]]  车道索引到车道相位字符串列表的映射。
        """
        phases = self.config.PHASES
        index = 0
        lane_index_to_phase = {}

        for approach in self.config.FIXED_ORDER_LANES:
            for k, v in self.config.LANE_TO_PHASE.items():
                if approach in k:
                    lane_index_to_phase[index] = v
                    index += 1

        phase_map: List[List[int]] = []
        for phase in phases:
            phase_str = phase.split("_")
            mapped: List[int] = []
            for movement in phase_str:
                mapped.extend([k for k, v in lane_index_to_phase.items() if movement in v])
            phase_map.append(sorted(set(mapped)))

        return phase_map, lane_index_to_phase

    def _build_lane_feature_vector(self, state: Dict) -> np.ndarray:
        """
        功能: 根据当前路口状态构造车道特征向量,用于输入 AttendLightQNet。
        输入:
            state: 当前路口状态字典,包含 running_vehicle / waiting_vehicle 等信息。
        输出:
            feats: 一维 numpy 数组,长度为 lane_count * 8。
                  其中每个车道占 8 维,目前只用前 2 维(运行车辆数、等待车辆数),其余 6 维补 0 占位。
        """
        inter = state[self.config.INTERSECTION]
        running = inter.get("running_vehicle", {}) or {}
        waiting = inter.get("waiting_vehicle", {}) or {}

        feats: List[float] = []
        for i in range(self.lane_count):
            movement = self.lane_index_to_phase.get(i, "")
            # 若 movement 来自 lane_to_phase 的组合写法(如 "EW_EN"),
            # 需要拆分后对日志里的单 movement 维度做确定性相加。
            if "_" in movement:
                parts = [p for p in movement.split("_") if p]
                run_v = float(sum(float(running.get(p, 0)) for p in parts))
                wait_v = float(sum(float(waiting.get(p, 0)) for p in parts))
            else:
                run_v = float(running.get(movement, 0))
                wait_v = float(waiting.get(movement, 0))
            feats.extend([run_v, wait_v, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0])

        return np.asarray(feats, dtype=np.float32)


    def _sum_q_for_combine_phases(self, q_values: np.ndarray, combine_phases: List[str]) -> List[float]:
        """
        功能: 将基础相位的 Q 值汇总成「组合相位」(如 'SN_SE') 的评分。
        输入:
            q_values: numpy 数组,长度等于 self.config.PHASES,表示每个基础相位的 Q 值。
            combine_phases: 组合相位字符串列表,如 ['SN_SE', 'WE_WN']。
        输出:
            scores: 每个组合相位对应的 Q 值总和列表,用于后续选取最大值。
        """
        phase_to_idx = {p: i for i, p in enumerate(self.config.PHASES)}
        scores: List[float] = []
        for cp in combine_phases:
            total = 0.0
            for movement in cp.split("_"):
                idx = phase_to_idx.get(movement)
                if idx is not None:
                    total += float(q_values[idx])
            scores.append(total)
        return scores

    def take_one_layer_action(self, curr_action: int, combine_phases: List[str]) -> int:
        """
        功能: 在单层候选相位集合 combine_phases 中,基于 AttendLight Q 网络选择一个相位索引。
        输入:
            curr_action: 当前相位索引,若为 -1 表示不考虑当前相位,直接按评分最大选择。
            combine_phases: 当前层可选的组合相位字符串列表。
        输出:
            action: 被选中的组合相位在 combine_phases 中的索引。
        """
        x = self._build_lane_feature_vector(self.state_cached)
        x_t = torch.from_numpy(x).unsqueeze(0).to(self.device)
        with torch.no_grad():
            q = self.q_network(x_t).detach().cpu().numpy()[0]

        scores = self._sum_q_for_combine_phases(q, combine_phases)
        if curr_action == -1:
            return int(np.argmax(scores))
        return int(np.argmax(scores))

    def layers_action(self, bind_phases, old_action_list, new_layers_action_result, branch_flag: bool, layers_flag: list):
        """
        功能: 在多层绑定相位结构 bind_phases 中,递归选择每一层的动作,生成新的层级动作序列。
        输入:
            bind_phases: 当前层的绑定相位结构(树/嵌套列表)。
            old_action_list: 历史动作序列,用于首层定位当前相位。
            new_layers_action_result: 输出容器,逐层追加新的动作索引。
            branch_flag: 标记是否已经发生分支切换,影响首层处理逻辑。
            layers_flag: 与层对应的标记列表,控制是否按顺序或强制切换。
        输出:
            无; 结果写入 new_layers_action_result。
        """
        if type(bind_phases) == int:
            return

        combine_phases: List[str] = []
        for i in bind_phases:
            a = np.atleast_1d(i).flatten()
            l = np.array(self.config.PHASES)[a]
            combine_phases.append("_".join(l))

        current_phase = -1 if branch_flag else old_action_list[0]
        action = self.take_one_layer_action(current_phase, combine_phases)

        if action != current_phase and branch_flag is True and layers_flag and layers_flag[0] is True:
            action = 0
        if action != current_phase and branch_flag is False:
            branch_flag = True
            if layers_flag and layers_flag[0] is True:
                action = (current_phase + 1) % len(combine_phases)

        new_layers_action_result.append(action)
        next_bind_phases = bind_phases[action]
        old_action_list = old_action_list[1:]
        layers_flag = layers_flag[1:] if layers_flag else []
        self.layers_action(next_bind_phases, old_action_list, new_layers_action_result, branch_flag, layers_flag)

    def algorithm_control(self, curr_action, state, env_state):
        """
        功能: AttendLight 算法主控流程,生成多层相位序列。
        输入:
            curr_action: 当前相位索引(主相位)。
            state: 当前路口状态字典。
            env_state: 环境状态(如信号机当前相位、计划等)。
        输出:
            new_layers_action_result: 多层相位序列,供上层框架转换为实际信号相位。
        """
        # 缓存当前状态,供递归选相位时构造特征使用
        self.state_cached = state

        inter = state[self.config.INTERSECTION]
        self.cur_waiting_vehicle_roads = inter.get("waiting_vehicle")
        self.cur_running_vehicle_roads = inter.get("running_vehicle")

        old_action_list: List[int] = []
        index_to_actionlist(curr_action - 1, self.config.BIND_PHASES, old_action_list)
        new_layers_action_result: List[int] = []
        self.layers_action(self.config.BIND_PHASES, old_action_list, new_layers_action_result, False, self.config.LAYERS_ORDER_FLAG)
        return new_layers_action_result

    def take_action(self, state: Dict, env_state):
        """
        功能: 算法统一入口,配合基类的 take_follow_action 完成完整相位决策流程。
        输入:
            state: 当前路口状态字典。
            env_state: 环境状态字典(包含 currentPhase 等信息)。
        输出:
            action: 算法最终输出的信号机相位索引。
        """
        action = self.take_follow_action(state, env_state)
        self.set_cur_input_and_output(action, state, env_state)
        return action


AdvancedV2_3 = AdvancedV2_3  # backward-compatible alias
