from algorithms.saferules.rules.pre_rules.imports import *

class CheckAlgoStatus(BaseRule):
    def __init__(self, algo=None):
        super().__init__(algo)

    def execute(self, state: Dict, env_state: Dict, action) -> RuleResult:
        try:
            #指定算法状态
            if action != None:
                phase = self.algo.config.CURRENT_PLAN_STAGE_PHASE[int(action)]
                if phase in self.algo.config.PHASES:
                    self.algo.config.ALGO_STATUS = AlgorithmStatus.PHASE
                elif phase.startswith('follow'):
                    self.algo.config.ALGO_STATUS = AlgorithmStatus.FOLLOW_PHASE
                elif phase in self.algo.config.OVERFLOW_PHASE:
                    self.algo.config.ALGO_STATUS = AlgorithmStatus.OVERFLOW_PHASE
                return RuleResult.SUCCESS
            else:
                self.algo.config.LOGGER(0, "Advanced_alg", f"Algorithm calculation result is None，Unable to assign algorithm state.")
                self.algo.log_collector.log(logging.ERROR, f"Advanced_alg, Algorithm calculation result is None，Unable to assign algorithm state. ")   
        except:
            self.algo.config.LOGGER(0, "Advanced_alg", f"Exception occurred: CheckAlgoStatus error message is {traceback.format_exc()}")
            self.algo.log_collector.log(logging.ERROR, f"Advanced_alg, Exception occurred: CheckAlgoStatus error message is {traceback.format_exc()}")
            return RuleResult.FAILURE

  