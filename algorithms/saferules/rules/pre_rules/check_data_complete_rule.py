from algorithms.saferules.rules.pre_rules.imports import *

class CheckDataCompleteRule(BaseRule):
    def __init__(self, algo=None):
        super().__init__(algo)

    def execute(self, state: Dict, env_state: Dict) -> RuleResult:
        try:
            if  self.algo.config.CITYFLOW_TEST:
                return RuleResult.SUCCESS

            action = env_state["currentPhase"]
          
            if state == {} or state[self.algo.config.INTERSECTION] == {} or 'running_vehicle' not in state[self.algo.config.INTERSECTION] or 'waiting_vehicle' not in state[self.algo.config.INTERSECTION]:
                if self.algo.config.DEBUG:
                    self.algo.config.LOGGER(5, "Advanced_alg", f"DEBUG: check_data_is_complete env_state is {env_state}") 
                    self.algo.log_collector.log(logging.DEBUG, f"Advanced_alg, DEBUG: check_data_is_complete env_state is {env_state}")
                return self._cycle_control(action)
            else:
                return RuleResult.SUCCESS
        except:
            self.algo.config.LOGGER(0, "Advanced_alg", f"Exception occurred: check_data_is_complete error message is {traceback.format_exc()}")
            self.algo.log_collector.log(logging.ERROR, f"Advanced_alg, Exception occurred: check_data_is_complete error message is {traceback.format_exc()}")
            return RuleResult.FAILURE

 