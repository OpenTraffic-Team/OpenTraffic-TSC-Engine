from algorithms.saferules.rules.pre_rules.imports import *

class CheckDelayGtThresholdRule(BaseRule):
    def __init__(self, algo=None):
        super().__init__(algo)

    def execute(self, state: Dict, env_state: Dict) -> RuleResult:
        try:
            if self.algo.config.CITYFLOW_TEST:
                return RuleResult.SUCCESS

            targetTimestep = env_state['timestamp']
            nowTimestep = state[self.algo.config.INTERSECTION]['timestamp']
            camera_delay_time = abs(nowTimestep - targetTimestep)
            if camera_delay_time >= self.algo.config.DELAY_TIME * 10:
                self.algo.config.LOGGER(0, "Advanced_alg", f"Exception occurred: check_delay_gt_threshold error, delay time is {camera_delay_time}") 
                self.algo.log_collector.log(logging.ERROR, f"Advanced_alg, Exception occurred: check_delay_gt_threshold error, delay time is {camera_delay_time}") 
                return RuleResult.FAILURE
            else:
                return RuleResult.SUCCESS
        except:
            self.algo.config.LOGGER(0, "Advanced_alg", f"Exception occurred: check_delay_gt_threshold error message is {traceback.format_exc()}")
            self.algo.log_collector.log(logging.ERROR, f"Advanced_alg, Exception occurred: check_delay_gt_threshold error message is {traceback.format_exc()}") 
            return RuleResult.FAILURE