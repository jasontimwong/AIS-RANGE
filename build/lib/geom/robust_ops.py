"""
几何鲁棒性操作工具
处理退化几何、自交、小环、缝隙等病理情况
"""

import logging
from typing import Union, List, Optional, Tuple
from shapely.geometry import (
    Polygon, MultiPolygon, LineString, MultiLineString,
    Point, GeometryCollection
)
from shapely.ops import unary_union
from shapely.validation import make_valid
import numpy as np

logger = logging.getLogger(__name__)

class RobustGeometryOps:
    """几何鲁棒性操作类"""
    
    def __init__(self, 
                 min_area: float = 1.0,
                 min_hole_area: float = 10.0,
                 simplify_tolerance: float = 0.1,
                 buffer_distance: float = 0.01):
        """
        初始化鲁棒性操作参数
        
        Args:
            min_area: 最小多边形面积（m²）
            min_hole_area: 最小孔洞面积（m²）
            simplify_tolerance: 简化容差（m）
            buffer_distance: 缓冲距离（m）
        """
        self.min_area = min_area
        self.min_hole_area = min_hole_area
        self.simplify_tolerance = simplify_tolerance
        self.buffer_distance = buffer_distance
        self.repair_stats = {
            'degenerate': 0,
            'self_intersection': 0,
            'small_polygons': 0,
            'small_holes': 0,
            'gaps': 0,
            'conservative_buffer': 0
        }
    
    def repair_geometry(self, geom: Union[Polygon, MultiPolygon], 
                       conservative: bool = True) -> Union[Polygon, MultiPolygon]:
        """
        修复病理几何
        
        Args:
            geom: 输入几何
            conservative: 是否使用保守策略（加厚边界）
            
        Returns:
            修复后的几何
        """
        if geom is None or geom.is_empty:
            return MultiPolygon([])
        
        # 1. 处理退化几何
        if not geom.is_valid:
            logger.debug("修复无效几何")
            self.repair_stats['degenerate'] += 1
            geom = self._fix_degenerate(geom)
        
        # 2. 处理自交
        if self._has_self_intersection(geom):
            logger.debug("修复自交几何")
            self.repair_stats['self_intersection'] += 1
            geom = self._fix_self_intersection(geom)
        
        # 3. 移除小多边形
        geom = self._remove_small_polygons(geom)
        
        # 4. 填充小孔洞
        geom = self._fill_small_holes(geom)
        
        # 5. 修复缝隙
        geom = self._fix_gaps(geom)
        
        # 6. 保守策略：轻微加厚
        if conservative and self._needs_conservative_buffer(geom):
            logger.debug("应用保守缓冲")
            self.repair_stats['conservative_buffer'] += 1
            geom = geom.buffer(self.buffer_distance).buffer(-self.buffer_distance)
        
        return geom
    
    def _fix_degenerate(self, geom) -> Union[Polygon, MultiPolygon]:
        """修复退化几何（重复点、共线点等）"""
        try:
            # 使用make_valid修复
            fixed = make_valid(geom)
            
            # 确保返回Polygon或MultiPolygon
            if isinstance(fixed, GeometryCollection):
                polygons = [g for g in fixed.geoms if isinstance(g, (Polygon, MultiPolygon))]
                if polygons:
                    fixed = unary_union(polygons)
                else:
                    fixed = MultiPolygon([])
            
            return fixed
        except Exception as e:
            logger.warning(f"退化修复失败: {e}")
            # 尝试buffer(0)修复
            return geom.buffer(0)
    
    def _has_self_intersection(self, geom) -> bool:
        """检测自交"""
        if isinstance(geom, Polygon):
            return not geom.exterior.is_simple
        elif isinstance(geom, MultiPolygon):
            return any(not p.exterior.is_simple for p in geom.geoms)
        return False
    
    def _fix_self_intersection(self, geom) -> Union[Polygon, MultiPolygon]:
        """修复自交几何"""
        # 使用unary_union分解并重组
        fixed = unary_union(geom)
        
        # 如果还有问题，使用buffer技术
        if not fixed.is_valid:
            fixed = geom.buffer(0)
        
        return fixed
    
    def _remove_small_polygons(self, geom) -> Union[Polygon, MultiPolygon]:
        """移除小面积多边形"""
        if isinstance(geom, Polygon):
            if geom.area < self.min_area:
                logger.debug(f"移除小多边形: area={geom.area}")
                self.repair_stats['small_polygons'] += 1
                return MultiPolygon([])
            return geom
        elif isinstance(geom, MultiPolygon):
            valid_polys = []
            for poly in geom.geoms:
                if poly.area >= self.min_area:
                    valid_polys.append(poly)
                else:
                    self.repair_stats['small_polygons'] += 1
            return MultiPolygon(valid_polys) if valid_polys else MultiPolygon([])
        return geom
    
    def _fill_small_holes(self, geom) -> Union[Polygon, MultiPolygon]:
        """填充小孔洞"""
        if isinstance(geom, Polygon):
            return self._fill_polygon_holes(geom)
        elif isinstance(geom, MultiPolygon):
            filled = []
            for poly in geom.geoms:
                filled.append(self._fill_polygon_holes(poly))
            return MultiPolygon(filled)
        return geom
    
    def _fill_polygon_holes(self, poly: Polygon) -> Polygon:
        """填充单个多边形的小孔洞"""
        if not poly.interiors:
            return poly
        
        valid_holes = []
        for hole in poly.interiors:
            hole_poly = Polygon(hole)
            if hole_poly.area >= self.min_hole_area:
                valid_holes.append(hole)
            else:
                logger.debug(f"填充小孔洞: area={hole_poly.area}")
                self.repair_stats['small_holes'] += 1
        
        if len(valid_holes) < len(poly.interiors):
            return Polygon(poly.exterior, valid_holes)
        return poly
    
    def _fix_gaps(self, geom) -> Union[Polygon, MultiPolygon]:
        """修复缝隙（相邻多边形间的小间隙）"""
        if isinstance(geom, MultiPolygon):
            # 使用微小buffer填充缝隙
            buffered = geom.buffer(self.buffer_distance * 0.5)
            debuffered = buffered.buffer(-self.buffer_distance * 0.5)
            
            if debuffered.area > geom.area * 1.001:  # 检测是否填充了缝隙
                self.repair_stats['gaps'] += 1
                return debuffered
        
        return geom
    
    def _needs_conservative_buffer(self, geom) -> bool:
        """判断是否需要保守缓冲"""
        # 检查是否有非常尖锐的角或细长部分
        if isinstance(geom, Polygon):
            return self._has_sharp_features(geom)
        elif isinstance(geom, MultiPolygon):
            return any(self._has_sharp_features(p) for p in geom.geoms)
        return False
    
    def _has_sharp_features(self, poly: Polygon) -> bool:
        """检测尖锐特征"""
        coords = list(poly.exterior.coords)
        for i in range(len(coords) - 2):
            p1, p2, p3 = coords[i:i+3]
            angle = self._calculate_angle(p1, p2, p3)
            if angle < np.pi / 6:  # 30度以下认为尖锐
                return True
        return False
    
    def _calculate_angle(self, p1, p2, p3) -> float:
        """计算三点形成的角度"""
        v1 = np.array(p1) - np.array(p2)
        v2 = np.array(p3) - np.array(p2)
        
        norm1 = np.linalg.norm(v1)
        norm2 = np.linalg.norm(v2)
        
        # 防止除零错误
        if norm1 < 1e-10 or norm2 < 1e-10:
            return 0.0  # 退化情况，返回0角度
        
        cos_angle = np.dot(v1, v2) / (norm1 * norm2)
        angle = np.arccos(np.clip(cos_angle, -1, 1))
        return angle
    
    def simplify_geometry(self, geom: Union[Polygon, MultiPolygon], 
                         preserve_topology: bool = True) -> Union[Polygon, MultiPolygon]:
        """
        简化几何（减少顶点数）
        
        Args:
            geom: 输入几何
            preserve_topology: 是否保持拓扑关系
            
        Returns:
            简化后的几何
        """
        if preserve_topology:
            return geom.simplify(self.simplify_tolerance, preserve_topology=True)
        else:
            return geom.simplify(self.simplify_tolerance, preserve_topology=False)
    
    def validate_geometry(self, geom) -> Tuple[bool, List[str]]:
        """
        验证几何有效性
        
        Returns:
            (是否有效, 问题列表)
        """
        issues = []
        
        if geom is None:
            issues.append("几何为None")
            return False, issues
        
        if geom.is_empty:
            issues.append("几何为空")
            return False, issues
        
        if not geom.is_valid:
            issues.append("几何无效")
        
        if isinstance(geom, (Polygon, MultiPolygon)):
            if geom.area < self.min_area:
                issues.append(f"面积过小: {geom.area} < {self.min_area}")
            
            if self._has_self_intersection(geom):
                issues.append("存在自交")
        
        return len(issues) == 0, issues
    
    def get_repair_stats(self) -> dict:
        """获取修复统计"""
        return self.repair_stats.copy()
    
    def reset_stats(self):
        """重置统计"""
        for key in self.repair_stats:
            self.repair_stats[key] = 0


class GeometryHealer:
    """几何修复器（高级接口）"""
    
    def __init__(self):
        self.robust_ops = RobustGeometryOps()
    
    def heal_navigable_area(self, area: Union[Polygon, MultiPolygon]) -> Union[Polygon, MultiPolygon]:
        """修复可航区域"""
        logger.info("开始修复可航区域几何")
        
        # 1. 基础修复
        healed = self.robust_ops.repair_geometry(area, conservative=False)
        
        # 2. 验证
        valid, issues = self.robust_ops.validate_geometry(healed)
        if not valid:
            logger.warning(f"修复后仍有问题: {issues}")
            # 尝试保守修复
            healed = self.robust_ops.repair_geometry(area, conservative=True)
        
        # 3. 简化
        healed = self.robust_ops.simplify_geometry(healed)
        
        stats = self.robust_ops.get_repair_stats()
        logger.info(f"修复统计: {stats}")
        
        return healed
    
    def heal_obstacles(self, obstacles: List[Union[Polygon, MultiPolygon]]) -> List[Union[Polygon, MultiPolygon]]:
        """修复障碍物几何"""
        healed = []
        
        for obs in obstacles:
            fixed = self.robust_ops.repair_geometry(obs, conservative=True)  # 障碍物使用保守策略
            if not fixed.is_empty:
                healed.append(fixed)
        
        return healed