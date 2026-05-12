from algorithms.saferules.rules.pre_rules.imports import *
from datetime import datetime

class CheckTransitionRule(BaseRule):
    def __init__(self, algo=None):
        super().__init__(algo)
        self.transition_start_time = None  # 记录开始满足条件的时间

    def execute(self, state: Dict, env_state: Dict) -> RuleResult:
        try:        

            # 如果算法是跟随相位状态，信号机是子相位状态，则需要过渡。
            # 如果算法是父相位状态，信号机是父相位状态，也需过渡

            #如果算法状态是跟随相位状态或信号机是溢出相位状态，表示当前不是过渡
            if self.algo.config.ALGO_STATUS is AlgorithmStatus.FOLLOW_PHASE \
                or self.algo.config.SIGNAL_CONTROLLER_STATUS is SignalControllerStatus.OVERFLOW_PHASE or int(self.algo.config.SIGNAL_IN_CONTROL) == 0:
                # 条件不满足时，重置开始时间
                self.transition_start_time = None
                return RuleResult.SUCCESS
                
            prev_action = -1
            if len(self.algo.config.ACTION_HISTORY) > 0:
                prev_action = self.algo.config.ACTION_HISTORY[-1]
            currentPhase = env_state['currentPhase']
            if prev_action != -1 and prev_action != currentPhase:
                current_datetime = env_state['timestamp']
                
                # 如果是第一次满足条件，记录开始时间
                if self.transition_start_time is None:
                    self.transition_start_time = current_datetime
                else:
                    # 检查持续时间是否超过9秒
                    duration = current_datetime - self.transition_start_time
                    if duration > self.algo.config.MAX_TRANSITION_DURATION:
                        # 持续报错，不重置时间，这样只要条件持续满足就会持续报错
                        error_msg = f"Transition EXCEPTION: {duration:.3f}s, prev_action={prev_action}, currentPhase={currentPhase}"
                        self.algo.config.LOGGER(0, "Advanced_alg", f"ERROR: {error_msg}")
                        self.algo.log_collector.log(logging.ERROR, f"Advanced_alg, ERROR: {error_msg}")
                        # 不重置时间，保持持续报错直到条件不再满足
                        return RuleResult.FAILURE
                
                
                # 记录日志
                if self.algo.config.DEBUG:
                    self.algo.config.LOGGER(5, "Advanced_alg", f"DEBUG: check_is_transition env_state is {env_state}")
                    self.algo.log_collector.log(logging.DEBUG, f"Advanced_alg, DEBUG: check_is_transition env_state is {env_state}")
                RuleResult.DATA = prev_action 
                return RuleResult.DATA 
            else:
                # 条件不满足时，重置开始时间
                self.transition_start_time = None
                return RuleResult.SUCCESS
        except:
            self.algo.config.LOGGER(0, "Advanced_alg", f"Exception occurred: transition error, error message is {traceback.format_exc()}")
            self.algo.log_collector.log(logging.ERROR, f"Advanced_alg, Exception occurred: transition error message is {traceback.format_exc()}")
            return RuleResult.FAILURE