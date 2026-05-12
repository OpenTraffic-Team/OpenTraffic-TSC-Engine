from typing import Dict
from enum import Enum
import traceback 
import copy

from algorithms.saferules.rules.pre_rules.check_is_overflow_rule import CheckIsOverflowRule
from algorithms.saferules.rules.pre_rules.check_person_rule import CheckPersonRule
from algorithms.saferules.rules.pre_rules.check_initial_phase_rule import CheckInitialPhaseRule
from algorithms.saferules.rules.pre_rules.check_person_click_rule import CheckIsPersonClickRule
from algorithms.saferules.rules.pre_rules.check_transition_rule import CheckTransitionRule
from algorithms.saferules.rules.pre_rules.check_cycle_control_rule import CheckCycleControlRule
from algorithms.saferules.rules.pre_rules.check_gt_maxkeep_rule import CheckIsGtMaxkeepRule
from algorithms.saferules.rules.pre_rules.check_remain_phases_excute_rule import CheckRemainPhasesNotExcuteRule
from algorithms.saferules.rules.pre_rules.check_min_green_time_rule import CheckMinGreenTimeRule

from algorithms.saferules.compositors.compositor import Compositor

class PreSafeRules:
    def __init__(self, algo=None):
        
        self.safe_excutor = Compositor(
            #相位运行保障
            CheckInitialPhaseRule(algo),

            CheckIsOverflowRule(algo),
            CheckMinGreenTimeRule(algo),          
            CheckTransitionRule(algo),
            CheckPersonRule(algo),
            CheckCycleControlRule(algo),
            CheckIsGtMaxkeepRule(algo),
            CheckRemainPhasesNotExcuteRule(algo)
        )
       

    def excute_rules_chain(self, state: Dict, env_state: Dict):
            
        return self.safe_excutor.evaluate(state, env_state)

