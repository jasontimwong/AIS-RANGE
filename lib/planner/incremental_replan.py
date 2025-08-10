"""
增量重规划模块
实现局部代价更新和局部搜索，优化重规划性能
"""

import logging
import time
from typing import Optional, Tuple, List, Set, Dict
from dataclasses import dataclass
import numpy as np
from heapq import heappush, heappop

from lib.planner.hybrid_astar import HybridAStar, PlannerConfig, Route, Node
from lib.region.feasible_region import FeasibleRegion

logger = logging.getLogger(__name__)


@dataclass
class ChangeEvent:
    """变更事件"""
    type: str  # 'obstacle_added', 'obstacle_removed', 'goal_changed', 'cost_changed'
    location: Optional[Tuple[float, float]] = None
    radius: Optional[float] = None
    old_value: Optional[any] = None
    new_value: Optional[any] = None


@dataclass
class DirtyRegion:
    """脏区域（需要重新计算的区域）"""
    min_x: float
    min_y: float
    max_x: float
    max_y: float
    
    def contains(self, x: float, y: float) -> bool:
        """检查点是否在脏区域内"""
        return self.min_x <= x <= self.max_x and self.min_y <= y <= self.max_y
    
    def expand(self, margin: float):
        """扩展脏区域"""
        self.min_x -= margin
        self.min_y -= margin
        self.max_x += margin
        self.max_y += margin


class IncrementalReplanner:
    """增量重规划器"""
    
    def __init__(self, config: PlannerConfig, region: FeasibleRegion):
        """
        初始化增量重规划器
        
        Args:
            config: 规划配置
            region: 可行域
        """
        self.config = config
        self.region = region
        self.base_planner = HybridAStar(config, region)
        
        # 缓存状态
        self.current_route: Optional[Route] = None
        self.cached_nodes: Dict[Tuple, Node] = {}
        self.dirty_regions: List[DirtyRegion] = []
        
        # 性能统计
        self.stats = {
            'full_replans': 0,
            'incremental_replans': 0,
            'cache_hits': 0,
            'cache_misses': 0,
            'total_time': 0.0,
            'avg_time': 0.0
        }
    
    def plan_initial(self, start: Tuple[float, float, float], 
                    goal: Tuple[float, float, Optional[float]],
                    initial_velocity: float = 10.0) -> Optional[Route]:
        """
        执行初始规划
        
        Args:
            start: 起点 (x, y, heading)
            goal: 终点 (x, y, heading_optional)
            initial_velocity: 初始速度
            
        Returns:
            规划的路径
        """
        logger.info("执行初始路径规划")
        
        start_time = time.time()
        route = self.base_planner.plan(start, goal, initial_velocity)
        elapsed = time.time() - start_time
        
        if route:
            self.current_route = route
            self._cache_route_nodes(route)
            logger.info(f"初始规划成功: {len(route.waypoints)} 航点, 耗时 {elapsed:.3f}s")
        else:
            logger.warning("初始规划失败")
        
        self.stats['full_replans'] += 1
        self.stats['total_time'] += elapsed
        self._update_avg_time()
        
        return route
    
    def replan_incremental(self, changes: List[ChangeEvent],
                          new_start: Optional[Tuple] = None,
                          new_goal: Optional[Tuple] = None) -> Optional[Route]:
        """
        执行增量重规划
        
        Args:
            changes: 变更事件列表
            new_start: 新起点（如果有）
            new_goal: 新终点（如果有）
            
        Returns:
            重规划的路径
        """
        if not self.current_route:
            logger.warning("无当前路径，执行完整规划")
            return self._fallback_to_full_replan(new_start, new_goal)
        
        logger.info(f"执行增量重规划: {len(changes)} 个变更")
        start_time = time.time()
        
        # 1. 识别脏区域
        dirty_regions = self._identify_dirty_regions(changes)
        
        # 2. 检查是否需要完整重规划
        if self._needs_full_replan(dirty_regions, new_start, new_goal):
            logger.info("变更过大，回退到完整重规划")
            return self._fallback_to_full_replan(new_start, new_goal)
        
        # 3. 执行局部修复
        repaired_route = self._local_repair(dirty_regions, new_start, new_goal)
        
        elapsed = time.time() - start_time
        
        if repaired_route:
            self.current_route = repaired_route
            self._cache_route_nodes(repaired_route)
            logger.info(f"增量重规划成功: 耗时 {elapsed:.3f}s")
            
            self.stats['incremental_replans'] += 1
            self.stats['total_time'] += elapsed
            self._update_avg_time()
            
            return repaired_route
        else:
            logger.warning("增量重规划失败，回退到完整重规划")
            return self._fallback_to_full_replan(new_start, new_goal)
    
    def _identify_dirty_regions(self, changes: List[ChangeEvent]) -> List[DirtyRegion]:
        """识别脏区域"""
        dirty_regions = []
        
        for change in changes:
            if change.type in ['obstacle_added', 'obstacle_removed']:
                if change.location and change.radius:
                    # 创建脏区域
                    region = DirtyRegion(
                        min_x=change.location[0] - change.radius,
                        min_y=change.location[1] - change.radius,
                        max_x=change.location[0] + change.radius,
                        max_y=change.location[1] + change.radius
                    )
                    # 扩展一定裕度
                    region.expand(self.config.grid_resolution * 2)
                    dirty_regions.append(region)
            
            elif change.type == 'cost_changed':
                # 代价变化影响更大区域
                if change.location:
                    region = DirtyRegion(
                        min_x=change.location[0] - self.config.grid_resolution * 5,
                        min_y=change.location[1] - self.config.grid_resolution * 5,
                        max_x=change.location[0] + self.config.grid_resolution * 5,
                        max_y=change.location[1] + self.config.grid_resolution * 5
                    )
                    dirty_regions.append(region)
        
        # 合并重叠的脏区域
        merged = self._merge_dirty_regions(dirty_regions)
        self.dirty_regions = merged
        
        return merged
    
    def _merge_dirty_regions(self, regions: List[DirtyRegion]) -> List[DirtyRegion]:
        """合并重叠的脏区域"""
        if len(regions) <= 1:
            return regions
        
        merged = []
        used = set()
        
        for i, r1 in enumerate(regions):
            if i in used:
                continue
            
            # 查找所有重叠的区域
            min_x, min_y = r1.min_x, r1.min_y
            max_x, max_y = r1.max_x, r1.max_y
            
            for j, r2 in enumerate(regions[i+1:], i+1):
                if j in used:
                    continue
                
                # 检查重叠
                if not (r2.max_x < min_x or r2.min_x > max_x or
                       r2.max_y < min_y or r2.min_y > max_y):
                    # 合并
                    min_x = min(min_x, r2.min_x)
                    min_y = min(min_y, r2.min_y)
                    max_x = max(max_x, r2.max_x)
                    max_y = max(max_y, r2.max_y)
                    used.add(j)
            
            merged.append(DirtyRegion(min_x, min_y, max_x, max_y))
            used.add(i)
        
        return merged
    
    def _needs_full_replan(self, dirty_regions: List[DirtyRegion],
                          new_start: Optional[Tuple],
                          new_goal: Optional[Tuple]) -> bool:
        """判断是否需要完整重规划"""
        # 起点或终点变化较大
        if new_start or new_goal:
            if new_start and self._distance(new_start[:2], 
                                          self.current_route.waypoints[0]) > self.config.grid_resolution * 10:
                return True
            if new_goal and self._distance(new_goal[:2], 
                                         self.current_route.waypoints[-1]) > self.config.grid_resolution * 10:
                return True
        
        # 脏区域过多
        if len(dirty_regions) > 5:
            return True
        
        # 脏区域过大
        total_dirty_area = sum((r.max_x - r.min_x) * (r.max_y - r.min_y) 
                              for r in dirty_regions)
        
        # 计算路径边界框
        xs = [wp[0] for wp in self.current_route.waypoints]
        ys = [wp[1] for wp in self.current_route.waypoints]
        route_area = (max(xs) - min(xs)) * (max(ys) - min(ys))
        
        if total_dirty_area > route_area * 0.3:  # 超过30%需要重算
            return True
        
        # 检查关键航点是否在脏区域
        affected_waypoints = 0
        for wp in self.current_route.waypoints:
            for region in dirty_regions:
                if region.contains(wp[0], wp[1]):
                    affected_waypoints += 1
                    break
        
        if affected_waypoints > len(self.current_route.waypoints) * 0.5:
            return True
        
        return False
    
    def _local_repair(self, dirty_regions: List[DirtyRegion],
                     new_start: Optional[Tuple],
                     new_goal: Optional[Tuple]) -> Optional[Route]:
        """执行局部修复"""
        logger.debug(f"执行局部修复: {len(dirty_regions)} 个脏区域")
        
        # 找出受影响的航段
        affected_segments = self._find_affected_segments(dirty_regions)
        
        if not affected_segments:
            # 无需修复
            return self.current_route
        
        # 构建修复后的路径
        repaired_waypoints = []
        repaired_headings = []
        repaired_velocities = []
        
        wp_index = 0
        for seg_start, seg_end in affected_segments:
            # 保留未受影响的部分
            while wp_index < seg_start:
                repaired_waypoints.append(self.current_route.waypoints[wp_index])
                repaired_headings.append(self.current_route.headings[wp_index])
                repaired_velocities.append(self.current_route.velocities[wp_index])
                wp_index += 1
            
            # 重规划受影响的段
            segment_start = self.current_route.waypoints[seg_start]
            segment_goal = self.current_route.waypoints[min(seg_end, 
                                                           len(self.current_route.waypoints)-1)]
            
            # 局部搜索
            local_route = self._local_search(
                (segment_start[0], segment_start[1], self.current_route.headings[seg_start]),
                (segment_goal[0], segment_goal[1], None),
                max_iterations=500  # 限制迭代次数
            )
            
            if local_route:
                # 添加局部路径（跳过重复的起点）
                for i, wp in enumerate(local_route.waypoints[1:], 1):
                    repaired_waypoints.append(wp)
                    if i < len(local_route.headings):
                        repaired_headings.append(local_route.headings[i])
                    if i < len(local_route.velocities):
                        repaired_velocities.append(local_route.velocities[i])
            else:
                # 局部搜索失败，返回None触发完整重规划
                return None
            
            wp_index = seg_end + 1
        
        # 添加剩余部分
        while wp_index < len(self.current_route.waypoints):
            repaired_waypoints.append(self.current_route.waypoints[wp_index])
            if wp_index < len(self.current_route.headings):
                repaired_headings.append(self.current_route.headings[wp_index])
            if wp_index < len(self.current_route.velocities):
                repaired_velocities.append(self.current_route.velocities[wp_index])
            wp_index += 1
        
        # 创建修复后的路径
        repaired_route = Route(repaired_waypoints, repaired_headings, repaired_velocities)
        repaired_route.total_cost = self._calculate_route_cost(repaired_route)
        
        return repaired_route
    
    def _find_affected_segments(self, dirty_regions: List[DirtyRegion]) -> List[Tuple[int, int]]:
        """找出受影响的航段"""
        affected = []
        current_segment = None
        
        for i, wp in enumerate(self.current_route.waypoints):
            is_affected = False
            for region in dirty_regions:
                if region.contains(wp[0], wp[1]):
                    is_affected = True
                    break
            
            if is_affected:
                if current_segment is None:
                    current_segment = [i, i]
                else:
                    current_segment[1] = i
            else:
                if current_segment is not None:
                    # 扩展边界
                    current_segment[0] = max(0, current_segment[0] - 1)
                    current_segment[1] = min(len(self.current_route.waypoints) - 1,
                                           current_segment[1] + 1)
                    affected.append(tuple(current_segment))
                    current_segment = None
        
        if current_segment is not None:
            current_segment[0] = max(0, current_segment[0] - 1)
            current_segment[1] = min(len(self.current_route.waypoints) - 1,
                                   current_segment[1] + 1)
            affected.append(tuple(current_segment))
        
        return affected
    
    def _local_search(self, start: Tuple, goal: Tuple, 
                     max_iterations: int = 500) -> Optional[Route]:
        """执行局部搜索"""
        # 创建临时配置（减少搜索范围）
        local_config = PlannerConfig(
            grid_resolution=self.config.grid_resolution,
            motion_step=self.config.motion_step,
            max_iterations=max_iterations,
            goal_tolerance_xy=self.config.goal_tolerance_xy * 2  # 放宽容差
        )
        
        # 使用缓存的节点作为启发
        local_planner = HybridAStar(local_config, self.region)
        
        # 注入缓存节点
        for key, node in self.cached_nodes.items():
            if self._distance(key[:2], start[:2]) < self.config.grid_resolution * 10:
                # 在局部搜索范围内
                if key not in local_planner.visited:
                    # visited是set，只记录访问
                    local_planner.visited.add(key)
                    self.stats['cache_hits'] += 1
        
        # 执行局部搜索
        route = local_planner.plan(start, goal, initial_velocity=10.0)
        
        if not route:
            self.stats['cache_misses'] += 1
        
        return route
    
    def _fallback_to_full_replan(self, new_start: Optional[Tuple],
                                new_goal: Optional[Tuple]) -> Optional[Route]:
        """回退到完整重规划"""
        # 使用新的起点/终点或保持原有的
        start = new_start if new_start else self.current_route.waypoints[0]
        goal = new_goal if new_goal else self.current_route.waypoints[-1]
        
        # 添加航向信息
        if len(start) == 2:
            start = (start[0], start[1], 0.0)
        if len(goal) == 2:
            goal = (goal[0], goal[1], None)
        
        start_time = time.time()
        route = self.base_planner.plan(start, goal, initial_velocity=10.0)
        elapsed = time.time() - start_time
        
        self.stats['full_replans'] += 1
        self.stats['total_time'] += elapsed
        self._update_avg_time()
        
        if route:
            self.current_route = route
            self._cache_route_nodes(route)
        
        return route
    
    def _cache_route_nodes(self, route: Route):
        """缓存路径节点"""
        # 清理旧缓存
        if len(self.cached_nodes) > 10000:
            self.cached_nodes.clear()
        
        # 缓存新节点
        for i, wp in enumerate(route.waypoints):
            if i < len(route.headings):
                key = (wp[0], wp[1], route.headings[i])
                node = Node(wp[0], wp[1], route.headings[i])
                node.g = i * self.config.motion_step  # 估算代价
                self.cached_nodes[key] = node
    
    def _calculate_route_cost(self, route: Route) -> float:
        """计算路径代价"""
        cost = 0.0
        for i in range(len(route.waypoints) - 1):
            dist = self._distance(route.waypoints[i], route.waypoints[i+1])
            cost += dist
        return cost
    
    def _distance(self, p1: Tuple, p2: Tuple) -> float:
        """计算两点距离"""
        return np.sqrt((p1[0] - p2[0])**2 + (p1[1] - p2[1])**2)
    
    def _update_avg_time(self):
        """更新平均时间"""
        total_replans = self.stats['full_replans'] + self.stats['incremental_replans']
        if total_replans > 0:
            self.stats['avg_time'] = self.stats['total_time'] / total_replans
    
    def get_performance_stats(self) -> Dict:
        """获取性能统计"""
        return self.stats.copy()
    
    def reset(self):
        """重置规划器状态"""
        self.current_route = None
        self.cached_nodes.clear()
        self.dirty_regions.clear()
        
        # 保留统计信息