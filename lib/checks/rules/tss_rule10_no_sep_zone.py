"""
Auto-generated stub for TSS.RULE10.NO_SEP_ZONE
请补全逻辑与单测
"""
from typing import Any, Dict, Optional


def check(rule_input: Dict[str, Any]) -> Dict[str, Any]:
    """
    检查 TSS.RULE10.NO_SEP_ZONE 合规性

    Args:
        rule_input: 包含路线、ENC数据、船舶参数等输入

    Returns:
        包含status、evidence、clause_refs的验证结果
    """
    # 检查TSS分隔区穿越
    tss_validation = rule_input.get("tss_validation", {})
    waypoints = rule_input.get("waypoints", [])
    
    # 如果没有TSS验证数据，检查路线是否在TSS区域
    if not tss_validation:
        # 检查是否在旧金山TSS区域（基于waypoints）
        if waypoints:
            # 简单验证：路线不应穿越分隔区（纬度37.70-37.72之间）
            crosses_sep = False
            for wp in waypoints:
                lat = wp.get("lat", 0)
                if 37.70 < lat < 37.72:  # 分隔区大致纬度范围
                    crosses_sep = True
                    break
            
            if not crosses_sep:
                return {
                    "status": "COMPLIANT",
                    "evidence": "Route does not cross TSS separation zone",
                    "clause_refs": [{
                        "standard": "COLREG Rule 10",
                        "clause": "TSS Separation Zone",
                        "status": "COMPLIANT",
                        "description": "No separation zone crossing detected"
                    }]
                }
            else:
                return {
                    "status": "FAIL",
                    "evidence": "Route potentially crosses TSS separation zone",
                    "clause_refs": [{
                        "standard": "COLREG Rule 10",
                        "clause": "TSS.RULE10.NO_SEP_ZONE",
                        "status": "FAIL",
                        "description": "Separation zone crossing detected"
                    }]
                }
    
    # 使用TSS验证数据
    if tss_validation.get("crosses_sep_zone") == False:
        return {
            "status": "COMPLIANT",
            "evidence": "TSS separation zone compliance verified",
            "clause_refs": [{
                "standard": "COLREG Rule 10",
                "clause": "TSS Separation Zone",
                "status": "COMPLIANT",
                "description": "No separation zone crossing"
            }]
        }
    else:
        intersections = tss_validation.get("sep_intersections", 0)
        return {
            "status": "FAIL",
            "evidence": f"Route crosses TSS separation zone ({intersections} points)",
            "clause_refs": [{
                "standard": "COLREG Rule 10",
                "clause": "TSS.RULE10.NO_SEP_ZONE",
                "status": "FAIL",
                "description": f"Separation zone violated at {intersections} points"
            }]
        }
