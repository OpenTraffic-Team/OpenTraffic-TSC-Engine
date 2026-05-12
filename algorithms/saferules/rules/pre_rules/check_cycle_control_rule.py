from algorithms.saferules.rules.pre_rules.imports import *

class CheckCycleControlRule(BaseRule):
    def __init__(self, algo=None):
        super().__init__(algo)

    def execute(self, state: Dict, env_state: Dict) -> RuleResult:
        try:
            if self.algo.config.CYCLE_CONTROL:
                if self.algo.config.DEBUG:
                    self.algo.config.LOGGER(5, "Advanced_alg", f"DEBUG: CheckCycleControlRule envstate is {env_state}") 
                    self.algo.log_collector.log(logging.DEBUG, f"Advanced_alg, DEBUG: CheckCycleControlRule envstate is {env_state}")
                action = env_state["currentPhase"]
                return self._cycle_control(action)
            else:
                return RuleResult.SUCCESS
        except:
            self.algo.config.LOGGER(0, "Advanced_alg", f"Exception occurred: CheckCycleControlRule error message is {traceback.format_exc()}")
            self.algo.log_collector.log(logging.ERROR, f"Advanced_alg, Exception occurred: CheckCycleControlRule error message is {traceback.format_exc()}")
            return RuleResult.FAILURE

  