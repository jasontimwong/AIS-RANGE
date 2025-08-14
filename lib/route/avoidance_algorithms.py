"""
COLREG避让算法实现

基于国际海上避碰规则(COLREG)实现船舶避让算法
"""

import math
from typing import List, Tuple, Optional
from dataclasses import dataclass
from ..ais import AISTarget, RiskAssessment

@dataclass
class AvoidanceAction:
    """避让行动"""
    action_type: str  # 'course_change', 'speed_change', 'waypoint_insert'
    description: str
    new_course: Optional[float] = None
    new_speed: Optional[float] = None
    new_waypoint: Optional[Tuple[float, float]] = None
    priority: int = 1  # 1=高优先级, 2=中等, 3=低优先级

class COLREGAvoidance:
    """COLREG避让算法"""
    
    def __init__(self):
        self.min_cpa_distance = 0.5  # 最小CPA距离（海里）
        self.avoidance_distance = 2.0  # 避让距离（海里）
        
    def generate_avoidance_actions(
        self, 
        own_position: Tuple[float, float],
        own_course: float,
        own_speed: float,
        risk_assessments: List[RiskAssessment]
    ) -> List[AvoidanceAction]:
        """生成避让行动方案"""
        actions = []
        
        # 按风险优先级排序
        high_risk_assessments = [
            assessment for assessment in risk_assessments 
            if assessment.cpa_result.risk_level in ['HIGH', 'CRITICAL', 'MEDIUM']
        ]
        
        for assessment in high_risk_assessments:
            action = self._generate_single_avoidance(
                own_position, own_course, own_speed, assessment
            )
            if action:
                actions.append(action)
        
        return actions
    
    def _generate_single_avoidance(
        self,
        own_position: Tuple[float, float], 
        own_course: float,
        own_speed: float,
        assessment: RiskAssessment
    ) -> Optional[AvoidanceAction]:
        """为单个目标生成避让行动"""
        
        target = assessment.target
        encounter_type = assessment.encounter_type
        
        from ..ais.risk_assessor import EncounterType
        
        if encounter_type == EncounterType.HEAD_ON:
            # 对遇：向右转
            return self._head_on_avoidance(own_position, own_course, target)
        elif encounter_type == EncounterType.CROSSING_GIVE_WAY:
            # 交叉让路：我船需避让
            return self._crossing_avoidance(own_position, own_course, target)
        elif encounter_type == EncounterType.OVERTAKING:
            # 追越：追越船避让
            return self._overtaking_avoidance(own_position, own_course, target)
        
        return None
    
    def _head_on_avoidance(
        self, 
        own_position: Tuple[float, float],
        own_course: float, 
        target: AISTarget
    ) -> AvoidanceAction:
        """对遇避让：向右转"""
        # COLREG Rule 14: 对遇时，两船都应向右转
        new_course = (own_course + 15) % 360  # 向右转15度
        
        return AvoidanceAction(
            action_type='course_change',
            description=f'对遇局面：向右转避让 {target.name}',
            new_course=new_course,
            priority=1
        )
    
    def _crossing_avoidance(
        self, 
        own_position: Tuple[float, float],
        own_course: float, 
        target: AISTarget
    ) -> AvoidanceAction:
        """交叉避让：让路船转向"""
        # COLREG Rule 15: 交叉局面中，右舷来船有路权
        # 计算目标相对方位
        relative_bearing = self._calculate_relative_bearing(own_position, target.position)
        
        if 0 <= relative_bearing <= 112.5:
            # 目标在右舷，我船让路，向右转
            new_course = (own_course + 20) % 360
            action_desc = f'交叉让路：向右转避让 {target.name}'
        else:
            # 目标在左舷，我船有路权，但仍需谨慎
            new_course = own_course
            action_desc = f'交叉直航：保持航向，监视 {target.name}'
        
        return AvoidanceAction(
            action_type='course_change',
            description=action_desc,
            new_course=new_course,
            priority=1 if new_course != own_course else 2
        )
    
    def _overtaking_avoidance(
        self, 
        own_position: Tuple[float, float],
        own_course: float, 
        target: AISTarget
    ) -> AvoidanceAction:
        """追越避让"""
        # COLREG Rule 13: 追越船应避让被追越船
        # 简单实现：向右转或减速
        if target.sog < 10:  # 目标速度较慢，可以转向
            new_course = (own_course + 25) % 360
            return AvoidanceAction(
                action_type='course_change',
                description=f'追越避让：向右转超越 {target.name}',
                new_course=new_course,
                priority=2
            )
        else:  # 减速避让
            return AvoidanceAction(
                action_type='speed_change',
                description=f'追越避让：减速避让 {target.name}',
                new_speed=8.0,  # 减速至8节
                priority=2
            )
    
    def calculate_avoidance_waypoint(
        self,
        current_pos: Tuple[float, float],
        next_waypoint: Tuple[float, float],
        target: AISTarget,
        avoidance_action: AvoidanceAction
    ) -> Optional[Tuple[float, float]]:
        """计算避让航路点"""
        
        if avoidance_action.action_type != 'course_change':
            return None
        
        # 计算到目标的距离和方位
        distance_to_target = self._calculate_distance(current_pos, target.position)
        
        # 对于高风险目标，即使距离较远也要生成避让点
        # 距离检查改为基于实际需要，而不是简单的10海里限制
        
        # 在当前位置和下一个航路点之间插入避让点
        # 使用新的航向计算避让点
        new_course = avoidance_action.new_course
        avoidance_distance = min(distance_to_target + self.avoidance_distance, 5.0)
        
        # 计算避让点位置
        new_lat = current_pos[0] + (avoidance_distance / 60) * math.cos(math.radians(new_course))
        new_lon = current_pos[1] + (avoidance_distance / 60) * math.sin(math.radians(new_course)) / math.cos(math.radians(current_pos[0]))
        
        return (new_lat, new_lon)
    
    def _calculate_relative_bearing(
        self, 
        own_pos: Tuple[float, float], 
        target_pos: Tuple[float, float]
    ) -> float:
        """计算相对方位（度）"""
        lat1, lon1 = math.radians(own_pos[0]), math.radians(own_pos[1])
        lat2, lon2 = math.radians(target_pos[0]), math.radians(target_pos[1])
        
        dlon = lon2 - lon1
        y = math.sin(dlon) * math.cos(lat2)
        x = math.cos(lat1) * math.sin(lat2) - math.sin(lat1) * math.cos(lat2) * math.cos(dlon)
        
        bearing = math.atan2(y, x)
        bearing = math.degrees(bearing)
        bearing = (bearing + 360) % 360
        
        return bearing
    
    def _calculate_distance(
        self, 
        pos1: Tuple[float, float], 
        pos2: Tuple[float, float]
    ) -> float:
        """计算两点间距离（海里）"""
        lat1, lon1 = math.radians(pos1[0]), math.radians(pos1[1])
        lat2, lon2 = math.radians(pos2[0]), math.radians(pos2[1])
        
        dlat = lat2 - lat1
        dlon = lon2 - lon1
        
        a = math.sin(dlat/2)**2 + math.cos(lat1) * math.cos(lat2) * math.sin(dlon/2)**2
        c = 2 * math.atan2(math.sqrt(a), math.sqrt(1-a))
        
        # 地球半径 * 弧度转换为海里
        distance_nm = 6371 * c * 0.539957  # 转换为海里
        return distance_nm