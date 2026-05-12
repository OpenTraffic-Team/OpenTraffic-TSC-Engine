from algorithms.saferules.rules.pre_rules.imports import *

class CheckMinGreenTimeRule(BaseRule):
    def __init__(self, algo=None):
        super().__init__(algo)
        
    def execute(self, state: Dict, env_state: Dict) -> RuleResult:
        try:
            phase_keep = env_state["phaseTime"]
            action = env_state["currentPhase"]
            #子相位最短绿
            if self.algo.config.SIGNAL_CONTROLLER_STATUS is SignalControllerStatus.FOLLOW_PHASE:
                if phase_keep < 20:  
                    RuleResult.DATA = action
                    return RuleResult.DATA
                else:
                    return RuleResult.SUCCESS
            #溢出相位最短绿
            elif self.algo.config.SIGNAL_CONTROLLER_STATUS is SignalControllerStatus.OVERFLOW_PHASE:
                if phase_keep < self.algo.config.OVERFLOW_MIN_GREEN_TIME: 
                    RuleResult.DATA = action
                    return RuleResult.DATA
                else:
                    return RuleResult.SUCCESS
            else:
                    # 普通相位最短绿
                if phase_keep < self.algo.config.MIN_GREEN_TIME[self.algo.config.CURRENT_PLAN_STAGE_PHASE[int(action)]]:
                    # 如果当前动作是历史最后一个动作，或者是第一个动作（历史为空），或者是只监不控状态，则执行当前动作
                    #这样写的目的是防止过了最短绿后，进入选择阶段，选择了新的相位，并进入高峰期
                    # 但是下一论在最短绿逻辑里最短绿规则变成高峰期的规则，导致出现A->B->A的情况,
                    # 所以需要判断当前动作是否是历史最后一个动作，或者是第一个动作（历史为空），也就是当前相位是否是新相位
                    # 只监不控状态存在当前相位和上一个不同，要满足最短绿规则
                    if not self.algo.config.ACTION_HISTORY \
                        or action == self.algo.config.ACTION_HISTORY[-1] \
                            or int(self.algo.config.SIGNAL_IN_CONTROL) == 0:
                        RuleResult.DATA = action
                        return RuleResult.DATA
                    else:
                        return RuleResult.SUCCESS
                else:
                    return RuleResult.SUCCESS
              
        except:
            print(action)
            self.algo.config.LOGGER(0, "Advanced_alg", f"Exception occurred: check_is_min_green_time error message is {traceback.format_exc()}")
            self.algo.log_collector.log(logging.ERROR, f"Advanced_alg, Exception occurred: check_is_min_green_time error message is {traceback.format_exc()}") 
            return RuleResult.FAILURE