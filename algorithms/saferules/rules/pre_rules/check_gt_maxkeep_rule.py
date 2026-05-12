from algorithms.saferules.rules.pre_rules.imports import *

class CheckIsGtMaxkeepRule(BaseRule):
    def __init__(self, algo=None):
        super().__init__(algo)
        #self.max_keep_time = self.algo.config.MAX_KEEP_TIME

    def execute(self, state: Dict, env_state: Dict) -> RuleResult:
        try:
            phase_keep = env_state["phaseTime"]
            action = env_state["currentPhase"]
            if phase_keep >= self.algo.config.MAX_KEEP_TIME[self.algo.config.CURRENT_PLAN_STAGE_PHASE[action]]:
                # 先执行未执行的相位/主从关系再执行周期
                if self.algo.config.SIGNAL_CONTROLLER_STATUS is SignalControllerStatus.FOLLOW_PHASE:
                    # 当前是跟随相位：返回对应的 master 相位（非 follow）
                    master = self.algo.config.FOLLOW_MASTER_PHASE_DICT[self.algo.config.CURRENT_PLAN_STAGE_PHASE[action]]
                    master_action = self.algo.config.CURRENT_PLAN_PHASE_TO_NUMBER[master]
                    result = self._excute_remain_phases(master_action)  
                    if result != master_action and result is not RuleResult.SUCCESS:  
                        return result
                    else:
                        return self._cycle_control(master_action)
                else:
                    if self.algo.config.MASTER_FOLLOW_PHASE_DICT[self.algo.config.CURRENT_PLAN_STAGE_PHASE[action]]:
                        # 当前是 master 且存在跟随相位：直接返回该 master 的第一个 follow 相位
                        master_phase_name = self.algo.config.CURRENT_PLAN_STAGE_PHASE[action]
                        follow_list = self.algo.config.MASTER_FOLLOW_PHASE_DICT[master_phase_name]
                        first_follow_name = follow_list[0]
                        if first_follow_name in self.algo.config.CURRENT_PLAN_PHASE_TO_NUMBER:
                            follow_action = self.algo.config.CURRENT_PLAN_PHASE_TO_NUMBER[first_follow_name]
                            RuleResult.DATA = follow_action
                            self.algo.config.PRE_FOLLOW_PHASE = follow_action
                            return RuleResult.DATA
                        else:
                            return None
                    else:
                        result = self._excute_remain_phases(action)        
                        if self.algo.config.DEBUG:
                            self.algo.config.LOGGER(5, "Advanced_alg", f"DEBUG: check_is_gt_maxkeep env_state is {env_state}, remain unexcute phase is {result}") 
                            self.algo.log_collector.log(logging.DEBUG, f"Advanced_alg, DEBUG: check_is_gt_maxkeep env_state is {env_state}, remain unexcute phase is {result}") 
                        if result is not RuleResult.SUCCESS:
                            return result
                        else:
                            return self._cycle_control(action)
            else:
                return RuleResult.SUCCESS
        except:
            self.algo.config.LOGGER(0, "Advanced_alg", f"Exception occurred: check_is_gt_maxkeep error message is {traceback.format_exc()}")
            self.algo.log_collector.log(logging.ERROR, f"Advanced_alg, Exception occurred: check_is_gt_maxkeep error message is {traceback.format_exc()}") 
            return RuleResult.FAILURE

   