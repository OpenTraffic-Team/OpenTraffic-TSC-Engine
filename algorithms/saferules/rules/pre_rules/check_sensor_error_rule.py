from algorithms.saferules.rules.pre_rules.imports import *

class CheckSensorErrorRule(BaseRule):
    def __init__(self, algo=None):
        super().__init__(algo)

    def execute(self, state: Dict, env_state: Dict) -> RuleResult:
        try:
            if self.algo.config.CITYFLOW_TEST:
                return RuleResult.SUCCESS

            camera_state = state[self.algo.config.INTERSECTION]['cameraState']
            zero_count = sum(1 for key in camera_state if camera_state[key] == 1)
      
            camera_valid = zero_count == 0
            if camera_valid is not True:
                self.algo.config.LOGGER(0, "Advanced_alg", f"Exception occurred: check_camera_is_error error, camera state is {camera_state}") 
                self.algo.log_collector.log(logging.ERROR, f"Advanced_alg, Exception occurred: check_camera_is_error camera state is {camera_state}")
                return RuleResult.FAILURE
            else:
                return RuleResult.SUCCESS
        except:
            self.algo.config.LOGGER(0, "Advanced_alg", f"Exception occurred: check_camera_is_error error message is {traceback.format_exc()}")
            self.algo.log_collector.log(logging.ERROR, f"Advanced_alg, Exception occurred: check_camera_is_error error message is {traceback.format_exc()}")
            return RuleResult.FAILURE