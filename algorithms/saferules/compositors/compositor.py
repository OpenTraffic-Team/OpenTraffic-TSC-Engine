
from typing import Dict

from algorithms.saferules.compositors.base_compoistor import BaseCompositor
from algorithms.saferules.rules.base_rule import BaseRule
from algorithms.saferules.rules.rule_result import RuleResult

import logging
class Compositor(BaseCompositor):
    def __init__(self, *rules: BaseRule):
        super().__init__(*rules)

    def get_rule(self, rule_type):
        """查找并返回指定类型的规则"""
        for rule in self.rules:
            if isinstance(rule, rule_type):
                return rule
        return None  # 如果没找到，返回 None


    def evaluate(self, state: Dict, env_state: Dict) -> RuleResult:
        for rule in self.rules:
            result = rule.execute(state, env_state)
            if result is RuleResult.SUCCESS:
                pass
            elif result is RuleResult.FAILURE:
                if rule.algo.config.DEBUG:  
                    rule.algo.config.LOGGER(0,"Advanced_alg", f"Exception occurred: check rule: {str(rule.__class__.__name__)} error")
                    rule.algo.log_collector.log(logging.ERROR,f"Advanced_alg, Exception occurred: check rule: {str(rule.__class__.__name__)} error")
                return result
            else:
                if rule.algo.config.DEBUG:
                    rule.algo.config.LOGGER(5,"Advanced_alg", f"Rule: {str(rule.__class__.__name__)} success return {str(result)}")
                    rule.algo.log_collector.log(logging.DEBUG,f"Advanced_alg, Rule: {str(rule.__class__.__name__)} success return {str(result)}")
                return result
        return RuleResult.SUCCESS
    
    def verify(self, state: Dict, env_state: Dict, action=None) -> RuleResult:
        for rule in self.rules:
            result = rule.execute(state, env_state, action)
            if result is RuleResult.SUCCESS:
                pass
            elif result is RuleResult.FAILURE:
                if rule.algo.config.DEBUG:  
                    rule.algo.config.LOGGER(0,"Advanced_alg", f"Exception occurred: check rule: {str(rule.__class__.__name__)} error")
                    rule.algo.log_collector.log(logging.ERROR,f"Advanced_alg, Exception occurred: check rule: {str(rule.__class__.__name__)} error")
                return result
            else:
                if rule.algo.config.DEBUG:
                    rule.algo.config.LOGGER(5,"Advanced_alg", f"Rule: {str(rule.__class__.__name__)} success return {str(result)}")
                    rule.algo.log_collector.log(logging.DEBUG,f"Advanced_alg, Rule: {str(rule.__class__.__name__)} success return {str(result)}")
                return result
        return RuleResult.SUCCESS
    

        
        
 