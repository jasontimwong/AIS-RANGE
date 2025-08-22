#!/usr/bin/env python3
"""初始化海事系统的可行域和规划器"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from lib.region.feasible_region import FeasibleRegionBuilder, SafetyParameters, FeasibleRegion
from lib.planner.hybrid_astar import HybridAStar, PlannerConfig
from shapely.geometry import MultiPolygon, Polygon, box
import numpy as np
import logging

logger = logging.getLogger(__name__)

def initialize_maritime_region():
    """
    初始化海事可行域（简化版本）
    返回一个基本的FeasibleRegion对象，允许在亚太地区进行路径规划
    """
    try:
        logger.info("开始初始化海事可行域...")
        
        # 亚太地区范围
        bounds = (100.0, -10.0, 130.0, 40.0)  # (minx, miny, maxx, maxy)
        
        # 创建一个基本的可行域，整个矩形区域都是可航行的
        # 在实际应用中，这里应该加载真实的海岸线和障碍物数据
        navigable_box = box(*bounds)
        
        # 创建一些模拟的障碍物（岛屿）
        # 这些只是示例，实际应该从地图数据加载
        islands = [
            # 台湾岛简化形状
            Polygon([(120.0, 22.0), (121.5, 22.0), (121.5, 25.5), (120.0, 25.5)]),
            # 海南岛简化形状  
            Polygon([(108.5, 18.0), (111.0, 18.0), (111.0, 20.5), (108.5, 20.5)]),
            # 菲律宾部分岛屿
            Polygon([(120.0, 7.0), (127.0, 7.0), (127.0, 19.0), (120.0, 19.0)]),
        ]
        
        # 从可航行区域中减去障碍物
        no_go_areas = MultiPolygon(islands)
        navigable_area = navigable_box.difference(no_go_areas)
        
        # 确保navigable_area是MultiPolygon
        if not isinstance(navigable_area, MultiPolygon):
            if isinstance(navigable_area, Polygon):
                navigable_area = MultiPolygon([navigable_area])
            else:
                # 如果是其他类型，转换为MultiPolygon
                navigable_area = MultiPolygon([navigable_box])
        
        # 创建FeasibleRegion对象（包含所有必需参数）
        region = FeasibleRegion(
            bounds=bounds,
            no_go_areas=no_go_areas,
            navigable_area=navigable_area,
            depth_contours={},  # 简化版本，不包含深度等高线
            danger_zones=[],  # 空的危险区域列表
            restricted_areas=[],  # 空的限制区域列表
            tss_zones=None  # 简化版本，不包含TSS
        )
        
        # 设置bbox属性（某些代码可能需要）
        region.bbox = bounds
        
        # 创建一个简单的网格表示（用于某些算法）
        # 100x100的网格，覆盖整个区域
        grid_size = 100
        region.grid = np.ones((grid_size, grid_size), dtype=bool)
        
        # 标记障碍物区域
        for i in range(grid_size):
            for j in range(grid_size):
                # 将网格坐标转换为地理坐标
                lon = bounds[0] + (bounds[2] - bounds[0]) * j / grid_size
                lat = bounds[1] + (bounds[3] - bounds[1]) * i / grid_size
                point = Polygon([(lon, lat), (lon, lat), (lon, lat), (lon, lat)]).centroid
                
                # 检查点是否在障碍物中
                if no_go_areas.contains(point):
                    region.grid[i, j] = False
        
        logger.info(f"✓ 可行域初始化成功: 范围 {bounds}")
        return region
        
    except Exception as e:
        logger.error(f"初始化海事可行域失败: {e}")
        import traceback
        traceback.print_exc()
        
        # 返回一个最小的可行域，避免系统完全失败
        try:
            bounds = (100.0, -10.0, 130.0, 40.0)
            navigable_area = MultiPolygon([box(*bounds)])
            minimal_region = FeasibleRegion(
                bounds=bounds,
                no_go_areas=MultiPolygon(),
                navigable_area=navigable_area,
                depth_contours={},
                danger_zones=[],
                restricted_areas=[],
                tss_zones=None
            )
            minimal_region.bbox = bounds
            minimal_region.grid = np.ones((10, 10), dtype=bool)
            logger.warning("返回最小可行域作为后备方案")
            return minimal_region
        except:
            return None


def init_maritime_system():
    """完整的海事系统初始化（用于测试）"""
    print("正在初始化海事系统...")
    
    # 1. 创建安全参数
    safety_params = SafetyParameters(
        safety_depth=10.0,
        safety_contour=20.0,
        xtd_margin=500.0,  # 500米横向安全距离
        under_keel_clearance=2.0,  # 2米龙骨下净空
        vessel_draft=12.0  # 12米吃水
    )
    
    # 2. 获取可行域
    region = initialize_maritime_region()
    
    if region:
        print(f"✓ 可行域构建成功")
        print(f"  范围: {region.bbox}")
        if hasattr(region, 'grid'):
            print(f"  网格大小: {region.grid.shape}")
    else:
        print("✗ 可行域构建失败")
        return False
    
    # 3. 创建规划器
    print("初始化路径规划器...")
    config = PlannerConfig(
        motion_step=0.05,  # 50米精度
        max_iterations=50000,
        heuristic_weight=1.2
    )
    
    try:
        planner = HybridAStar(region, config)
        print("✓ 规划器初始化成功")
    except Exception as e:
        print(f"✗ 规划器初始化失败: {e}")
        return False
    
    # 4. 测试规划
    print("\n测试路径规划...")
    try:
        # 上海到新加坡
        start = (121.508, 31.23, 0)  # 上海
        goal = (103.85, 1.27, None)   # 新加坡
        
        route = planner.plan(start, goal)
        if route and len(route.waypoints) > 0:
            print(f"✓ 测试规划成功: {len(route.waypoints)} 个航点")
            return True
        else:
            print("✗ 测试规划失败：未生成路径")
            return False
    except Exception as e:
        print(f"✗ 测试规划异常: {e}")
        import traceback
        traceback.print_exc()
        return False


if __name__ == "__main__":
    success = init_maritime_system()
    sys.exit(0 if success else 1)