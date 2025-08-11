"""
COLREG Rule 7 - Risk of Collision Assessment
碰撞危险评估
"""
from typing import Any, Dict, Optional


def check(rule_input: Dict[str, Any]) -> Dict[str, Any]:
    """
    检查 COLREG.RULE7 合规性 - 碰撞危险评估
    """
    # 获取CPA/TCPA数据
    cpa_tcpa = rule_input.get("cpa_tcpa", {})
    other_vessels = rule_input.get("other_vessels", [])
    
    if not other_vessels:
        return {
            "status": "COMPLIANT",
            "evidence": "No other vessels detected - no collision risk",
            "clause_refs": [{
                "standard": "COLREG",
                "clause": "Rule 7",
                "status": "COMPLIANT",
                "description": "Collision risk assessment performed"
            }]
        }
    
    # 检查是否有碰撞风险
    min_cpa = cpa_tcpa.get("min_cpa_nm", float('inf'))
    min_tcpa = cpa_tcpa.get("min_tcpa_min", float('inf'))
    
    if min_cpa < 0.5 or min_tcpa < 10:  # 高风险阈值
        return {
            "status": "WARN",
            "evidence": f"Collision risk detected: CPA={min_cpa:.1f}nm, TCPA={min_tcpa:.1f}min",
            "clause_refs": [{
                "standard": "COLREG",
                "clause": "Rule 7",
                "status": "WARN",
                "description": "High collision risk - action required"
            }]
        }
    
    return {
        "status": "COMPLIANT",
        "evidence": f"Collision risk assessed: CPA={min_cpa:.1f}nm, TCPA={min_tcpa:.1f}min",
        "clause_refs": [{
            "standard": "COLREG",
            "clause": "Rule 7",
            "status": "COMPLIANT",
            "description": "Collision risk within safe limits"
        }]
    }
