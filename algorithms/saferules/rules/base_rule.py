from abc import ABC, abstractmethod
from typing import Dict
from algorithms.enums.algorithm_status_enum import AlgorithmStatus
from algorithms.saferules.rules.rule_result import RuleResult
from algorithms.utils.util import master_index_2_signal_index, signal_index_2_master_index
class BaseRule(ABC):
    def __init__(self, algo=None):
        self.algo = algo

    @abstractmethod
    def execute(self, state: Dict, env_state: Dict, action=None) -> RuleResult:
        pass

    def _cycle_control(self, action) -> RuleResult: 
        # 周期性选择相位  
        while 'follow' in self.algo.config.CURRENT_PLAN_STAGE_PHASE[int(action)]:
            #找到follow相位的master相位的编号  
            action_phases = self.algo.config.CURRENT_PLAN_STAGE_PHASE[int(action)] 
            action_phases = self.algo.config.PHASES_LIST[(self.algo.config.PHASES_LIST.index(action_phases) - 1)]
            action = self.algo.config.CURRENT_PLAN_PHASE_TO_NUMBER[action_phases]
        master_action_index = signal_index_2_master_index(action, self.algo.config.PHASES, self.algo.config.CURRENT_PLAN_STAGE_PHASE)
        master_action_index = (master_action_index + 1) % self.algo.config.PHASE_NUMBER
        action = master_index_2_signal_index(master_action_index, self.algo.config.PHASES, self.algo.config.CURRENT_PLAN_PHASE_TO_NUMBER)
        self.algo.config.ACTION_HISTORY.append(action)
        RuleResult.DATA = action
        return RuleResult.DATA
    
    def _excute_remain_phases(self, action) -> RuleResult:

        reference = [master_index_2_signal_index(i, self.algo.config.PHASES, self.algo.config.CURRENT_PLAN_PHASE_TO_NUMBER)  for i in range(self.algo.config.PHASE_NUMBER)]
        action_history_set = set(self.algo.config.ACTION_HISTORY)
        missing_numbers = [x for x in reference if x not in action_history_set] 
        
        # 如果advanced算法调度了n轮，则计算advanced历史action，求得未采用的action
        left_actions = list(missing_numbers)
        if self.algo.config.DEBUG:
            self.algo.config.LOGGER(5, "Advanced_alg", f"DEBUG: _excute_remain_phases remain unexcute phases is {left_actions}") 
        if len(left_actions) == 0:
            self.algo.config.ADVANCED_TAKE_COUNT = 0
            self.algo.config.ACTION_HISTORY.clear()
            return RuleResult.SUCCESS
        else:
            if self.algo.config.LAYERS_ORDER_FLAG[-1] == True:
                master_action_index = signal_index_2_master_index(action, self.algo.config.PHASES, self.algo.config.CURRENT_PLAN_STAGE_PHASE)
                master_action_index = (master_action_index + 1) % self.algo.config.PHASE_NUMBER
                action = master_index_2_signal_index(master_action_index, self.algo.config.PHASES, self.algo.config.CURRENT_PLAN_PHASE_TO_NUMBER)
            else:
                action = left_actions.pop(0)
            self.algo.config.ACTION_HISTORY.append(action)
            RuleResult.DATA = action
            return RuleResult.DATA