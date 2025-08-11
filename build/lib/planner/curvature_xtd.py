"""
曲率和XTD(Cross-Track Distance)计算模块
计算航线曲率和横向偏移距离，用于航线优化
符合IMO航线规划标准
"""

from typing import List, Tuple, Optional
import numpy as np
from shapely.geometry import LineString, Point

class CurvatureXTDCalculator:
    """曲率和XTD计算器"""
    
    def __init__(self, safety_xtd: float = 185.2):  # 0.1海里
        """
        初始化计算器
        
        Args:
            safety_xtd: 安全横向偏离距离(米)
        """
        self.safety_xtd = safety_xtd
    
    def calculate_curvatures(self, waypoints: List[Tuple[float, float]]) -> List[float]:
        """
        计算航线各点曲率
        
        Args:
            waypoints: 航点列表[(x,y),...]
            
        Returns:
            各点曲率列表
        """
        n = len(waypoints)
        if n < 3:
            return [0.0] * n
        
        curvatures = []
        
        # 第一个点
        curvatures.append(self._point_curvature(
            waypoints[0], waypoints[0], waypoints[1], waypoints[2]
        ))
        
        # 中间点
        for i in range(1, n-1):
            k = self._point_curvature(
                waypoints[i-1], waypoints[i], waypoints[i+1], 
                waypoints[min(i+2, n-1)]
            )
            curvatures.append(k)
        
        # 最后一个点
        curvatures.append(self._point_curvature(
            waypoints[n-3], waypoints[n-2], waypoints[n-1], waypoints[n-1]
        ))
        
        return curvatures
    
    def _point_curvature(self, p0: Tuple[float, float], 
                        p1: Tuple[float, float],
                        p2: Tuple[float, float], 
                        p3: Tuple[float, float]) -> float:
        """
        使用四点法计算p1点的曲率
        """
        # 三点圆曲率计算
        x1, y1 = p0
        x2, y2 = p1
        x3, y3 = p2
        
        # 避免共线
        area = abs((x2-x1)*(y3-y1) - (x3-x1)*(y2-y1))
        if area < 1e-10:
            return 0.0
        
        # 三边长度
        a = np.hypot(x2-x1, y2-y1)
        b = np.hypot(x3-x2, y3-y2)
        c = np.hypot(x3-x1, y3-y1)
        
        if a < 1e-6 or b < 1e-6 or c < 1e-6:
            return 0.0
        
        # 曲率 = 4*面积/(a*b*c)
        curvature = 4 * area / (a * b * c)
        
        # 判断凹凸性(叉积)
        cross = (x2-x1)*(y3-y2) - (y2-y1)*(x3-x2)
        if cross < 0:
            curvature = -curvature
        
        return curvature
    
    def calculate_xtd(self, position: Tuple[float, float],
                     route: LineString) -> float:
        """
        计算位置到航线的横向偏离距离
        
        Args:
            position: 当前位置(x,y)
            route: 航线LineString
            
        Returns:
            XTD距离(米)，左负右正
        """
        point = Point(position)
        distance = point.distance(route)
        
        # 判断左右侧
        # 找最近点所在的线段
        closest_point = route.interpolate(route.project(point))
        
        # 获取最近线段
        for i in range(len(route.coords) - 1):
            seg = LineString([route.coords[i], route.coords[i+1]])
            if seg.distance(point) < 1e-6:
                # 计算叉积判断左右
                x1, y1 = route.coords[i]
                x2, y2 = route.coords[i+1]
                px, py = position
                
                cross = (x2-x1)*(py-y1) - (y2-y1)*(px-x1)
                if cross < 0:
                    distance = -distance
                break
        
        return distance
    
    def check_xtd_violation(self, waypoints: List[Tuple[float, float]],
                           safety_margin: Optional[float] = None) -> List[int]:
        """
        检查XTD违规点
        
        Args:
            waypoints: 航点列表
            safety_margin: 安全边距(默认使用初始化值)
            
        Returns:
            违规航点索引列表
        """
        if safety_margin is None:
            safety_margin = self.safety_xtd
        
        violations = []
        route = LineString(waypoints)
        
        # 检查每个航点的局部XTD
        for i in range(1, len(waypoints) - 1):
            # 创建局部直线段
            straight_line = LineString([waypoints[i-1], waypoints[i+1]])
            
            # 计算中间点到直线的距离
            xtd = self.calculate_xtd(waypoints[i], straight_line)
            
            if abs(xtd) > safety_margin:
                violations.append(i)
        
        return violations
    
    def smooth_route_curvature(self, waypoints: List[Tuple[float, float]],
                              max_curvature: float = 0.01) -> List[Tuple[float, float]]:
        """
        平滑航线曲率
        
        Args:
            waypoints: 原始航点
            max_curvature: 最大允许曲率
            
        Returns:
            平滑后的航点
        """
        smoothed = waypoints.copy()
        curvatures = self.calculate_curvatures(smoothed)
        
        # 迭代平滑高曲率点
        max_iterations = 10
        for _ in range(max_iterations):
            modified = False
            
            for i in range(1, len(smoothed) - 1):
                if abs(curvatures[i]) > max_curvature:
                    # 使用加权平均平滑
                    x_prev, y_prev = smoothed[i-1]
                    x_next, y_next = smoothed[i+1]
                    
                    # 新位置 = 0.5*当前 + 0.25*前 + 0.25*后
                    new_x = 0.5 * smoothed[i][0] + 0.25 * x_prev + 0.25 * x_next
                    new_y = 0.5 * smoothed[i][1] + 0.25 * y_prev + 0.25 * y_next
                    
                    smoothed[i] = (new_x, new_y)
                    modified = True
            
            if not modified:
                break
            
            # 重新计算曲率
            curvatures = self.calculate_curvatures(smoothed)
        
        return smoothed
    
    def calculate_turn_radius(self, p1: Tuple[float, float],
                            p2: Tuple[float, float],
                            p3: Tuple[float, float]) -> float:
        """
        计算三点形成的转弯半径
        
        Args:
            p1, p2, p3: 三个连续航点
            
        Returns:
            转弯半径(米)
        """
        curvature = self._point_curvature(p1, p2, p3, p3)
        
        if abs(curvature) < 1e-10:
            return float('inf')
        
        return 1.0 / abs(curvature)