import setup_path
import json 

class Spec_Ctl:
    def __init__(self, config_str):
        config = json.loads(config_str)
        self.lock_phase = config['locked_phase']

    def convert_cur_state(self, localLaneInfo: dict):       
        return {}
    

    def convert_neighbor_state(self, state: dict):
        return {}

    def take_action(self, state, env_state) -> int:       
        return self.lock_phase