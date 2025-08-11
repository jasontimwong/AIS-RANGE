"""
COLREG Rule 16 - Action by Give-way Vessel
让路船动作
"""
from typing import Any, Dict, Optional


def check(rule_input: Dict[str, Any]) -> Dict[str, Any]:
    """
    检查 COLREG.RULE16 合规性 - 让路船动作
    """
    # 获取让路船状态
    give_way_status = rule_input.get("give_way_status", {})
    
    if not give_way_status or not give_way_status.get("is_give_way", False):
        return {
            "status": "COMPLIANT",
            "evidence": "Not designated as give-way vessel",
            "clause_refs": [{
                "standard": "COLREG",
                "clause": "Rule 16",
                "status": "COMPLIANT",
                "description": "Rule 16 not applicable - not give-way vessel"
            }]
        }
    
    # 检查让路动作
    action_taken = give_way_status.get("action_taken", False)
    action_early = give_way_status.get("action_early", False)
    action_substantial = give_way_status.get("action_substantial", False)
    
    if action_taken and action_early and action_substantial:
        return {
            "status": "COMPLIANT",
            "evidence": "Early and substantial give-way action taken",
            "clause_refs": [{
                "standard": "COLREG",
                "clause": "Rule 16",
                "status": "COMPLIANT",
                "description": "Give-way vessel taking proper action"
            }]
        }
    elif action_taken but not action_early:
        return {
            "status": "WARN",
            "evidence": "Give-way action taken but may be late",
            "clause_refs": [{
                "standard": "COLREG",
                "clause": "Rule 16",
                "status": "WARN",
                "description": "Take action earlier"
            }]
        }
    
    return {
        "status": "FAIL",
        "evidence": "Give-way vessel not taking required action",
        "clause_refs": [{
            "standard": "COLREG",
            "clause": "Rule 16",
            "status": "FAIL",
            "description": "Must take early and substantial action"
        }]
    }
