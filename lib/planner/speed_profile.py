"""
速度剖面生成模块
根据航线几何和限制条件生成最优速度剖面
符合IMO MSC.232(82)安全航速要求
"""

from typing import List, Tuple, Optional
from dataclasses import dataclass
import numpy as np

@dataclass
class SpeedConstraint:
    """速度约束条件"""
    start_idx: int  # 起始航点索引
    end_idx: int    # 结束航点索引
    max_speed: float  # 最大速度(节)
    reason: str     # 限速原因
    
@dataclass
class SpeedProfile:
    """航线速度剖面"""
    waypoint_speeds: List[float]  # 各航点速度(节)
    segment_speeds: List[float]   # 各段平均速度(节)
    constraints: List[SpeedConstraint]  # 速度约束
    total_time: float  # 总航行时间(小时)
    
class SpeedProfileGenerator:
    """速度剖面生成器"""
    
    def __init__(self, 
                 cruise_speed: float = 15.0,
                 min_speed: float = 5.0,
                 max_speed: float = 25.0,
                 acceleration: float = 0.5,  # 节/分钟
                 deceleration: float = 1.0):  # 节/分钟
        """
        初始化速度剖面生成器
        
        Args:
            cruise_speed: 巡航速度(节)
            min_speed: 最小速度(节)
            max_speed: 最大速度(节)
            acceleration: 加速率(节/分钟)
            deceleration: 减速率(节/分钟)
        """
        self.cruise_speed = cruise_speed
        self.min_speed = min_speed
        self.max_speed = max_speed
        self.acceleration = acceleration
        self.deceleration = deceleration
    
    def generate(self, 
                waypoints: List[Tuple[float, float]],
                curvatures: Optional[List[float]] = None,
                depths: Optional[List[float]] = None,
                tss_zones: Optional[List[bool]] = None) -> SpeedProfile:
        """
        生成速度剖面
        
        Args:
            waypoints: 航点列表[(x,y),...]
            curvatures: 各点曲率(可选)
            depths: 各点水深(可选)
            tss_zones: TSS区域标记(可选)
            
        Returns:
            SpeedProfile对象
        """
        n_points = len(waypoints)
        speeds = [self.cruise_speed] * n_points
        constraints = []
        
        # 1. 曲率约束
        if curvatures:
            for i, curvature in enumerate(curvatures):
                if abs(curvature) > 0.01:  # 高曲率
                    max_speed = self._curvature_speed_limit(curvature)
                    speeds[i] = min(speeds[i], max_speed)
                    if max_speed < self.cruise_speed:
                        constraints.append(SpeedConstraint(
                            i, i, max_speed, "曲率限制"
                        ))
        
        # 2. 水深约束
        if depths:
            for i, depth in enumerate(depths):
                if depth < 20:  # 浅水
                    max_speed = self._shallow_water_speed(depth)
                    speeds[i] = min(speeds[i], max_speed)
                    if max_speed < self.cruise_speed:
                        constraints.append(SpeedConstraint(
                            i, i, max_speed, f"浅水限制(深度{depth:.1f}m)"
                        ))
        
        # 3. TSS约束
        if tss_zones:
            for i, in_tss in enumerate(tss_zones):
                if in_tss:
                    speeds[i] = min(speeds[i], 10.0)  # TSS限速10节
                    constraints.append(SpeedConstraint(
                        i, i, 10.0, "TSS限速"
                    ))
        
        # 4. 平滑速度过渡
        speeds = self._smooth_speeds(speeds, waypoints)
        
        # 5. 计算段速度和总时间
        segment_speeds = []
        total_time = 0.0
        
        for i in range(n_points - 1):
            avg_speed = (speeds[i] + speeds[i+1]) / 2.0
            segment_speeds.append(avg_speed)
            
            # 计算段长度(海里)
            dx = waypoints[i+1][0] - waypoints[i][0]
            dy = waypoints[i+1][1] - waypoints[i][1]
            distance_m = np.hypot(dx, dy)
            distance_nm = distance_m / 1852.0
            
            # 计算时间
            if avg_speed > 0:
                total_time += distance_nm / avg_speed
        
        return SpeedProfile(
            waypoint_speeds=speeds,
            segment_speeds=segment_speeds,
            constraints=constraints,
            total_time=total_time
        )
    
    def _curvature_speed_limit(self, curvature: float) -> float:
        """根据曲率计算速度限制"""
        # 经验公式: v_max = sqrt(g*R/tan(heel_angle))
        # 简化为: v_max = k / sqrt(|curvature|)
        if abs(curvature) < 1e-6:
            return self.max_speed
        
        k = 2.0  # 经验系数
        speed_mps = k / np.sqrt(abs(curvature))
        speed_kts = speed_mps * 1.944  # m/s转节
        
        return np.clip(speed_kts, self.min_speed, self.max_speed)
    
    def _shallow_water_speed(self, depth: float) -> float:
        """浅水速度限制"""
        # Froude数限制: Fr = v/sqrt(g*h) < 0.7
        if depth <= 0:
            return self.min_speed
            
        g = 9.81
        max_speed_mps = 0.7 * np.sqrt(g * depth)
        max_speed_kts = max_speed_mps * 1.944
        
        return np.clip(max_speed_kts, self.min_speed, self.max_speed)
    
    def _smooth_speeds(self, speeds: List[float], 
                      waypoints: List[Tuple[float, float]]) -> List[float]:
        """平滑速度过渡"""
        smoothed = speeds.copy()
        n = len(speeds)
        
        # 前向传播(加速约束)
        for i in range(1, n):
            dx = waypoints[i][0] - waypoints[i-1][0]
            dy = waypoints[i][1] - waypoints[i-1][1]
            distance_m = np.hypot(dx, dy)
            time_min = (distance_m / 1852.0) / smoothed[i-1] * 60  # 分钟
            
            max_increase = self.acceleration * time_min
            if smoothed[i] > smoothed[i-1] + max_increase:
                smoothed[i] = smoothed[i-1] + max_increase
        
        # 后向传播(减速约束)
        for i in range(n-2, -1, -1):
            dx = waypoints[i+1][0] - waypoints[i][0]
            dy = waypoints[i+1][1] - waypoints[i][1]
            distance_m = np.hypot(dx, dy)
            time_min = (distance_m / 1852.0) / smoothed[i] * 60
            
            max_decrease = self.deceleration * time_min
            if smoothed[i] > smoothed[i+1] + max_decrease:
                smoothed[i] = smoothed[i+1] + max_decrease
        
        return smoothed