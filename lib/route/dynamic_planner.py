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
        
        # 调试输出
        print(f"动态规划器调试: AIS目标数={len(ais_targets)}, 活跃威胁={len(current_active)}")
        if ais_targets:
            print(f"  威胁MMSI: {[t.mmsi for t in ais_targets[:5]]}")
            scenario = getattr(self.ais_manager, 'get_scenario', lambda: 'unknown')()
            print(f"  当前场景: {scenario}")
        
        # 获取基础可航区域
        try:
            region = self._get_region()
        except Exception:
            region = None
        
        if region is None:
            # 轻量级威胁规避逻辑（当没有可航区域时）
            print(f"进入轻量级逻辑: region=None, current_active={current_active}")
            self.current_dynamic_route.active_threats = current_active
            
            # 如果有威胁目标，执行简单的威胁规避
            if ais_targets:
                # 获取原始路径
                original_waypoints = self.current_dynamic_route.original_route
                if len(original_waypoints) < 2:
                    return self.current_dynamic_route
                
                # 执行轻量级威胁规避
                avoidance_waypoints = self._lightweight_threat_avoidance(
                    original_waypoints, ais_targets, current_position
                )
                
                if avoidance_waypoints and len(avoidance_waypoints) > len(original_waypoints):
                    # 更新路径为避让路径，标记避让点
                    new_waypoints = []
                    for i, (lat, lon) in enumerate(avoidance_waypoints):
                        # 原路径点不是避让点，新增的是避让点
                        is_avoidance = i >= len(original_waypoints)
                        waypoint = RouteWaypoint(
                            lat=lat, 
                            lon=lon, 
                            sog=self.own_vessel_speed,
                            is_avoidance_point=is_avoidance
                        )
                        new_waypoints.append(waypoint)
                    
                    self.current_dynamic_route.waypoints = new_waypoints
                    self.current_dynamic_route.last_update = current_time
                    print(f"轻量级威胁规避: 添加了{len(avoidance_waypoints) - len(original_waypoints)}个避让点")
            
            return self.current_dynamic_route
        
        # 计算目标点（取原始路径终点）
        goal_lat, goal_lon = self.current_dynamic_route.original_route[-1]
        
        # 单次完整规划方案：
        # 1. 保存基准路径（无AIS威胁）用于对比显示
        if not hasattr(self, '_baseline_route') or time_since_update > 30:
            # 每30秒更新一次基准路径，或首次计算
            baseline_latlon = self._plan_with_region(
                region, current_position, (goal_lat, goal_lon), motion_step=100.0
            )
            self._baseline_route = baseline_latlon
        else:
            baseline_latlon = self._baseline_route
        
        # 2. 集成AIS威胁约束，进行完整重规划
        if ais_targets:
            constrained_region = self._apply_ais_constraints(region, ais_targets, current_position)
        else:
            constrained_region = region
        
        # 3. 单次完整规划（核心改变）- 使用100m粒度平衡精度和性能
        dynamic_latlon = self._plan_with_region(
            constrained_region, 
            current_position, 
            (goal_lat, goal_lon),
            motion_step=100.0  # 100m精度，平衡精度和计算性能
        )
        
        # 如果动态规划失败，尝试轻量级威胁规避
        if not dynamic_latlon:
            print(f"完整规划失败，回退到轻量级威胁规避")
            if ais_targets:
                # 执行轻量级威胁规避
                original_waypoints = self.current_dynamic_route.original_route
                avoidance_waypoints = self._lightweight_threat_avoidance(
                    original_waypoints, ais_targets, current_position
                )
                
                if avoidance_waypoints and len(avoidance_waypoints) > len(original_waypoints):
                    # 更新路径为避让路径，标记避让点
                    new_waypoints = []
                    for i, (lat, lon) in enumerate(avoidance_waypoints):
                        is_avoidance = i >= len(original_waypoints)
                        waypoint = RouteWaypoint(
                            lat=lat, 
                            lon=lon, 
                            sog=self.own_vessel_speed,
                            is_avoidance_point=is_avoidance
                        )
                        new_waypoints.append(waypoint)
                    
                    self.current_dynamic_route.waypoints = new_waypoints
                    self.current_dynamic_route.active_threats = current_active
                    self.current_dynamic_route.last_update = current_time
                    print(f"轻量级威胁规避: 添加了{len(avoidance_waypoints) - len(original_waypoints)}个避让点")
                    return self.current_dynamic_route
            
            # 如果轻量级规避也失败，使用基准路径
            selected_latlon = baseline_latlon
        else:
            selected_latlon = dynamic_latlon
            
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

    def _lightweight_threat_avoidance(
        self, 
        original_waypoints: List[Tuple[float, float]], 
        ais_targets: List[AISTarget],
        current_position: Tuple[float, float]
    ) -> Optional[List[Tuple[float, float]]]:
        """轻量级威胁规避 - 在没有可航区域时使用的简化避让算法"""
        
        # 评估威胁
        high_risk_targets = []
        for target in ais_targets:
            # 简单的距离检查
            target_lat, target_lon = target.position
            
            # 检查威胁是否在路径附近
            for i in range(len(original_waypoints) - 1):
                seg_start = original_waypoints[i]
                seg_end = original_waypoints[i + 1]
                
                # 计算点到线段的距离
                dist_to_segment = self._point_to_segment_distance(
                    (target_lat, target_lon), seg_start, seg_end
                )
                
                # 如果威胁在路径5海里范围内，认为是高风险
                if dist_to_segment < 5.0:  # 5海里
                    high_risk_targets.append(target)
                    break
        
        if not high_risk_targets:
            return original_waypoints
        
        # 简单的避让策略：在威胁点附近添加绕行点
        avoidance_waypoints = []
        
        for i, waypoint in enumerate(original_waypoints):
            avoidance_waypoints.append(waypoint)
            
            # 检查下一段是否需要避让
            if i < len(original_waypoints) - 1:
                next_waypoint = original_waypoints[i + 1]
                
                # 检查这一段是否有威胁
                segment_threats = []
                for target in high_risk_targets:
                    dist = self._point_to_segment_distance(
                        target.position, waypoint, next_waypoint
                    )
                    if dist < 3.0:  # 3海里以内认为需要避让
                        segment_threats.append(target)
                
                # 如果有威胁，添加避让点
                if segment_threats:
                    # 选择最危险的威胁
                    main_threat = segment_threats[0]
                    
                    # 计算避让点（简单策略：向左或右偏移）
                    avoidance_point = self._calculate_simple_avoidance_point(
                        waypoint, next_waypoint, main_threat
                    )
                    
                    if avoidance_point:
                        avoidance_waypoints.append(avoidance_point)
        
        return avoidance_waypoints
    
    def _point_to_segment_distance(
        self, 
        point: Tuple[float, float], 
        seg_start: Tuple[float, float], 
        seg_end: Tuple[float, float]
    ) -> float:
        """计算点到线段的距离（海里）"""
        import math
        
        # 转换为简单的直角坐标系
        lat_avg = (seg_start[0] + seg_end[0]) / 2
        deg_to_nm_lat = 60.0
        deg_to_nm_lon = 60.0 * math.cos(math.radians(lat_avg))
        
        # 线段向量
        seg_dx = (seg_end[1] - seg_start[1]) * deg_to_nm_lon
        seg_dy = (seg_end[0] - seg_start[0]) * deg_to_nm_lat
        seg_length_sq = seg_dx**2 + seg_dy**2
        
        if seg_length_sq == 0:
            # 线段长度为0，返回点到点的距离
            dx = (point[1] - seg_start[1]) * deg_to_nm_lon
            dy = (point[0] - seg_start[0]) * deg_to_nm_lat
            return math.sqrt(dx**2 + dy**2)
        
        # 计算投影参数
        point_dx = (point[1] - seg_start[1]) * deg_to_nm_lon
        point_dy = (point[0] - seg_start[0]) * deg_to_nm_lat
        t = max(0, min(1, (point_dx * seg_dx + point_dy * seg_dy) / seg_length_sq))
        
        # 最近点
        proj_x = seg_dx * t
        proj_y = seg_dy * t
        
        # 距离
        dist_x = point_dx - proj_x
        dist_y = point_dy - proj_y
        return math.sqrt(dist_x**2 + dist_y**2)
    
    def _calculate_simple_avoidance_point(
        self, 
        seg_start: Tuple[float, float], 
        seg_end: Tuple[float, float], 
        threat: AISTarget
    ) -> Optional[Tuple[float, float]]:
        """计算简单的避让点"""
        import math
        
        # 计算航向
        course = self._calculate_course(seg_start, seg_end)
        
        # 计算中点
        mid_lat = (seg_start[0] + seg_end[0]) / 2
        mid_lon = (seg_start[1] + seg_end[1]) / 2
        
        # 根据威胁位置决定左避还是右避
        threat_bearing = self._calculate_course((mid_lat, mid_lon), threat.position)
        relative_bearing = (threat_bearing - course + 360) % 360
        
        # 如果威胁在右舷，向左避让；如果在左舷，向右避让
        if relative_bearing > 180:
            # 威胁在左舷，向右避让
            avoidance_course = (course + 90) % 360
        else:
            # 威胁在右舷，向左避让
            avoidance_course = (course - 90) % 360
        
        # 避让距离：5海里
        avoidance_distance_nm = 5.0
        avoidance_distance_deg_lat = avoidance_distance_nm / 60.0
        avoidance_distance_deg_lon = avoidance_distance_nm / (60.0 * math.cos(math.radians(mid_lat)))
        
        # 计算避让点
        avoidance_lat = mid_lat + avoidance_distance_deg_lat * math.cos(math.radians(avoidance_course))
        avoidance_lon = mid_lon + avoidance_distance_deg_lon * math.sin(math.radians(avoidance_course))
        
        return (avoidance_lat, avoidance_lon)

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
            # 增加最大迭代次数以处理长距离路径
            config = PlannerConfig(
                grid_resolution=motion_step,
                motion_step=motion_step,
                max_iterations=50000,  # 增加10倍以处理长距离
                goal_tolerance_xy=motion_step * 2  # 放宽目标容差
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