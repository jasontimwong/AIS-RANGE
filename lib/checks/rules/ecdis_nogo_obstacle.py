"""
ECDIS No-Go Area and Obstacle Avoidance
危险物/禁航区避让
"""
from typing import Any, Dict, Optional


def check(rule_input: Dict[str, Any]) -> Dict[str, Any]:
    """
    检查 ECDIS.NOGO_OBSTACLE 合规性
    """
    # 获取危险物和禁航区数据
    obstacles = rule_input.get("obstacles", [])
    nogo_areas = rule_input.get("nogo_areas", [])
    route = rule_input.get("waypoints", [])
    
    # 检查是否有危险物
    if not obstacles and not nogo_areas:
        return {
            "status": "COMPLIANT",
            "evidence": "No obstacles or no-go areas identified",
            "clause_refs": [{
                "standard": "IMO/IEC/IHO",
                "clause": "ECDIS Safety",
                "status": "COMPLIANT",
                "description": "Clear of all obstacles and no-go areas"
            }]
        }
    
    # 检查路线是否避开危险物
    violations = []
    
    for obstacle in obstacles:
        min_clearance = obstacle.get("min_clearance_nm", float('inf'))
        if min_clearance < 0.5:  # 小于0.5海里认为太近
            violations.append(f"{obstacle.get('name', 'obstacle')} ({min_clearance:.1f}nm)")
    
    for nogo in nogo_areas:
        if nogo.get("route_intersects", False):
            violations.append(f"No-go area: {nogo.get('name', 'restricted area')}")
    
    if not violations:
        return {
            "status": "COMPLIANT",
            "evidence": "All obstacles and no-go areas avoided",
            "clause_refs": [{
                "standard": "IMO/IEC/IHO",
                "clause": "ECDIS Safety",
                "status": "COMPLIANT",
                "description": "Safe clearance from all hazards"
            }]
        }
    else:
        return {
            "status": "FAIL",
            "evidence": f"Route too close to: {', '.join(violations)}",
            "clause_refs": [{
                "standard": "IMO/IEC/IHO",
                "clause": "ECDIS.NOGO_OBSTACLE",
                "status": "FAIL",
                "description": "Insufficient clearance from hazards"
            }]
        }
