from algorithms.saferules.rules.pre_rules.imports import *

class CheckSensorFrequentDelayRule(BaseRule):
    def __init__(self, algo=None):
        super().__init__(algo)
        self.error_time = 0

    def execute(self, state: Dict[str, Dict[str, int]], env_state: Dict) -> RuleResult:
        try:
            if self.algo.config.CITYFLOW_TEST:
                return RuleResult.SUCCESS
            action = env_state["currentPhase"]
            targetTimestep = env_state['timestamp']
            #TODO 改成固定时长
            if self.error_time > 65:
                self.algo.config.LOGGER(0, "Advanced_alg", f"Exception occurred: check_camera_frequent_delay error, error_time is {self.error_time}") 
                self.algo.log_collector.log(logging.ERROR, f"Advanced_alg, Exception occurred: check_camera_frequent_delay error, error_time is {self.error_time}")
                return RuleResult.FAILURE
            # 判断相机异常
            # 若是传输延迟
            nowTimestep = state[self.algo.config.INTERSECTION]['timestamp']
            sensor_delay_time = abs(nowTimestep - targetTimestep)
            if sensor_delay_time >= self.algo.config.DELAY_TIME and sensor_delay_time <= self.algo.config.DELAY_TIME + 1:
                self.error_time += 1
            else:
                self.error_time = 0
            return RuleResult.SUCCESS
        except:
            self.algo.config.LOGGER(0, "Advanced_alg", f"Exception occurred: check_camera_frequent_delay error message is {traceback.format_exc()}")
            self.algo.log_collector.log(logging.ERROR, f"Advanced_alg, Exception occurred: check_camera_frequent_delay error message is {traceback.format_exc()}")
            return RuleResult.FAILURE