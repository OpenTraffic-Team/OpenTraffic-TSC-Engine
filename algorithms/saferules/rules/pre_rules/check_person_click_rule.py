from algorithms.saferules.rules.pre_rules.imports import *

class CheckIsPersonClickRule(BaseRule):
    def __init__(self, algo=None):
        super().__init__(algo)
        self.is_person_WE = False
        self.is_person_SN = False
        self.person_min_time = copy.deepcopy(self.algo.config.PERSON_MIN_TIME)

    def execute(self, state: Dict, env_state: Dict) -> RuleResult:
        try:
            if self.algo.config.DEBUG:
                self.algo.config.LOGGER(5, "Advanced_alg", f"DEBUG: check_is_person_click is_person_WE is {self.is_person_WE}, is_person_SN is {self.is_person_SN}, \
                                          person_min_time is {self.person_min_time}") 
                self.algo.log_collector.log(logging.DEBUG, f"DEBUG: check_is_person_click is_person_WE is {self.is_person_WE}, is_person_SN is {self.is_person_SN}, \
                                          person_min_time is {self.person_min_time}") 
            # 行人模块，方案1，有行人则给40s绿灯，方案2，跟车辆一样自适应控制
            if self.is_person_WE or 'IS_PERSON_WE_EW' in state[self.algo.config.INTERSECTION] and state[self.algo.config.INTERSECTION]['IS_PERSON_WE_EW'] is True:
                self.is_person_WE = True
                self.person_min_time -= 1
                # 如果行人时间变为0，则恢复，以便下次使用
                if self.person_min_time == 0:
                    self.person_min_time = self.algo.config.PERSON_MIN_TIME
                    self.is_person_WE = False
                # 若是2相位，返回东西向，若是4相位，则给东西向左转或者直行
                if self.algo.config.PHASE_NUMBER == 2:
                    return self.algo.config.PHASES.index('WE_EW_WN_ES') + 1
                else:
                    return RuleResult.SUCCESS
            
            # 行人模块，方案1，有行人则给40s绿灯，方案2，跟车辆一样自适应控制
            elif self.is_person_SN or 'IS_PERSON_NS_SN' in state[self.algo.config.INTERSECTION] and state[self.algo.config.INTERSECTION]['IS_PERSON_NS_SN'] is True:
                self.is_person_SN = True
                self.person_min_time -= 1
                # 如果行人时间变为0，则恢复，以便下次使用
                if self.person_min_time == 0:
                    self.person_min_time = self.algo.config.PERSON_MIN_TIME
                    self.is_person_SN = False
                if self.algo.config.PHASE_NUMBER == 2:
                    return self.algo.config.PHASES.index('NS_SN_NE_SW') + 1
                else:
                    return RuleResult.SUCCESS
            else:
                return RuleResult.SUCCESS
        except:
            self.algo.config.LOGGER(0, "Advanced_alg", f"Exception occurred: check_is_person_click error message is {traceback.format_exc()}")
            self.algo.log_collector.log(logging.ERROR, f"Advanced_alg, Exception occurred: check_is_person_click error message is {traceback.format_exc()}") 
            return RuleResult.FAILURE
