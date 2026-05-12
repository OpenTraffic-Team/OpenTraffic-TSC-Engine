from algorithms.saferules.rules.pre_rules.imports import *
from collections import Counter
from algorithms.utils.util import return_next_action_index
from algorithms.enums.algorithm_init_status import AlgorithmInitStatus
class CheckInitialPhaseRule(BaseRule):
    def __init__(self, algo=None):
        super().__init__(algo)
        self.last_timestamp = None
        self.is_timeout = False
        self.last_action = None
        self.switch_plan = False
        self.pre_plan_phases = None
        self.last_signalCtlStatus = None
        self.pending_signal_status = None
        self.need_init = False  # 标记是否需要初始化
        self.init_reason = None  # 记录触发原因
        self.init_action = None
        self.phasetime_check = False
    def execute(self, state: Dict, env_state: Dict) -> RuleResult:
        current_phase = None
        try:
            current_phase = env_state["currentPhase"]
            prev_action = -1 if self.last_action is None else self.last_action
            action = current_phase
            current_time  = env_state["timestamp"]
            phasetime = env_state['phaseTime']
            current_phases = env_state['phases']
            signal_ctl_status = int(self.algo.config.SIGNAL_IN_CONTROL) == 1

            # 信号机异常上报 currentPhase=-1，记录日志并返回 None
            if action == -1:
                msg = "Signal controller reports invalid phase (-1), possible network/IO issue"
                self.algo.config.LOGGER(0, "Advanced_alg", f"Advanced_alg, check_is_initial_phase rule, {msg}")
                self.algo.log_collector.log(logging.ERROR, f"Advanced_alg, {msg}")
                RuleResult.DATA = None
                return RuleResult.DATA

              # 检查是否需要init
            if self.last_signalCtlStatus is None:
                self.need_init = True
                self.init_reason = AlgorithmInitStatus.FIRST_RUN
                self.pending_signal_status = signal_ctl_status
            elif not self.last_signalCtlStatus and signal_ctl_status:
                self.need_init = True
                self.init_reason = AlgorithmInitStatus.GAIN_CONTROL
                self.pending_signal_status = signal_ctl_status
            elif self.last_signalCtlStatus and not signal_ctl_status:
                self.need_init = True
                self.init_reason = AlgorithmInitStatus.LOSE_CONTROL
                self.pending_signal_status = signal_ctl_status

            # 如果上一周期无有效相位（-1），当前恢复为正常相位，则需要重新初始化
            if prev_action == -1 and action != -1:
                self.need_init = True
                
                if self.init_reason is None:
                    self.init_reason = AlgorithmInitStatus.GAIN_CONTROL
                       
            #self.algo.config.PHASES = env_state['phases']
            if self.last_timestamp is not None:
                self.is_timeout, time_diff = self.check_is_timeout(self.last_timestamp,current_time) 
            self.last_timestamp = current_time
            if self.are_lists_equal(self.pre_plan_phases, current_phases):
                self.switch_plan = False
            else:
                self.pre_plan_phases = current_phases
                self.switch_plan = True
            
            # if action == 0:
            #     if self.algo.config.CITYFLOW_TEST:
            #         if self.algo.config.CURRENT_PLAN_STAGE_PHASE:
            #             first_key = next(iter(self.algo.config.CURRENT_PLAN_STAGE_PHASE))
            #             action = first_key
            #         RuleResult.DATA = action
            #         return RuleResult.DATA
            #     self.algo.log_collector.log(logging.ERROR, "Signal controller offline")
            #     return RuleResult.FAILURE
            if  self.is_timeout:
                print(f"时间差超过30秒：{time_diff}s")
                self.algo.log_collector.log(logging.WARNING, f"Advanced_alg, WARNING occurred:  check_is_initial_phase excuted data timeout:{time_diff},restarting algorithm")             
            if  self.is_timeout or self.switch_plan or self.need_init:
                if self.need_init and self.init_reason == AlgorithmInitStatus.LOSE_CONTROL:
                    RuleResult.DATA = action
                    self.algo.config.LOGGER(0, "Advanced_alg", f"Advanced_alg, check_is_initial_phase rule, signal controller exits control, maintain the original phase {action}")
                    self.finalize_signal_init_status()
                    return RuleResult.DATA
                #如果当前相位运行时间小于初始化设定时间，则保持原相位，等待初始化完成
                #TODO 如果启动阶段是过渡则需要先保持相位一致 
                # if phasetime < self.algo.config.INIT_TIME or phasetime >self.algo.config.MAX_TRANSITION_TIME or
                # env_state['transition_flag'] == 1:
                if phasetime < self.algo.config.INIT_TIME and self.phasetime_check == False:
                    RuleResult.DATA = action
                    self.algo.config.LOGGER(0, "Advanced_alg", f"Advanced_alg, check_is_initial_phase rule, The phase operation time is too short, maintain the original phase{action}, waiting for initialization")
                    return RuleResult.DATA
                else:
                    if self.init_action ==  None : 
                        # 只有当相位运行时间达到INIT_TIME时，才执行完整的初始化流程
                        self.algo.config.OVERFLOW_HISTORY.clear()
                        self.algo.config.ACTION_HISTORY.clear()
                        result = self._cycle_control(action) 
                        self.algo.config.AlgorithmStatus = AlgorithmStatus.PHASE
                        self.init_action = result
                        self.phasetime_check = True
                        RuleResult.DATA = result
                        return RuleResult.DATA
                    elif self.init_action != current_phase:
                        RuleResult.DATA = self.init_action
                        return RuleResult.DATA
                    else:
                        self.algo.config.LOGGER(0, "Advanced_alg", f"Advanced_alg, check_is_initial_phase rule, init algorithm")
                        self.algo.log_collector.log(logging.DEBUG, f"Advanced_alg, check_is_initial_phase rule, init algorithm")
                        self.algo.config.ACTION_HISTORY.append(RuleResult.DATA) 
                        self.finalize_signal_init_status()
                        # 初始化完成后，重置need_init标志，避免重复初始化
                        return RuleResult.DATA
            else:
                return RuleResult.SUCCESS
        except:
            self.algo.config.LOGGER(0, "Advanced_alg", f"Exception occurred: check_is_initial_phase error message is {traceback.format_exc()}")
            self.algo.log_collector.log(logging.ERROR, f"Advanced_alg, Exception occurred: check_is_initial_phase error message is {traceback.format_exc()}") 
            return RuleResult.FAILURE
        finally:
            # 记录上一周期信号机上报的相位（可能为-1），用于恢复检测
            if current_phase is not None:
                self.last_action = current_phase
    def are_lists_equal(self, list1, list2):
        """检查两个列表的值是否相同（顺序无关，包括重复值）"""
        return Counter(list1) == Counter(list2)
    
    def check_is_timeout(self, last_timestamp, current_time):
        return current_time - last_timestamp > 30, (current_time - last_timestamp)
    
    def finalize_signal_init_status(self):
        if self.pending_signal_status is not None:
            self.last_signalCtlStatus = self.pending_signal_status
            self.pending_signal_status = None
        self.need_init = False
        self.init_reason = None
        self.init_action = None
        self.phasetime_check = False
        