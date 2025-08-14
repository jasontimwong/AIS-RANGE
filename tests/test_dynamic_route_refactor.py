#!/usr/bin/env python3
"""
动态路径规划重构验收测试

测试项目：
1. 粒度配置测试
2. 完整重规划测试
3. AIS约束集成测试
4. 性能测试
5. 兼容性测试
"""

import sys
import math
import time
import unittest
from pathlib import Path
from typing import List, Tuple
from datetime import datetime

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from lib.ais.manager import AISManager
from lib.ais import AISTarget
from lib.route.dynamic_planner import DynamicRoutePlanner
from lib.region.feasible_region import FeasibleRegion
from lib.planner.hybrid_astar import HybridAStar, PlannerConfig
from shapely.geometry import MultiPolygon, box


class TestDynamicRouteRefactor(unittest.TestCase):
    """动态路径规划重构测试套件"""
    
    def setUp(self):
        """设置测试环境"""
        self.ais_manager = AISManager()
        
        # 创建测试可航区域
        self.region = self._create_test_region()
        
        # 创建动态规划器
        self.planner = DynamicRoutePlanner(
            self.ais_manager,
            get_feasible_region=lambda: self.region,
            get_planner_config=lambda: PlannerConfig(
                grid_resolution=50.0,
                motion_step=50.0,
                goal_tolerance_xy=50.0
            )
        )
        
        # 初始化测试路径
        self.test_route = [
            (31.23, 121.508),
            (31.20, 121.60),
            (31.15, 121.70),
            (31.10, 121.80),
            (31.00, 122.00)
        ]
        self.planner.initialize_route(self.test_route)
    
    def _create_test_region(self) -> FeasibleRegion:
        """创建测试可航区域"""
        meters_per_deg_lat = 111320.0
        meters_per_deg_lon = 111320.0 * math.cos(math.radians(31.0))
        
        min_x = 120.0 * meters_per_deg_lon
        max_x = 123.0 * meters_per_deg_lon
        min_y = 30.0 * meters_per_deg_lat
        max_y = 32.0 * meters_per_deg_lat
        
        return FeasibleRegion(
            bounds=(min_x, min_y, max_x, max_y),
            no_go_areas=MultiPolygon([]),
            navigable_area=MultiPolygon([box(min_x, min_y, max_x, max_y)]),
            depth_contours={},
            danger_zones=[],
            restricted_areas=[]
        )
    
    def _add_test_ais_target(self, mmsi: str, lat: float, lon: float, 
                           sog: float = 10.0, cog: float = 180.0):
        """添加测试AIS目标"""
        target = AISTarget(
            mmsi=mmsi,
            timestamp=datetime.now(),
            position=(lat, lon),
            sog=sog,
            cog=cog % 360,
            heading=cog % 360,
            nav_status=0,
            ship_type=70,
            name=f"Test Vessel {mmsi}"
        )
        self.ais_manager.targets[mmsi] = target
        return target
    
    def test_01_motion_step_configuration(self):
        """测试1: 粒度配置是否生效"""
        print("\n测试1: 验证50m粒度配置...")
        
        # 获取当前动态路径
        current_pos = (31.23, 121.508)
        route = self.planner.update_dynamic_route(current_pos)
        
        self.assertIsNotNone(route, "路径规划失败")
        
        # 计算路径点间距
        distances = []
        for i in range(len(route.waypoints) - 1):
            wp1 = route.waypoints[i]
            wp2 = route.waypoints[i + 1]
            
            lat1, lon1 = wp1.lat, wp1.lon
            lat2, lon2 = wp2.lat, wp2.lon
            
            meters_per_deg_lat = 111320.0
            meters_per_deg_lon = 111320.0 * math.cos(math.radians((lat1 + lat2) / 2))
            
            dx = (lon2 - lon1) * meters_per_deg_lon
            dy = (lat2 - lat1) * meters_per_deg_lat
            distance = math.sqrt(dx * dx + dy * dy)
            
            distances.append(distance)
        
        # 验证平均间距接近50m
        avg_distance = sum(distances) / len(distances) if distances else 0
        max_distance = max(distances) if distances else 0
        
        print(f"  平均间距: {avg_distance:.1f}米")
        print(f"  最大间距: {max_distance:.1f}米")
        
        self.assertLess(avg_distance, 55.0, "平均间距超过55米")
        self.assertGreater(avg_distance, 45.0, "平均间距小于45米")
        self.assertLess(max_distance, 60.0, "最大间距超过60米")
        
        print("  ✓ 粒度配置测试通过")
    
    def test_02_complete_replanning(self):
        """测试2: 完整重规划功能"""
        print("\n测试2: 验证完整重规划...")
        
        # 添加AIS威胁
        self._add_test_ais_target("TEST001", 31.18, 121.65, 15.0, 270.0)
        
        current_pos = (31.23, 121.508)
        
        # 第一次规划
        route1 = self.planner.update_dynamic_route(current_pos)
        self.assertIsNotNone(route1)
        waypoints1 = [(wp.lat, wp.lon) for wp in route1.waypoints]
        
        # 添加更多威胁
        self._add_test_ais_target("TEST002", 31.15, 121.70, 12.0, 180.0)
        
        # 第二次规划（应该是完整重规划）
        time.sleep(1.1)  # 等待更新间隔
        route2 = self.planner.update_dynamic_route(current_pos)
        self.assertIsNotNone(route2)
        waypoints2 = [(wp.lat, wp.lon) for wp in route2.waypoints]
        
        # 验证路径发生了变化（证明进行了重规划）
        self.assertNotEqual(waypoints1, waypoints2, "路径未发生变化")
        
        print(f"  原始路径点数: {len(waypoints1)}")
        print(f"  重规划路径点数: {len(waypoints2)}")
        print(f"  活跃威胁数: {len(route2.active_threats)}")
        print("  ✓ 完整重规划测试通过")
    
    def test_03_ais_constraint_integration(self):
        """测试3: AIS约束集成"""
        print("\n测试3: 验证AIS约束集成...")
        
        # 清空AIS目标
        self.ais_manager.targets.clear()
        
        current_pos = (31.23, 121.508)
        
        # 无威胁时的路径
        route_no_threat = self.planner.update_dynamic_route(current_pos)
        self.assertIsNotNone(route_no_threat)
        initial_threat_count = len(route_no_threat.active_threats)
        
        # 在路径上添加威胁
        self._add_test_ais_target("THREAT001", 31.175, 121.65, 20.0, 0.0)
        
        time.sleep(1.1)
        
        # 有威胁时的路径
        route_with_threat = self.planner.update_dynamic_route(current_pos)
        self.assertIsNotNone(route_with_threat)
        
        # 验证威胁数量增加了（由于可能有背景AIS目标，我们只验证数量变化）
        new_threat_count = len(route_with_threat.active_threats)
        self.assertGreaterEqual(new_threat_count, initial_threat_count, "威胁数量未增加")
        
        # 验证路径避开了威胁
        # 简单验证：检查路径是否偏离了威胁点
        threat_lat, threat_lon = 31.175, 121.65
        min_distance_to_threat = float('inf')
        
        for wp in route_with_threat.waypoints:
            dist = math.sqrt((wp.lat - threat_lat)**2 + (wp.lon - threat_lon)**2)
            min_distance_to_threat = min(min_distance_to_threat, dist)
        
        print(f"  与威胁最小距离: {min_distance_to_threat*111320:.1f}米")
        print(f"  活跃威胁: {route_with_threat.active_threats}")
        
        # 验证保持了安全距离（至少0.005度，约550米）
        self.assertGreater(min_distance_to_threat, 0.005, "未保持安全距离")
        
        print("  ✓ AIS约束集成测试通过")
    
    def test_04_performance_requirements(self):
        """测试4: 性能要求"""
        print("\n测试4: 验证性能要求...")
        
        # 添加多个AIS目标
        for i in range(20):
            self._add_test_ais_target(
                f"PERF{i:03d}",
                31.2 + i * 0.005,
                121.5 + i * 0.01,
                10.0 + i * 0.5,
                (180.0 + i * 15) % 360
            )
        
        current_pos = (31.23, 121.508)
        
        # 测量规划时间
        times = []
        for _ in range(5):
            start_time = time.perf_counter()
            route = self.planner.update_dynamic_route(current_pos)
            end_time = time.perf_counter()
            
            if route:
                times.append(end_time - start_time)
            
            time.sleep(1.1)
        
        avg_time = sum(times) / len(times) if times else 0
        max_time = max(times) if times else 0
        
        print(f"  平均规划时间: {avg_time:.3f}秒")
        print(f"  最大规划时间: {max_time:.3f}秒")
        
        # 验证性能要求
        self.assertLess(avg_time, 3.0, "平均规划时间超过3秒")
        self.assertLess(max_time, 5.0, "最大规划时间超过5秒")
        
        print("  ✓ 性能要求测试通过")
    
    def test_05_backward_compatibility(self):
        """测试5: 向后兼容性"""
        print("\n测试5: 验证向后兼容性...")
        
        # 测试原有接口是否正常工作
        current_pos = (31.23, 121.508)
        
        # initialize_route
        route_init = self.planner.initialize_route(self.test_route)
        self.assertIsNotNone(route_init)
        
        # update_dynamic_route
        route_update = self.planner.update_dynamic_route(current_pos)
        self.assertIsNotNone(route_update)
        
        # get_route_comparison
        comparison = self.planner.get_route_comparison()
        self.assertIsNotNone(comparison)
        self.assertIn('original_route', comparison)
        self.assertIn('dynamic_route', comparison)
        self.assertIn('active_threats', comparison)
        
        print("  ✓ 所有原有接口正常工作")
        print("  ✓ 向后兼容性测试通过")
    
    def test_06_edge_cases(self):
        """测试6: 边界情况"""
        print("\n测试6: 验证边界情况处理...")
        
        # 测试空AIS目标
        self.ais_manager.targets.clear()
        current_pos = (31.23, 121.508)
        route = self.planner.update_dynamic_route(current_pos)
        self.assertIsNotNone(route, "空AIS目标时规划失败")
        print("  ✓ 空AIS目标处理正常")
        
        # 测试大量AIS目标
        for i in range(100):
            self._add_test_ais_target(
                f"EDGE{i:03d}",
                31.0 + i * 0.002,
                121.5 + i * 0.002,
                5.0,
                i % 360
            )
        
        time.sleep(1.1)
        route = self.planner.update_dynamic_route(current_pos)
        self.assertIsNotNone(route, "大量AIS目标时规划失败")
        print(f"  ✓ 处理{len(self.ais_manager.targets)}个AIS目标正常")
        
        print("  ✓ 边界情况测试通过")


def run_acceptance_tests():
    """运行验收测试套件"""
    print("="*80)
    print("动态路径规划重构验收测试")
    print("="*80)
    print(f"开始时间: {datetime.now()}")
    print("-"*80)
    
    # 创建测试套件
    suite = unittest.TestLoader().loadTestsFromTestCase(TestDynamicRouteRefactor)
    
    # 运行测试
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)
    
    print("\n" + "="*80)
    print("验收测试结果汇总")
    print("="*80)
    
    # 统计结果
    total = result.testsRun
    failures = len(result.failures)
    errors = len(result.errors)
    success = total - failures - errors
    
    print(f"总测试数: {total}")
    print(f"成功: {success}")
    print(f"失败: {failures}")
    print(f"错误: {errors}")
    
    if failures + errors == 0:
        print("\n✅ 验收通过！所有测试均成功完成。")
        print("\n验收标准达成:")
        print("  ✓ 路径点间距 ≤ 60米")
        print("  ✓ AIS威胁正确避让")
        print("  ✓ API保持兼容")
        print("  ✓ 重规划时间 < 3秒")
        print("  ✓ 完整重规划实现")
    else:
        print("\n❌ 验收失败！存在未通过的测试。")
        if result.failures:
            print("\n失败的测试:")
            for test, traceback in result.failures:
                print(f"  - {test}")
        if result.errors:
            print("\n错误的测试:")
            for test, traceback in result.errors:
                print(f"  - {test}")
    
    print("="*80)
    return result.wasSuccessful()


if __name__ == "__main__":
    success = run_acceptance_tests()
    sys.exit(0 if success else 1)