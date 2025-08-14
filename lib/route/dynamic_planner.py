"""
动态路径规划器

基于AIS数据和风险评估实时调整航线
"""

import math
from typing import List, Tuple, Optional, Dict, Callable
from dataclasses import dataclass
from datetime import datetime, timedelta

from ..ais import AISTarget, AISRiskAssessor, AISManager
from .avoidance_algorithms import COLREGAvoidance, AvoidanceAction
from lib.planner.hybrid_astar import HybridAStar, PlannerConfig
from lib.region.feasible_region import FeasibleRegion
from shapely.geometry import Point
from shapely.ops import unary_union
from shapely.geometry import LineString

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
    
    def __init__(self, ais_manager: AISManager,
                 get_feasible_region: Optional[Callable[[], Optional[FeasibleRegion]]] = None,
                 get_planner_config: Optional[Callable[[], Optional[object]]] = None):
        self.ais_manager = ais_manager
        self.risk_assessor = AISRiskAssessor()
        self.avoidance = COLREGAvoidance()
        self._get_region = get_feasible_region or (lambda: None)
        self._get_planner_cfg = get_planner_config or (lambda: None)
        
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
        """更新动态路径 - 完整重规划实现"""
        if not self.current_dynamic_route:
            return None
        
        current_time = datetime.utcnow()
        
        # 检查是否需要更新
        time_since_update = (current_time - self.current_dynamic_route.last_update).seconds
        if time_since_update < 1 and self.current_dynamic_route.active_threats:
            return self.current_dynamic_route
        
        # 获取当前AIS目标
        self.ais_manager.update_targets()
        ais_targets = self.ais_manager.get_all_targets()
        
        # 更新活跃威胁列表
        current_active = [t.mmsi for t in ais_targets][:10]
        
        # 获取基础可航区域
        try:
            region = self._get_region()
        except Exception:
            region = None
        
        if region is None:
            # 回退到轻量级逻辑
            self.current_dynamic_route.active_threats = current_active
            return self.current_dynamic_route
        
        # 计算目标点（取原始路径终点）
        goal_lat, goal_lon = self.current_dynamic_route.original_route[-1]
        
        # 单次完整规划方案：
        # 1. 保存基准路径（无AIS威胁）用于对比显示
        if not hasattr(self, '_baseline_route') or time_since_update > 30:
            # 每30秒更新一次基准路径，或首次计算
            baseline_latlon = self._plan_with_region(
                region, current_position, (goal_lat, goal_lon), motion_step=50.0
            )
            self._baseline_route = baseline_latlon
        else:
            baseline_latlon = self._baseline_route
        
        # 2. 集成AIS威胁约束，进行完整重规划
        if ais_targets:
            constrained_region = self._apply_ais_constraints(region, ais_targets, current_position)
        else:
            constrained_region = region
        
        # 3. 单次完整规划（核心改变）- 使用50m统一粒度
        dynamic_latlon = self._plan_with_region(
            constrained_region, 
            current_position, 
            (goal_lat, goal_lon),
            motion_step=50.0  # 统一高精度
        )
        
        # 如果动态规划失败，使用基准路径
        selected_latlon = dynamic_latlon or baseline_latlon
        if not selected_latlon:
            return self.current_dynamic_route
        
        # 4. 直接构建路径，无需后处理加密
        new_waypoints = [
            RouteWaypoint(lat=lat, lon=lon, sog=self.own_vessel_speed)
            for (lat, lon) in selected_latlon
        ]
        
        # 5. 返回更新后的动态路径
        self.current_dynamic_route = DynamicRoute(
            waypoints=new_waypoints,
            original_route=baseline_latlon or self.current_dynamic_route.original_route,
            last_update=current_time,
            active_threats=current_active
        )
        
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
            if a.cpa_result.risk_level in ['MEDIUM', 'HIGH', 'CRITICAL']
        ]
        
        if high_risk_assessments:
            return {
                'risk_level': max(a.cpa_result.risk_level for a in high_risk_assessments),
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

    def _plan_with_region(self, region: FeasibleRegion, start_latlon: Tuple[float, float], 
                         goal_latlon: Tuple[float, float], motion_step: float = 50.0) -> Optional[List[Tuple[float, float]]]:
        """使用Hybrid A*在给定可航区域内规划，返回(lat, lon) 轨迹。
        
        Args:
            region: 可航区域
            start_latlon: 起点 (lat, lon)
            goal_latlon: 终点 (lat, lon)
            motion_step: 路径点间距（米）
        """
        try:
            # 简化投影：与服务端一致的近似
            import math
            lat_avg = (start_latlon[0] + goal_latlon[0]) / 2.0
            m_per_deg_lat = 111320.0
            m_per_deg_lon = 111320.0 * math.cos(math.radians(lat_avg))
            sx = start_latlon[1] * m_per_deg_lon
            sy = start_latlon[0] * m_per_deg_lat
            gx = goal_latlon[1] * m_per_deg_lon
            gy = goal_latlon[0] * m_per_deg_lat
            
            # 使用统一的50m粒度配置
            config = PlannerConfig(
                grid_resolution=motion_step,
                motion_step=motion_step,
                max_iterations=5000,
                goal_tolerance_xy=motion_step
            )
            planner = HybridAStar(config, region)
            
            # 使用motion_step_override参数进行规划
            route = planner.plan(
                (sx, sy, 0.0), 
                (gx, gy, None), 
                initial_velocity=self.own_vessel_speed * 0.514444,
                motion_step_override=motion_step
            )
            
            if not route:
                return None
                
            # 直接用与投影一致的反变换返回lat,lon
            latlon_list: List[Tuple[float, float]] = []
            for (x, y) in route.waypoints:
                lat = y / m_per_deg_lat
                lon = x / m_per_deg_lon
                latlon_list.append((lat, lon))
            return latlon_list
        except Exception as e:
            import traceback
            print(f"Planning error: {e}")
            traceback.print_exc()
            return None


    def _build_ais_mask_union(self, targets: List[AISTarget], current_position: Tuple[float, float]):
        """构建AIS威胁mask的并集（米坐标系）。"""
        import math
        lat0 = current_position[0]
        m_per_deg_lat = 111320.0
        m_per_deg_lon = 111320.0 * math.cos(math.radians(lat0))
        try:
            scenario = getattr(self.ais_manager, 'get_scenario', lambda: 'default')()
        except Exception:
            scenario = 'default'
        base_scale = 1.0 if scenario != 'aggressive' else 2.0
        assessments = self.risk_assessor.assess_risks(current_position[0], current_position[1], self.own_vessel_speed, 0.0, targets)
        risk_by_mmsi = {}
        for a in assessments:
            lvl = getattr(a.cpa_result, 'risk_level', 'LOW')
            w = 0.0
            if lvl == 'HIGH': w = 1.0
            elif lvl == 'MEDIUM': w = 0.6
            elif lvl == 'LOW': w = 0.3
            risk_by_mmsi[getattr(a.target, 'mmsi', None)] = w
        buffers = []
        for t in targets:
            sog = getattr(t, 'sog', 10.0)
            risk_w = risk_by_mmsi.get(getattr(t, 'mmsi', None), 0.0)
            speed_amp = 1.0 + 0.02 * max(0.0, sog - 10.0)
            risk_amp = 1.0 + 1.0 * risk_w
            radius_m = max(300.0, min(1500.0, sog * 50.0)) * base_scale * speed_amp * risk_amp
            x = t.position[1] * m_per_deg_lon  # lon
            y = t.position[0] * m_per_deg_lat  # lat
            buffers.append(Point(x, y).buffer(radius_m))
        return unary_union(buffers) if buffers else None

    def _apply_ais_constraints(self, region: FeasibleRegion, targets: List[AISTarget], current_position: Tuple[float, float]) -> FeasibleRegion:
        """将AIS威胁集成为约束，返回受约束的可航区域。
        
        Args:
            region: 原始可航区域
            targets: AIS目标列表
            current_position: 当前位置
            
        Returns:
            包含AIS威胁约束的新可航区域
        """
        mask = self._build_ais_mask_union(targets, current_position)
        navigable = region.navigable_area
        
        if mask and not mask.is_empty:
            try:
                navigable_masked = navigable.difference(mask)
            except Exception:
                navigable_masked = navigable
        else:
            navigable_masked = navigable
            
        return FeasibleRegion(
            bounds=region.bounds,
            no_go_areas=region.no_go_areas,
            navigable_area=navigable_masked if isinstance(navigable_masked, type(region.navigable_area)) else region.navigable_area,
            depth_contours=region.depth_contours,
            danger_zones=region.danger_zones,
            restricted_areas=region.restricted_areas,
            tss_zones=region.tss_zones
        )
    
    def _apply_ais_masks(self, region: FeasibleRegion, targets: List[AISTarget], current_position: Tuple[float, float]):
        """保留兼容性的包装方法"""
        return self._apply_ais_constraints(region, targets, current_position), None

    
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
        
        def _length_nm(latlon: List[Tuple[float, float]]) -> float:
            if not latlon or len(latlon) < 2:
                return 0.0
            total = 0.0
            for i in range(len(latlon) - 1):
                total += self._calculate_distance(latlon[i], latlon[i+1])
            return total

        original_latlon = self.current_dynamic_route.original_route
        dynamic_latlon = [(wp.lat, wp.lon) for wp in self.current_dynamic_route.waypoints]
        original_len_nm = _length_nm(original_latlon)
        dynamic_len_nm = _length_nm(dynamic_latlon)
        delta_len_nm = max(0.0, dynamic_len_nm - original_len_nm)

        return {
            'original_route': original_latlon,
            'dynamic_route': dynamic_latlon,
            'avoidance_points': [
                (wp.lat, wp.lon) for wp in self.current_dynamic_route.waypoints 
                if wp.is_avoidance_point
            ],
            'active_threats': self.current_dynamic_route.active_threats,
            'last_update': self.current_dynamic_route.last_update.isoformat(),
            'original_distance_nm': original_len_nm,
            'dynamic_distance_nm': dynamic_len_nm,
            'delta_distance_nm': delta_len_nm
        }