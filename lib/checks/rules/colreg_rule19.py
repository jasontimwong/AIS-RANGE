"""
COLREG Rule 19 - Conduct in Restricted Visibility
能见度不良时的行动
"""
from typing import Any, Dict, Optional


def check(rule_input: Dict[str, Any]) -> Dict[str, Any]:
    """
    检查 COLREG.RULE19 合规性 - 能见度不良
    """
    # 获取能见度数据
    visibility = rule_input.get("visibility", {})
    vessel = rule_input.get("vessel", {})
    
    visibility_nm = visibility.get("visibility_nm", 10.0)
    fog_signal = visibility.get("fog_signal_active", False)
    radar_on = visibility.get("radar_on", True)
    safe_speed = visibility.get("safe_speed", True)
    
    # 能见度良好，规则不适用
    if visibility_nm > 3.0:
        return {
            "status": "COMPLIANT",
            "evidence": f"Good visibility ({visibility_nm:.1f}nm) - Rule 19 not applicable",
            "clause_refs": [{
                "standard": "COLREG",
                "clause": "Rule 19",
                "status": "COMPLIANT",
                "description": "Not in restricted visibility"
            }]
        }
    
    # 能见度不良检查
    issues = []
    if not fog_signal:
        issues.append("fog signals not active")
    if not radar_on:
        issues.append("radar not operational")
    if not safe_speed:
        issues.append("speed not reduced")
    
    if not issues:
        return {
            "status": "COMPLIANT",
            "evidence": f"Restricted visibility ({visibility_nm:.1f}nm) procedures followed",
            "clause_refs": [{
                "standard": "COLREG",
                "clause": "Rule 19",
                "status": "COMPLIANT",
                "description": "All restricted visibility requirements met"
            }]
        }
    else:
        return {
            "status": "FAIL",
            "evidence": f"Restricted visibility violations: {', '.join(issues)}",
            "clause_refs": [{
                "standard": "COLREG",
                "clause": "Rule 19",
                "status": "FAIL",
                "description": f"Must address: {', '.join(issues)}"
            }]
        }
