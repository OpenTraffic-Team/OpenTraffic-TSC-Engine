from algorithms.saferules.compositors.compositor import Compositor
from algorithms.saferules.rules.post_rules.check_algo_status_rule import CheckAlgoStatus
from typing import Dict
class PostSafeRules:
    def __init__(self, algo=None):
        
        self.safe_excutor = Compositor(
            #算法状态检查
            CheckAlgoStatus(algo)
        )
       

    def excute_rules_chain(self, state: Dict, env_state: Dict, action):
            
        return self.safe_excutor.verify(state, env_state, action)