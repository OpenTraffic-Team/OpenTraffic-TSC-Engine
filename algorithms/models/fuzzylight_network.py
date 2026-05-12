import torch
import torch.nn as nn
import torch.nn.functional as F
from torch.nn import MultiheadAttention
from typing import List

"""
@File      : fuzzylight_network.py
@Desc      : fuzzylight network搭建
@Author    : lizhuojun
@Date      : 2025-09-04
"""

class ActorNet(nn.Module):
    def __init__(self, max_lane: int, num_phases: int, phase_map: List[List[int]], high: int = 40):
        super().__init__()
        self.max_lane = max_lane
        self.num_phases = num_phases
        self.phase_map = phase_map
        self.high = high

        # Embedding layers (lane -> phase)
        self.feature_transform = nn.Linear(4, 4)
        self.feature_transform2 = nn.Linear(4, 16)
        self.mha = MultiheadAttention(embed_dim=16, num_heads=4, batch_first=True)
        self.state_fc1 = nn.Linear(16, 16)
        self.state_fc2 = nn.Linear(16, 16)  # embedding output: 16-dim (match TF)

        # Head
        self.fc1 = nn.Linear(16, 256)
        self.fc2 = nn.Linear(256, 256)
        self.fc3 = nn.Linear(256, 1)

    def get_lane_embedding(self, ins0: torch.Tensor, ins1: torch.Tensor) -> torch.Tensor:
        # Normalize shapes
        if ins0.dim() == 1:
            ins0 = ins0.unsqueeze(0)
        if ins0.dim() > 2:
            ins0 = ins0.view(ins0.shape[0], -1)
        if ins1.dim() == 2:
            ins1 = ins1.unsqueeze(1)  # [B,1,num_phases]
        elif ins1.dim() > 3:
            # Squeeze extra singleton dims
            ins1 = ins1.view(ins1.shape[0], -1, ins1.shape[-1])
        batch_size = ins0.size(0)
        feat1 = ins0.view(batch_size, self.max_lane, 4)
        feat1 = torch.sigmoid(self.feature_transform(feat1))
        feat1 = self.feature_transform2(feat1)  # [B,max_lane,16]
        lane_feats_s = torch.split(feat1, 1, dim=1)

        phase_feats_map_2: List[torch.Tensor] = []
        for i in range(self.num_phases):
            phase_lane_indices = self.phase_map[i] if i < len(self.phase_map) else []
            if len(phase_lane_indices) == 0:
                phase_feats_map_2.append(torch.zeros(batch_size, 1, 16, device=ins0.device))
                continue
            selected = [lane_feats_s[idx] for idx in phase_lane_indices if idx < len(lane_feats_s)]
            if len(selected) == 0:
                phase_feats_map_2.append(torch.zeros(batch_size, 1, 16, device=ins0.device))
                continue
            tmp_feat_1 = torch.cat(selected, dim=1)
            tmp_feat_2, _ = self.mha(tmp_feat_1, tmp_feat_1, tmp_feat_1)
            tmp_feat_3 = torch.mean(tmp_feat_2, dim=1, keepdim=True)
            phase_feats_map_2.append(tmp_feat_3)

        phase_feat_all = torch.cat(phase_feats_map_2, dim=1)  # [B,num_phases,16]
        selected_phase_feat = torch.matmul(ins1, phase_feat_all)
        # Squeeze to [B,16]
        if selected_phase_feat.dim() == 3:
            selected_phase_feat = selected_phase_feat.squeeze(1)
        elif selected_phase_feat.dim() == 4:
            selected_phase_feat = selected_phase_feat.squeeze(1).squeeze(1)
        hidden = F.relu(self.state_fc1(selected_phase_feat))
        hidden = F.relu(self.state_fc2(hidden))  # [B,16]
        return hidden

    def forward(self, ins0: torch.Tensor, ins1: torch.Tensor) -> torch.Tensor:
        hidden = self.get_lane_embedding(ins0, ins1)  # [B,16]
        out = F.relu(self.fc1(hidden))
        out = F.relu(self.fc2(out))
        outputs = torch.sigmoid(self.fc3(out)) * self.high
        return outputs


class CriticNet(nn.Module):
    def __init__(self, max_lane: int, num_phases: int, phase_map: List[List[int]]):
        super().__init__()
        self.max_lane = max_lane
        self.num_phases = num_phases
        self.phase_map = phase_map

        # Embedding layers (lane -> phase)
        self.feature_transform = nn.Linear(4, 4)
        self.feature_transform2 = nn.Linear(4, 16)
        self.mha = MultiheadAttention(embed_dim=16, num_heads=4, batch_first=True)
        self.state_fc1 = nn.Linear(16, 16)
        self.state_fc2 = nn.Linear(16, 32)  # critic state branch to 32-dim (match TF)

        # Action branch
        self.action_fc = nn.Linear(1, 32)

        # Head
        self.concat_fc1 = nn.Linear(64, 256)
        self.concat_fc2 = nn.Linear(256, 256)
        self.concat_fc3 = nn.Linear(256, 1)

    def get_lane_embedding(self, ins0: torch.Tensor, ins1: torch.Tensor) -> torch.Tensor:
        # Normalize shapes
        if ins0.dim() == 1:
            ins0 = ins0.unsqueeze(0)
        if ins0.dim() > 2:
            ins0 = ins0.view(ins0.shape[0], -1)
        if ins1.dim() == 2:
            ins1 = ins1.unsqueeze(1)
        elif ins1.dim() > 3:
            ins1 = ins1.view(ins1.shape[0], -1, ins1.shape[-1])
        batch_size = ins0.size(0)
        feat1 = ins0.view(batch_size, self.max_lane, 4)
        feat1 = torch.sigmoid(self.feature_transform(feat1))
        feat1 = self.feature_transform2(feat1)
        lane_feats_s = torch.split(feat1, 1, dim=1)
        phase_feats_map_2: List[torch.Tensor] = []
        for i in range(self.num_phases):
            phase_lane_indices = self.phase_map[i] if i < len(self.phase_map) else []
            if len(phase_lane_indices) == 0:
                phase_feats_map_2.append(torch.zeros(batch_size, 1, 16, device=ins0.device))
                continue
            selected = [lane_feats_s[idx] for idx in phase_lane_indices if idx < len(lane_feats_s)]
            if len(selected) == 0:
                phase_feats_map_2.append(torch.zeros(batch_size, 1, 16, device=ins0.device))
                continue
            tmp_feat_1 = torch.cat(selected, dim=1)
            tmp_feat_2, _ = self.mha(tmp_feat_1, tmp_feat_1, tmp_feat_1)
            tmp_feat_3 = torch.mean(tmp_feat_2, dim=1, keepdim=True)
            phase_feats_map_2.append(tmp_feat_3)
        phase_feat_all = torch.cat(phase_feats_map_2, dim=1)
        selected_phase_feat = torch.matmul(ins1, phase_feat_all)
        if selected_phase_feat.dim() == 3:
            selected_phase_feat = selected_phase_feat.squeeze(1)
        elif selected_phase_feat.dim() == 4:
            selected_phase_feat = selected_phase_feat.squeeze(1).squeeze(1)
        hidden = F.relu(self.state_fc1(selected_phase_feat))
        hidden = F.relu(self.state_fc2(hidden))  # [B,32]
        return hidden

    def forward(self, ins0: torch.Tensor, ins1: torch.Tensor, action_input: torch.Tensor) -> torch.Tensor:
        state_out = self.get_lane_embedding(ins0, ins1)  # [B,32]
        if action_input.dim() > 2:
            action_input = action_input.view(action_input.shape[0], -1)
        if action_input.dim() == 1:
            action_input = action_input.unsqueeze(1)
        if action_input.size(1) != 1:
            action_input = action_input[:, :1]
        action_out = F.relu(self.action_fc(action_input))  # [B,32]
        concat = torch.cat([state_out, action_out], dim=1)  # [B,64]
        out = F.relu(self.concat_fc1(concat))
        out = F.relu(self.concat_fc2(out))
        outputs = self.concat_fc3(out)
        return outputs