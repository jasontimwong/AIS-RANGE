"""
COLREG Rule 8 - Action to Avoid Collision
避免碰撞措施
"""
from typing import Any, Dict, Optional


def check(rule_input: Dict[str, Any]) -> Dict[str, Any]:
    """
    检查 COLREG.RULE8 合规性 - 避免碰撞措施
    """
    # 获取避让动作
    avoidance_action = rule_input.get("avoidance_action", {})
    cpa_tcpa = rule_input.get("cpa_tcpa", {})
    
    if not avoidance_action:
        # 检查是否需要避让
        min_cpa = cpa_tcpa.get("min_cpa_nm", float('inf'))
        if min_cpa < 1.0:
            return {
                "status": "WARN",
                "evidence": "No avoidance action planned for close encounter",
                "clause_refs": [{
                    "standard": "COLREG",
                    "clause": "Rule 8",
                    "status": "WARN",
                    "description": "Avoidance action may be required"
                }]
            }
        return {
            "status": "COMPLIANT",
            "evidence": "No avoidance action required - safe passing distance",
            "clause_refs": [{
                "standard": "COLREG",
                "clause": "Rule 8",
                "status": "COMPLIANT",
                "description": "Safe passing distance maintained"
            }]
        }
    
    # 验证避让动作是否充分
    action_type = avoidance_action.get("type", "")
    action_magnitude = avoidance_action.get("magnitude", 0)
    
    if action_type in ["course_change", "speed_reduction"] and action_magnitude >= 10:
        return {
            "status": "COMPLIANT",
            "evidence": f"Substantial {action_type} of {action_magnitude} degrees/knots",
            "clause_refs": [{
                "standard": "COLREG",
                "clause": "Rule 8",
                "status": "COMPLIANT",
                "description": "Substantial and effective avoidance action"
            }]
        }
    
    return {
        "status": "WARN",
        "evidence": "Avoidance action may not be substantial enough",
        "clause_refs": [{
            "standard": "COLREG",
            "clause": "Rule 8",
            "status": "WARN",
            "description": "Consider more substantial action"
        }]
    }
