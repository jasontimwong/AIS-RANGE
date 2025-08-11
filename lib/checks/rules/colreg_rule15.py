"""
COLREG Rule 15 - Crossing Situation
交叉
"""
from typing import Any, Dict, Optional


def check(rule_input: Dict[str, Any]) -> Dict[str, Any]:
    """
    检查 COLREG.RULE15 合规性 - 交叉
    """
    # 获取交叉场景数据
    crossing = rule_input.get("crossing_scenario", {})
    
    if not crossing:
        return {
            "status": "COMPLIANT",
            "evidence": "No crossing situation detected",
            "clause_refs": [{
                "standard": "COLREG",
                "clause": "Rule 15",
                "status": "COMPLIANT",
                "description": "Not in crossing situation"
            }]
        }
    
    # 检查让路义务
    other_vessel_bearing = crossing.get("other_vessel_bearing", 0)
    give_way = crossing.get("give_way", False)
    
    # 右舷来船，本船应让路
    if 0 < other_vessel_bearing < 112.5 and give_way:
        return {
            "status": "COMPLIANT",
            "evidence": "Give-way vessel in crossing - taking avoidance action",
            "clause_refs": [{
                "standard": "COLREG",
                "clause": "Rule 15",
                "status": "COMPLIANT",
                "description": "Give-way obligations fulfilled"
            }]
        }
    elif 0 < other_vessel_bearing < 112.5 and not give_way:
        return {
            "status": "FAIL",
            "evidence": "Failed to give way to vessel on starboard",
            "clause_refs": [{
                "standard": "COLREG",
                "clause": "Rule 15",
                "status": "FAIL",
                "description": "Must give way to vessel on starboard"
            }]
        }
    
    return {
        "status": "COMPLIANT",
        "evidence": "Stand-on vessel in crossing situation",
        "clause_refs": [{
            "standard": "COLREG",
            "clause": "Rule 15",
            "status": "COMPLIANT",
            "description": "Maintaining course and speed as stand-on vessel"
        }]
    }
