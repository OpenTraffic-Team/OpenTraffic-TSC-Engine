from algorithms.saferules.rules.pre_rules.imports import *

class CheckPersonRule(BaseRule):
    def __init__(self, algo=None):
        super().__init__(algo)
        # 保留一份最短绿时间的深拷贝，避免补偿修改全局配置
        self.min_green_time = copy.deepcopy(self.algo.config.MIN_GREEN_TIME)
        self.prePhase = 0
        self._init_variable()

    def _init_variable(self):
        self.maxPersonGreenTime = 50  #考虑行人最大时间
        self.compensated_time = 6 #补偿性时间，让行人过马路
        self.hasCompensated = False
        # 用拷贝恢复，避免引用同一个可变字典被持续抬升
        self.algo.config.MIN_GREEN_TIME = copy.deepcopy(self.min_green_time)

    
    def phase_to_person(self,currentPhase):
        directions ={'W':'E','E':'W','N':'S','S':'N'}
        phase_split = currentPhase.split('_')
        person_phase = set()
        for phase in phase_split:
            if directions[phase[0]] == phase[1]:
                person_phase.add(phase[0])
                person_phase.add(phase[1])
        return list(person_phase)

    
    def phase_person_count(self,state_run_person,current_phase):
        count = 0
        if current_phase.startswith('follow_'):
            current_phase = current_phase.replace('follow_','')
        for i in self.phase_to_person(current_phase):
            count+=state_run_person[i]
        return count
    

    
    def execute(self, state: Dict, env_state: Dict) -> RuleResult:
        try:
            if self.algo.config.CITYFLOW_TEST or self.algo.config.ALGO_STATUS is AlgorithmStatus.FOLLOW_PHASE \
                 or self.algo.config.SIGNAL_CONTROLLER_STATUS is SignalControllerStatus.OVERFLOW_PHASE:  #cityflow不考虑行人
                self.reset()
                return RuleResult.SUCCESS
            action = env_state["currentPhase"]
            if action != self.prePhase:
                self.reset()
                self.prePhase = action
            phase_time = env_state['phaseTime']
            state_run_person = state[self.algo.config.INTERSECTION]['running_person']
            phase = self.algo.config.CURRENT_PLAN_STAGE_PHASE[int(action)]
            phase_person = self.phase_person_count(state_run_person,phase)

            if phase_time > self.algo.config.MAX_KEEP_TIME[self.algo.config.CURRENT_PLAN_STAGE_PHASE[action]]:
                return RuleResult.SUCCESS
            
            if not self.hasCompensated and phase_person >= 1:
                self.algo.config.MIN_GREEN_TIME[phase] += self.compensated_time
                self.hasCompensated = True
                if self.algo.config.DEBUG:
                    self.algo.config.LOGGER(5, "Advanced_alg", f"DEBUG: check_person_rule comensated time for person,\
                                 current phase is {phase}, phase_person number is {phase_person}")
                    self.algo.log_collector.log(logging.DEBUG, f"Advanced_alg, DEBUG: check_person_rule comensated time for person,\
                                 current phase is {phase}, phase_person number is {phase_person}") 
                RuleResult.DATA = action
                return RuleResult.DATA
            if phase_person > self.algo.config.PERSON_FACTOR:
                if self.algo.config.DEBUG:
                    self.algo.config.LOGGER(5, "Advanced_alg", f"DEBUG: check_person_rule colocked phase time for person,\
                                 current phase is {phase}, phase_person number is {phase_person}")
                    self.algo.log_collector.log(logging.DEBUG, f"Advanced_alg, DEBUG: check_person_rule colocked phase time for person,\
                                 current phase is {phase}, phase_person number is {phase_person}")
                RuleResult.DATA = action
                return RuleResult.DATA
            
            return RuleResult.SUCCESS
        except:
            self.algo.config.LOGGER(0, "Advanced_alg", f"Exception occurred: CheckPersonRule error message is {traceback.format_exc()}")
            self.algo.log_collector.log(logging.ERROR, f"Advanced_alg, Exception occurred: CheckPersonRule error message is {traceback.format_exc()}")
            return RuleResult.FAILURE
        
    def reset(self):   #切相位就reset
        self._init_variable()









