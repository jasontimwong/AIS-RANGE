"""
COLREG Rule 14 - Head-on Situation
对遇
"""
from typing import Any, Dict, Optional


def check(rule_input: Dict[str, Any]) -> Dict[str, Any]:
    """
    检查 COLREG.RULE14 合规性 - 对遇
    """
    # 获取对遇场景数据
    head_on = rule_input.get("head_on_scenario", {})
    
    if not head_on:
        return {
            "status": "COMPLIANT",
            "evidence": "No head-on situation detected",
            "clause_refs": [{
                "standard": "COLREG",
                "clause": "Rule 14",
                "status": "COMPLIANT",
                "description": "Not in head-on situation"
            }]
        }
    
    # 检查对遇避让动作（应向右转）
    action = head_on.get("action", "")
    
    if action == "alter_course_starboard" or action == "port_to_port":
        return {
            "status": "COMPLIANT",
            "evidence": "Correct head-on avoidance: altering course to starboard",
            "clause_refs": [{
                "standard": "COLREG",
                "clause": "Rule 14",
                "status": "COMPLIANT",
                "description": "Port-to-port passing arranged"
            }]
        }
    elif action == "alter_course_port":
        return {
            "status": "FAIL",
            "evidence": "Incorrect action: altering to port in head-on situation",
            "clause_refs": [{
                "standard": "COLREG",
                "clause": "Rule 14",
                "status": "FAIL",
                "description": "Must alter course to starboard"
            }]
        }
    
    return {
        "status": "WARN",
        "evidence": "Head-on situation requires action",
        "clause_refs": [{
            "standard": "COLREG",
            "clause": "Rule 14",
            "status": "WARN",
            "description": "Alter course to starboard for port-to-port passing"
        }]
    }
