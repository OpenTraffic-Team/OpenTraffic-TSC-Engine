from algorithms.saferules.rules.pre_rules.imports import *

class CheckRemainPhasesNotExcuteRule(BaseRule):
    def __init__(self, algo=None):
        super().__init__(algo)

    def execute(self, state: Dict, env_state: Dict) -> RuleResult:
        try:
            # 如果调用算法次数大于n轮，则周期调度
            per_cycle_seconds = 0
            action = env_state["currentPhase"]
            for i in range(self.algo.config.PHASE_NUMBER):
                per_cycle_seconds += self.algo.config.MIN_GREEN_TIME[self.algo.config.PHASES[i]] + 6
            max_advanced_take_time = self.algo.config.MAX_KEEP_NUM * per_cycle_seconds
                
            

            if self.algo.config.ADVANCED_TAKE_COUNT >= max_advanced_take_time:
                if self.algo.config.DEBUG:
                    self.algo.config.LOGGER(0, "Advanced_alg", f"DEBUG: check_remain_phases_not_excute env_state is {env_state}, max algorithm take time is {max_advanced_take_time}\
                                            algorithm take time is {self.algo.config.ADVANCED_TAKE_COUNT}") 
                    self.algo.log_collector.log(logging.DEBUG, f"Advanced_alg, DEBUG: check_remain_phases_not_excute env_state is {env_state}, max algorithm take time is {max_advanced_take_time}\
                                            algorithm take time is {self.algo.config.ADVANCED_TAKE_COUNT}")
                # 如果advanced算法调度了n轮，则计算advanced历史action，求得未采用的action
                return self._excute_remain_phases(action)
            else:
                return RuleResult.SUCCESS
        except:
            self.algo.config.LOGGER(5, "Advanced_alg", f"Exception occurred: check_remain_phases_not_excute error message is {traceback.format_exc()}")
            self.algo.log_collector.log(logging.ERROR, f"Advanced_alg, Exception occurred: check_remain_phases_not_excute error message is {traceback.format_exc()}")
            return RuleResult.FAILURE
