"""
Auto-generated stub for SPD.LIMITS
请补全逻辑与单测
"""
from typing import Any, Dict, Optional


def check(rule_input: Dict[str, Any]) -> Dict[str, Any]:
    """
    检查 SPD.LIMITS 合规性

    Args:
        rule_input: 包含路线、ENC数据、船舶参数等输入

    Returns:
        包含status、evidence、clause_refs的验证结果
    """
    # 检查速度限制合规性
    speed_limits = rule_input.get("speed_limits", {})
    vessel = rule_input.get("vessel", {})
    waypoints = rule_input.get("waypoints", [])
    
    # 获取船舶计划速度
    planned_speed = vessel.get("speed_kts", 15.0)
    
    # 检查是否有速度限制区域
    if speed_limits:
        max_allowed = speed_limits.get("max_speed_kts", float('inf'))
        zone_name = speed_limits.get("zone_name", "Speed restricted area")
        
        if planned_speed > max_allowed:
            return {
                "status": "FAIL",
                "evidence": f"Planned speed {planned_speed}kts exceeds limit {max_allowed}kts in {zone_name}",
                "clause_refs": [{
                    "standard": "S-124",
                    "clause": "Speed Restriction",
                    "status": "FAIL",
                    "description": f"Speed limit violation in {zone_name}"
                }]
            }
        else:
            return {
                "status": "COMPLIANT",
                "evidence": f"Speed {planned_speed}kts within limit {max_allowed}kts",
                "clause_refs": [{
                    "standard": "S-124",
                    "clause": "Speed Restriction",
                    "status": "COMPLIANT",
                    "description": "Speed limits observed"
                }]
            }
    
    # 默认速度限制检查（旧金山湾区域）
    if waypoints:
        # 检查是否在港口区域（简化检查）
        in_port_area = any(
            37.70 <= wp.get("lat", 0) <= 37.85 and 
            -122.50 >= wp.get("lon", 0) >= -122.90 
            for wp in waypoints
        )
        
        if in_port_area:
            port_speed_limit = 10.0  # 港口区域限速10节
            if planned_speed > port_speed_limit:
                return {
                    "status": "WARN",
                    "evidence": f"Speed {planned_speed}kts may exceed port area recommendations",
                    "clause_refs": [{
                        "standard": "Local Regulations",
                        "clause": "Port Speed Limit",
                        "status": "WARN",
                        "description": "Consider reducing speed in port area"
                    }]
                }
    
    return {
        "status": "COMPLIANT",
        "evidence": "No speed restrictions identified for the route",
        "clause_refs": [{
            "standard": "S-124",
            "clause": "Speed Limits",
            "status": "COMPLIANT",
            "description": "No speed limit violations detected"
        }]
    }
