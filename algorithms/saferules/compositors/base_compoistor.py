
from abc import ABC, abstractmethod
from typing import Dict

from algorithms.saferules.rules.base_rule import BaseRule
from algorithms.saferules.rules.rule_result import RuleResult

from algorithms.saferules.rules.pre_rules.check_is_overflow_rule import CheckIsOverflowRule
from algorithms.saferules.rules.pre_rules.check_person_rule import CheckPersonRule
from algorithms.saferules.rules.pre_rules.check_data_complete_rule import CheckDataCompleteRule
from algorithms.saferules.rules.pre_rules.check_sensor_error_rule import CheckSensorErrorRule
from algorithms.saferules.rules.pre_rules.check_sensor_frequent_delay_rule import CheckSensorFrequentDelayRule
from algorithms.saferules.rules.pre_rules.check_delay_gt_threshold_rule import CheckDelayGtThresholdRule
from algorithms.saferules.rules.pre_rules.check_initial_phase_rule import CheckInitialPhaseRule
from algorithms.saferules.rules.pre_rules.check_person_click_rule import CheckIsPersonClickRule
from algorithms.saferules.rules.pre_rules.check_transition_rule import CheckTransitionRule
from algorithms.saferules.rules.pre_rules.check_cycle_control_rule import CheckCycleControlRule
from algorithms.saferules.rules.pre_rules.check_gt_maxkeep_rule import CheckIsGtMaxkeepRule
from algorithms.saferules.rules.pre_rules.check_remain_phases_excute_rule import CheckRemainPhasesNotExcuteRule
from algorithms.saferules.rules.pre_rules.check_min_green_time_rule import CheckMinGreenTimeRule



class BaseCompositor(ABC):
    def __init__(self, *rules: BaseRule,):
        self.rules = rules

    @abstractmethod
    def evaluate(self, state: Dict, env_state: Dict, action=None) -> RuleResult:
        pass
