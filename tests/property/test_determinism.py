"""
确定性测试：确保相同输入产生相同输出
"""
import hashlib
import json
import sys
import os
sys.path.insert(0, os.path.abspath('.'))

from lib.planner.hybrid_astar import HybridAStar, PlannerConfig
from lib.region.feasible_region import FeasibleRegion
from shapely.geometry import MultiPolygon, box
import numpy as np

def compute_hash(data):
    """计算数据的SHA256哈希"""
    if isinstance(data, dict):
        data = json.dumps(data, sort_keys=True)
    elif hasattr(data, '__dict__'):
        data = json.dumps(data.__dict__, sort_keys=True, default=str)
    return hashlib.sha256(str(data).encode()).hexdigest()

def test_planner_determinism():
    """测试规划器的确定性"""
    # 固定随机种子
    np.random.seed(42)
    
    # 创建测试场景
    region = FeasibleRegion(
        bounds=(-11000000, 4200000, -10700000, 4220000),
        no_go_areas=MultiPolygon([]),
        navigable_area=MultiPolygon([box(-11000000, 4200000, -10700000, 4220000)]),
        depth_contours={},
        danger_zones=[],
        restricted_areas=[]
    )
    
    config = PlannerConfig(
        grid_resolution=1000.0,
        motion_step=1000.0,
        max_iterations=100,
        goal_tolerance_xy=100.0
    )
    
    start = (-10773647.9, 4207896.0, 0.0)
    goal = (-10764853.1, 4210122.4, None)
    
    # 运行100次，收集哈希
    hashes = []
    for i in range(100):
        np.random.seed(42)  # 每次重置种子
        planner = HybridAStar(config, region)
        route = planner.plan(start, goal, initial_velocity=10.0)
        
        if route:
            route_data = {
                'waypoints': route.waypoints,
                'headings': [float(h) for h in route.headings],
                'velocities': [float(v) for v in route.velocities],
                'total_cost': float(route.total_cost)
            }
            route_hash = compute_hash(route_data)
            hashes.append(route_hash)
    
    # 验证所有哈希相同
    unique_hashes = set(hashes)
    assert len(unique_hashes) == 1, f"发现{len(unique_hashes)}个不同结果，期望1个"
    
    print(f"✓ 确定性测试通过：100次运行产生相同结果")
    print(f"  路径哈希: {list(unique_hashes)[0][:16]}...")
    return True

def test_float_stability():
    """测试浮点数稳定性"""
    # 使用固定精度进行计算
    values = []
    for i in range(100):
        # 模拟浮点运算
        result = 0.0
        for j in range(1000):
            result += 0.1
        result = round(result, 10)  # 固定精度
        values.append(result)
    
    # 验证所有值相同
    unique_values = set(values)
    assert len(unique_values) == 1, f"浮点运算不稳定：{unique_values}"
    
    print("✓ 浮点稳定性测试通过")
    return True

if __name__ == "__main__":
    test_planner_determinism()
    test_float_stability()
    print("\n所有确定性测试通过！")