"""
动态路径规划器

基于AIS数据和风险评估实时调整航线
"""

import math
from typing import List, Tuple, Optional, Dict
from dataclasses import dataclass
from datetime import datetime, timedelta

from ..ais import AISTarget, AISRiskAssessor, AISManager
from .avoidance_algorithms import COLREGAvoidance, AvoidanceAction

@dataclass 
class RouteWaypoint:
    """航路点"""
    lat: float
    lon: float
    eta: Optional[datetime] = None  # 预计到达时间
    sog: float = 15.0  # 航行速度（节）
    is_avoidance_point: bool = False  # 是否为避让点

@dataclass
class DynamicRoute:
    """动态路径"""
    waypoints: List[RouteWaypoint]
    original_route: List[Tuple[float, float]]  # 原始路径
    last_update: datetime
    active_threats: List[str]  # 活跃威胁的MMSI列表
    
class DynamicRoutePlanner:
    """动态路径规划器"""
    
    def __init__(self, ais_manager: AISManager):
        self.ais_manager = ais_manager
        self.risk_assessor = AISRiskAssessor()
        self.avoidance = COLREGAvoidance()
        
        # 规划参数
        self.own_vessel_speed = 15.0  # 本船速度（节）
        self.planning_horizon = 2.0   # 规划时域（小时）
        self.update_interval = 30     # 更新间隔（秒）
        
        # 当前动态路径
        self.current_dynamic_route: Optional[DynamicRoute] = None
        
    def initialize_route(self, original_waypoints: List[Tuple[float, float]]) -> DynamicRoute:
        """初始化动态路径"""
        waypoints = []
        current_time = datetime.utcnow()
        
        for i, (lat, lon) in enumerate(original_waypoints):
            waypoint = RouteWaypoint(
                lat=lat,
                lon=lon,
                eta=current_time + timedelta(hours=i * 0.5),  # 假设每个点间隔30分钟
                sog=self.own_vessel_speed
            )
            waypoints.append(waypoint)
        
        self.current_dynamic_route = DynamicRoute(
            waypoints=waypoints,
            original_route=original_waypoints.copy(),
            last_update=current_time,
            active_threats=[]
        )
        
        return self.current_dynamic_route
    
    def update_dynamic_route(self, current_position: Tuple[float, float]) -> Optional[DynamicRoute]:
        """更新动态路径"""
        if not self.current_dynamic_route:
            return None
        
        current_time = datetime.utcnow()
        
        # 检查是否需要更新
        if (current_time - self.current_dynamic_route.last_update).seconds < self.update_interval:
            return self.current_dynamic_route
        
        # 获取当前AIS目标
        self.ais_manager.update_targets()
        ais_targets = self.ais_manager.get_all_targets()
        
        if not ais_targets:
            return self.current_dynamic_route
        
        # 评估当前航路的风险
        route_risks = self._assess_route_risks(current_position, ais_targets)
        
        # 检查是否需要重新规划
        high_risk_segments = [risk for risk in route_risks if risk['risk_level'] in ['HIGH', 'CRITICAL']]
        
        if not high_risk_segments:
            # 无高风险，保持原路径
            return self.current_dynamic_route
        
        # 重新规划受威胁的航段
        new_route = self._replan_route(current_position, high_risk_segments, ais_targets)
        
        if new_route:
            self.current_dynamic_route = new_route
            print(f"路径已重新规划，规避 {len(high_risk_segments)} 个威胁")
        
        return self.current_dynamic_route
    
    def _assess_route_risks(
        self, 
        current_position: Tuple[float, float],
        ais_targets: List[AISTarget]
    ) -> List[Dict]:
        """评估航路风险"""
        risks = []
        waypoints = self.current_dynamic_route.waypoints
        
        # 评估从当前位置到前几个航路点的风险
        positions_to_check = [current_position]
        positions_to_check.extend([(wp.lat, wp.lon) for wp in waypoints[:5]])
        
        for i, pos in enumerate(positions_to_check[:-1]):
            next_pos = positions_to_check[i + 1]
            segment_risk = self._assess_segment_risk(pos, next_pos, ais_targets)
            
            if segment_risk:
                risks.append({
                    'segment': i,
                    'start_pos': pos,
                    'end_pos': next_pos,
                    'risk_level': segment_risk['risk_level'],
                    'threatening_targets': segment_risk['targets']
                })
        
        return risks
    
    def _assess_segment_risk(
        self,
        start_pos: Tuple[float, float],
        end_pos: Tuple[float, float], 
        ais_targets: List[AISTarget]
    ) -> Optional[Dict]:
        """评估航段风险"""
        # 计算航段中点和航向
        mid_lat = (start_pos[0] + end_pos[0]) / 2
        mid_lon = (start_pos[1] + end_pos[1]) / 2
        course = self._calculate_course(start_pos, end_pos)
        
        # 评估中点位置的风险
        assessments = self.risk_assessor.assess_risks(
            mid_lat, mid_lon, self.own_vessel_speed, course, ais_targets
        )
        
        high_risk_assessments = [
            a for a in assessments 
            if a.risk_level in ['HIGH', 'CRITICAL']
        ]
        
        if high_risk_assessments:
            return {
                'risk_level': max(a.risk_level for a in high_risk_assessments),
                'targets': [a.target for a in high_risk_assessments]
            }
        
        return None
    
    def _replan_route(
        self,
        current_position: Tuple[float, float],
        high_risk_segments: List[Dict],
        ais_targets: List[AISTarget]
    ) -> Optional[DynamicRoute]:
        """重新规划路径"""
        
        # 基于当前路径创建新路径
        new_waypoints = []
        current_time = datetime.utcnow()
        
        # 添加当前位置作为起始点
        new_waypoints.append(RouteWaypoint(
            lat=current_position[0],
            lon=current_position[1],
            eta=current_time,
            sog=self.own_vessel_speed
        ))
        
        # 处理每个高风险航段
        original_waypoints = self.current_dynamic_route.waypoints
        processed_segments = set()
        
        for risk_segment in high_risk_segments:
            if risk_segment['segment'] in processed_segments:
                continue
                
            # 为这个航段生成避让路径
            avoidance_waypoints = self._generate_avoidance_waypoints(
                risk_segment, ais_targets
            )
            
            if avoidance_waypoints:
                new_waypoints.extend(avoidance_waypoints)
                processed_segments.add(risk_segment['segment'])
        
        # 添加剩余的原始航路点
        remaining_waypoints = original_waypoints[len(processed_segments)+1:]
        for wp in remaining_waypoints:
            new_waypoints.append(wp)
        
        # 更新ETA时间
        self._update_waypoint_etas(new_waypoints)
        
        # 获取活跃威胁列表
        active_threats = []
        for segment in high_risk_segments:
            for target in segment['threatening_targets']:
                if target.mmsi not in active_threats:
                    active_threats.append(target.mmsi)
        
        return DynamicRoute(
            waypoints=new_waypoints,
            original_route=self.current_dynamic_route.original_route,
            last_update=current_time,
            active_threats=active_threats
        )
    
    def _generate_avoidance_waypoints(
        self, 
        risk_segment: Dict,
        ais_targets: List[AISTarget]
    ) -> List[RouteWaypoint]:
        """为风险航段生成避让航路点"""
        avoidance_points = []
        
        start_pos = risk_segment['start_pos']
        end_pos = risk_segment['end_pos']
        threatening_targets = risk_segment['threatening_targets']
        
        if not threatening_targets:
            return []
        
        # 选择主要威胁目标
        primary_target = threatening_targets[0]
        
        # 计算当前航向
        current_course = self._calculate_course(start_pos, end_pos)
        
        # 生成避让行动
        assessments = self.risk_assessor.assess_risks(
            start_pos[0], start_pos[1], self.own_vessel_speed, current_course, [primary_target]
        )
        
        if not assessments:
            return []
        
        actions = self.avoidance.generate_avoidance_actions(
            start_pos, current_course, self.own_vessel_speed, assessments
        )
        
        if not actions:
            return []
        
        # 基于避让行动生成航路点
        primary_action = actions[0]
        
        if primary_action.new_course:
            # 生成绕行点
            avoidance_point = self.avoidance.calculate_avoidance_waypoint(
                start_pos, end_pos, primary_target, primary_action
            )
            
            if avoidance_point:
                avoidance_points.append(RouteWaypoint(
                    lat=avoidance_point[0],
                    lon=avoidance_point[1],
                    sog=primary_action.new_speed or self.own_vessel_speed,
                    is_avoidance_point=True
                ))
        
        return avoidance_points
    
    def _calculate_course(self, start_pos: Tuple[float, float], end_pos: Tuple[float, float]) -> float:
        """计算两点间航向"""
        lat1, lon1 = math.radians(start_pos[0]), math.radians(start_pos[1])
        lat2, lon2 = math.radians(end_pos[0]), math.radians(end_pos[1])
        
        dlon = lon2 - lon1
        y = math.sin(dlon) * math.cos(lat2)
        x = math.cos(lat1) * math.sin(lat2) - math.sin(lat1) * math.cos(lat2) * math.cos(dlon)
        
        course = math.atan2(y, x)
        course = math.degrees(course)
        course = (course + 360) % 360
        
        return course
    
    def _update_waypoint_etas(self, waypoints: List[RouteWaypoint]):
        """更新航路点ETA"""
        if not waypoints:
            return
        
        current_time = waypoints[0].eta or datetime.utcnow()
        
        for i in range(1, len(waypoints)):
            prev_wp = waypoints[i-1]
            current_wp = waypoints[i]
            
            # 计算距离
            distance = self._calculate_distance(
                (prev_wp.lat, prev_wp.lon),
                (current_wp.lat, current_wp.lon)
            )
            
            # 计算航行时间
            travel_time_hours = distance / current_wp.sog
            current_wp.eta = prev_wp.eta + timedelta(hours=travel_time_hours)
    
    def _calculate_distance(self, pos1: Tuple[float, float], pos2: Tuple[float, float]) -> float:
        """计算两点间距离（海里）"""
        lat1, lon1 = math.radians(pos1[0]), math.radians(pos1[1])
        lat2, lon2 = math.radians(pos2[0]), math.radians(pos2[1])
        
        dlat = lat2 - lat1
        dlon = lon2 - lon1
        
        a = math.sin(dlat/2)**2 + math.cos(lat1) * math.cos(lat2) * math.sin(dlon/2)**2
        c = 2 * math.atan2(math.sqrt(a), math.sqrt(1-a))
        
        distance_nm = 6371 * c * 0.539957  # 转换为海里
        return distance_nm
    
    def get_route_comparison(self) -> Dict:
        """获取路径对比数据（用于前端显示）"""
        if not self.current_dynamic_route:
            return {}
        
        return {
            'original_route': self.current_dynamic_route.original_route,
            'dynamic_route': [(wp.lat, wp.lon) for wp in self.current_dynamic_route.waypoints],
            'avoidance_points': [
                (wp.lat, wp.lon) for wp in self.current_dynamic_route.waypoints 
                if wp.is_avoidance_point
            ],
            'active_threats': self.current_dynamic_route.active_threats,
            'last_update': self.current_dynamic_route.last_update.isoformat()
        }