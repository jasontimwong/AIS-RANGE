"""
COLREG Rule 17 - Action by Stand-on Vessel
直航船动作
"""
from typing import Any, Dict, Optional


def check(rule_input: Dict[str, Any]) -> Dict[str, Any]:
    """
    检查 COLREG.RULE17 合规性 - 直航船动作
    """
    # 获取直航船状态
    stand_on_status = rule_input.get("stand_on_status", {})
    
    if not stand_on_status or not stand_on_status.get("is_stand_on", False):
        return {
            "status": "COMPLIANT",
            "evidence": "Not designated as stand-on vessel",
            "clause_refs": [{
                "standard": "COLREG",
                "clause": "Rule 17",
                "status": "COMPLIANT",
                "description": "Rule 17 not applicable - not stand-on vessel"
            }]
        }
    
    # 检查是否保持航向航速
    maintaining_course = stand_on_status.get("maintaining_course", True)
    other_vessel_action = stand_on_status.get("other_vessel_taking_action", True)
    
    if maintaining_course and other_vessel_action:
        return {
            "status": "COMPLIANT",
            "evidence": "Stand-on vessel maintaining course and speed",
            "clause_refs": [{
                "standard": "COLREG",
                "clause": "Rule 17",
                "status": "COMPLIANT",
                "description": "Correctly maintaining course as stand-on vessel"
            }]
        }
    elif not other_vessel_action:
        # 对方未采取行动，本船可能需要采取行动
        return {
            "status": "WARN",
            "evidence": "Other vessel not taking action - may need to take action",
            "clause_refs": [{
                "standard": "COLREG",
                "clause": "Rule 17(b)",
                "status": "WARN",
                "description": "May take action if other vessel not complying"
            }]
        }
    
    return {
        "status": "FAIL",
        "evidence": "Stand-on vessel not maintaining course and speed",
        "clause_refs": [{
            "standard": "COLREG",
            "clause": "Rule 17",
            "status": "FAIL",
            "description": "Must maintain course and speed as stand-on vessel"
        }]
    }
