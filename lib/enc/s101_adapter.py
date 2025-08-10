"""
S-101 ENC适配器
将S-101格式数据转换为内部格式，保持与S-57的兼容性
"""

import logging
from typing import Dict, List, Optional, Tuple, Any
from dataclasses import dataclass
from shapely.geometry import Polygon, MultiPolygon, Point, LineString, box
from shapely.ops import unary_union
import numpy as np
from pathlib import Path

logger = logging.getLogger(__name__)

# S-101到S-57特征映射
S101_TO_S57_MAPPING = {
    # 深度区域
    'DepthArea': 'DEPARE',
    'DepthContour': 'DEPCNT',
    'SoundingDatum': 'SNDDAT',
    
    # 障碍物
    'Obstruction': 'OBSTRN',
    'UnderwaterRock': 'UWTROC',
    'Wreck': 'WRECKS',
    
    # 限制区域
    'RestrictedAreaNavigational': 'RESARE',
    'RestrictedAreaRegulatory': 'RESARE',
    'CautionArea': 'CTNARE',
    
    # 交通分离
    'TrafficSeparationSchemeLane': 'TSSLPT',
    'TrafficSeparationSchemeBoundary': 'TSSBND',
    'TrafficSeparationZone': 'TSEZNE',
    'InshoreTrafficZone': 'ISTZNE',
    
    # 航道
    'FairwaySystem': 'FAIRWY',
    'DeepWaterRoute': 'DWRTPT',
    'RecommendedRoute': 'RCRTCL',
    
    # 陆地
    'LandArea': 'LNDARE',
    'CoastLine': 'COALNE',
    
    # 导航设施
    'Beacon': 'BCNLAT',
    'Buoy': 'BOYLAT',
    'Lighthouse': 'LIGHTS'
}

# S-101属性到S-57属性映射
S101_ATTR_MAPPING = {
    'minimumDepth': 'DRVAL1',
    'maximumDepth': 'DRVAL2',
    'verticalDatum': 'VERDAT',
    'depthRangeValue': 'DRVAL1',
    'categoryOfRestrictedArea': 'CATREA',
    'restriction': 'RESTRN',
    'status': 'STATUS',
    'trafficFlow': 'ORIENT'
}


@dataclass
class S101Feature:
    """S-101特征"""
    feature_type: str
    geometry: Any
    attributes: Dict[str, Any]
    s57_equivalent: Optional[str] = None


class S101Adapter:
    """S-101 ENC适配器"""
    
    def __init__(self, coordinate_system: str = 'EPSG:4326'):
        """
        初始化S-101适配器
        
        Args:
            coordinate_system: 坐标系统
        """
        self.coordinate_system = coordinate_system
        self.features = []
        self.navigable_area = None
        self.no_go_areas = None
        self.depth_contours = {}
        self.tss_zones = []
        self.consistency_report = {}
    
    def load_s101(self, file_path: str) -> bool:
        """
        加载S-101文件
        
        Args:
            file_path: S-101文件路径
            
        Returns:
            是否成功加载
        """
        logger.info(f"加载S-101文件: {file_path}")
        
        try:
            # 这里应该使用S-100 Product Specification解析器
            # 为演示目的，我们模拟加载过程
            self.features = self._parse_s101_file(file_path)
            
            # 转换为内部格式
            self._convert_features()
            
            # 构建可行域
            self._build_feasible_region()
            
            return True
            
        except Exception as e:
            logger.error(f"加载S-101失败: {e}")
            return False
    
    def _parse_s101_file(self, file_path: str) -> List[S101Feature]:
        """
        解析S-101文件（模拟）
        
        Returns:
            S-101特征列表
        """
        features = []
        
        # 模拟S-101数据
        # 深度区域
        features.append(S101Feature(
            feature_type='DepthArea',
            geometry=box(-122.6, 37.7, -122.3, 37.9),
            attributes={
                'minimumDepth': 10.0,
                'maximumDepth': 50.0,
                'verticalDatum': 'MLLW'
            }
        ))
        
        # 障碍物
        features.append(S101Feature(
            feature_type='Obstruction',
            geometry=Point(-122.45, 37.8).buffer(0.001),
            attributes={
                'categoryOfObstruction': 'submerged',
                'depthRangeValue': 5.0
            }
        ))
        
        # TSS区域
        features.append(S101Feature(
            feature_type='TrafficSeparationSchemeLane',
            geometry=Polygon([
                (-122.55, 37.75),
                (-122.50, 37.75),
                (-122.50, 37.85),
                (-122.55, 37.85),
                (-122.55, 37.75)
            ]),
            attributes={
                'trafficFlow': 'inbound',
                'status': 'permanent'
            }
        ))
        
        # 限制区域
        features.append(S101Feature(
            feature_type='RestrictedAreaNavigational',
            geometry=box(-122.48, 37.78, -122.46, 37.80),
            attributes={
                'categoryOfRestrictedArea': 'anchorage',
                'restriction': ['anchoring_prohibited']
            }
        ))
        
        return features
    
    def _convert_features(self):
        """转换S-101特征到S-57等价"""
        for feature in self.features:
            # 映射特征类型
            if feature.feature_type in S101_TO_S57_MAPPING:
                feature.s57_equivalent = S101_TO_S57_MAPPING[feature.feature_type]
            else:
                logger.warning(f"未知S-101特征类型: {feature.feature_type}")
            
            # 映射属性
            converted_attrs = {}
            for s101_attr, value in feature.attributes.items():
                if s101_attr in S101_ATTR_MAPPING:
                    s57_attr = S101_ATTR_MAPPING[s101_attr]
                    converted_attrs[s57_attr] = value
                else:
                    converted_attrs[s101_attr] = value
            
            feature.attributes = converted_attrs
    
    def _build_feasible_region(self):
        """构建可行域"""
        # 收集所有深度区域
        depth_areas = []
        obstacles = []
        restricted = []
        
        for feature in self.features:
            if feature.feature_type == 'DepthArea':
                # 检查最小深度
                min_depth = feature.attributes.get('DRVAL1', 0)
                if min_depth >= 10.0:  # 假设10米为安全深度
                    depth_areas.append(feature.geometry)
            
            elif feature.feature_type in ['Obstruction', 'UnderwaterRock', 'Wreck']:
                obstacles.append(feature.geometry)
            
            elif feature.feature_type in ['RestrictedAreaNavigational', 'RestrictedAreaRegulatory']:
                restricted.append(feature.geometry)
            
            elif feature.feature_type == 'TrafficSeparationSchemeLane':
                self.tss_zones.append({
                    'geometry': feature.geometry,
                    'direction': feature.attributes.get('ORIENT', 0),
                    'type': 'lane'
                })
        
        # 构建可航区域
        if depth_areas:
            self.navigable_area = unary_union(depth_areas)
        else:
            # 默认区域
            self.navigable_area = box(-123, 37.5, -122, 38)
        
        # 构建禁航区
        no_go_list = obstacles + restricted
        if no_go_list:
            self.no_go_areas = unary_union(no_go_list)
        else:
            self.no_go_areas = MultiPolygon([])
        
        # 从可航区域中减去禁航区
        if not self.no_go_areas.is_empty:
            self.navigable_area = self.navigable_area.difference(self.no_go_areas)
    
    def get_feasible_region(self) -> Dict[str, Any]:
        """
        获取可行域（与S-57兼容的格式）
        
        Returns:
            可行域字典
        """
        return {
            'navigable_area': self.navigable_area,
            'no_go_areas': self.no_go_areas,
            'depth_contours': self.depth_contours,
            'tss_zones': self.tss_zones,
            'bounds': self.navigable_area.bounds if self.navigable_area else None
        }
    
    def compare_with_s57(self, s57_region: Dict[str, Any]) -> Dict[str, Any]:
        """
        与S-57可行域比较
        
        Args:
            s57_region: S-57可行域
            
        Returns:
            一致性报告
        """
        logger.info("比较S-101与S-57可行域")
        
        s101_nav = self.navigable_area
        s57_nav = s57_region.get('navigable_area')
        
        if s101_nav is None or s57_nav is None:
            return {
                'iou': 0.0,
                'area_diff_percent': 100.0,
                'consistent': False
            }
        
        # 计算IoU（交并比）
        intersection = s101_nav.intersection(s57_nav)
        union = s101_nav.union(s57_nav)
        
        iou = intersection.area / union.area if union.area > 0 else 0
        
        # 计算面积差异
        area_diff = abs(s101_nav.area - s57_nav.area)
        area_diff_percent = (area_diff / s57_nav.area * 100) if s57_nav.area > 0 else 100
        
        # 计算边界差异
        s101_boundary = s101_nav.boundary
        s57_boundary = s57_nav.boundary
        
        if hasattr(s101_boundary, 'hausdorff_distance'):
            hausdorff_dist = s101_boundary.hausdorff_distance(s57_boundary)
        else:
            hausdorff_dist = 0
        
        # 生成差异热图数据
        diff_areas = {
            's101_only': s101_nav.difference(s57_nav),
            's57_only': s57_nav.difference(s101_nav),
            'common': intersection
        }
        
        report = {
            'iou': iou,
            'area_diff_percent': area_diff_percent,
            'hausdorff_distance': hausdorff_dist,
            's101_area': s101_nav.area,
            's57_area': s57_nav.area,
            'intersection_area': intersection.area,
            'union_area': union.area,
            'consistent': iou >= 0.99 and area_diff_percent <= 1.0,
            'diff_areas': diff_areas
        }
        
        self.consistency_report = report
        return report
    
    def generate_diff_heatmap(self, resolution: float = 100.0) -> np.ndarray:
        """
        生成差异热图
        
        Args:
            resolution: 栅格分辨率（米）
            
        Returns:
            热图矩阵
        """
        if not self.consistency_report or 'diff_areas' not in self.consistency_report:
            return np.array([])
        
        diff_areas = self.consistency_report['diff_areas']
        
        # 获取边界
        all_geoms = [
            diff_areas['s101_only'],
            diff_areas['s57_only'],
            diff_areas['common']
        ]
        
        bounds_list = []
        for geom in all_geoms:
            if not geom.is_empty:
                bounds_list.append(geom.bounds)
        
        if not bounds_list:
            return np.array([])
        
        # 计算总边界
        min_x = min(b[0] for b in bounds_list)
        min_y = min(b[1] for b in bounds_list)
        max_x = max(b[2] for b in bounds_list)
        max_y = max(b[3] for b in bounds_list)
        
        # 创建栅格
        width = int((max_x - min_x) / resolution) + 1
        height = int((max_y - min_y) / resolution) + 1
        
        heatmap = np.zeros((height, width))
        
        # 填充热图
        # 0: 无数据, 1: 仅S-101, 2: 仅S-57, 3: 共同区域
        for i in range(height):
            for j in range(width):
                x = min_x + j * resolution
                y = min_y + i * resolution
                point = Point(x, y)
                
                if diff_areas['common'].contains(point):
                    heatmap[i, j] = 3  # 共同区域
                elif diff_areas['s101_only'].contains(point):
                    heatmap[i, j] = 1  # 仅S-101
                elif diff_areas['s57_only'].contains(point):
                    heatmap[i, j] = 2  # 仅S-57
        
        return heatmap
    
    def export_to_evidence(self, output_dir: Path) -> Dict[str, Any]:
        """
        导出到证据包
        
        Args:
            output_dir: 输出目录
            
        Returns:
            证据摘要
        """
        output_dir = Path(output_dir)
        output_dir.mkdir(parents=True, exist_ok=True)
        
        evidence = {
            'adapter': 'S101Adapter',
            'features_count': len(self.features),
            'feature_types': list(set(f.feature_type for f in self.features)),
            'consistency_report': self.consistency_report
        }
        
        # 保存热图
        if self.consistency_report:
            heatmap = self.generate_diff_heatmap()
            if heatmap.size > 0:
                import json
                heatmap_file = output_dir / 's101_s57_diff_heatmap.json'
                with open(heatmap_file, 'w') as f:
                    json.dump({
                        'heatmap': heatmap.tolist(),
                        'legend': {
                            0: 'no_data',
                            1: 's101_only',
                            2: 's57_only',
                            3: 'common'
                        }
                    }, f)
                evidence['heatmap_file'] = str(heatmap_file)
        
        return evidence