"""
COLREG Rule 13 - Overtaking
追越
"""
from typing import Any, Dict, Optional


def check(rule_input: Dict[str, Any]) -> Dict[str, Any]:
    """
    检查 COLREG.RULE13 合规性 - 追越
    """
    # 获取追越场景数据
    overtaking = rule_input.get("overtaking_scenario", {})
    
    if not overtaking:
        return {
            "status": "COMPLIANT",
            "evidence": "No overtaking situation detected",
            "clause_refs": [{
                "standard": "COLREG",
                "clause": "Rule 13",
                "status": "COMPLIANT",
                "description": "Not in overtaking situation"
            }]
        }
    
    # 检查追越方向和距离
    overtaking_side = overtaking.get("side", "")
    clearance = overtaking.get("clearance_nm", 0)
    
    if overtaking_side and clearance >= 0.5:
        return {
            "status": "COMPLIANT",
            "evidence": f"Overtaking on {overtaking_side} with {clearance:.1f}nm clearance",
            "clause_refs": [{
                "standard": "COLREG",
                "clause": "Rule 13",
                "status": "COMPLIANT",
                "description": "Safe overtaking with adequate clearance"
            }]
        }
    
    return {
        "status": "WARN",
        "evidence": "Insufficient clearance for overtaking",
        "clause_refs": [{
            "standard": "COLREG",
            "clause": "Rule 13",
            "status": "WARN",
            "description": "Increase clearance when overtaking"
        }]
    }
