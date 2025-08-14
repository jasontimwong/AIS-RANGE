#!/usr/bin/env python3
"""
动态路径规划性能基准测试

用于测量和对比动态路径规划的性能指标：
1. 规划时间
2. 路径粒度
3. 内存使用
"""

import time
import sys
import json
import statistics
from pathlib import Path
from typing import List, Tuple, Dict, Any
from datetime import datetime

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from lib.ais.manager import AISManager
from lib.ais import AISTarget
from lib.route.dynamic_planner import DynamicRoutePlanner
from lib.region.feasible_region import FeasibleRegion
from lib.planner.hybrid_astar import HybridAStar, PlannerConfig
from shapely.geometry import MultiPolygon, box
import math


class PerformanceBenchmark:
    """性能基准测试类"""
    
    def __init__(self, version="v2_refactored"):
        self.results = {
            "timestamp": datetime.now().isoformat(),
            "version": version,
            "tests": []
        }
        
    def setup_test_environment(self, num_ais_targets: int = 10) -> DynamicRoutePlanner:
        """设置测试环境"""
        # 创建AIS管理器
        ais_manager = AISManager()
        
        # 添加测试AIS目标
        for i in range(num_ais_targets):
            target = AISTarget(
                mmsi=f"TEST{i:03d}",
                timestamp=datetime.now(),
                position=(31.2 + i * 0.01, 121.5 + i * 0.01),
                sog=10.0 + i * 0.5,
                cog=(180.0 + i * 10) % 360,  # Keep within 0-360 range
                heading=(180.0 + i * 10) % 360,  # Keep within 0-360 range
                nav_status=0,
                ship_type=70,
                name=f"Test Vessel {i}"
            )
            ais_manager.targets[target.mmsi] = target
            
        # 创建测试可航区域
        def get_test_region():
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
            
        # 创建测试规划器配置 - 使用新的50m粒度
        def get_test_planner():
            config = PlannerConfig(
                grid_resolution=50.0,  # 统一粒度
                motion_step=50.0,      # 统一粒度
                max_iterations=5000,
                goal_tolerance_xy=50.0  # 匹配motion_step
            )
            return config
            
        # 创建动态规划器
        planner = DynamicRoutePlanner(
            ais_manager,
            get_feasible_region=get_test_region,
            get_planner_config=get_test_planner
        )
        
        # 初始化路径
        test_route = [
            (31.23, 121.508),  # 起点
            (31.20, 121.60),
            (31.15, 121.70),
            (31.10, 121.80),
            (31.05, 121.90),
            (31.00, 122.00)    # 终点
        ]
        planner.initialize_route(test_route)
        
        return planner
        
    def measure_planning_time(self, planner: DynamicRoutePlanner, 
                            current_position: Tuple[float, float],
                            iterations: int = 10) -> Dict[str, float]:
        """测量规划时间"""
        times = []
        
        for _ in range(iterations):
            start_time = time.perf_counter()
            route = planner.update_dynamic_route(current_position)
            end_time = time.perf_counter()
            
            if route:
                times.append(end_time - start_time)
                
        return {
            "mean": statistics.mean(times),
            "median": statistics.median(times),
            "min": min(times),
            "max": max(times),
            "stdev": statistics.stdev(times) if len(times) > 1 else 0
        }
        
    def measure_route_granularity(self, route) -> Dict[str, float]:
        """测量路径粒度"""
        if not route or not route.waypoints or len(route.waypoints) < 2:
            return {"mean": 0, "max": 0, "min": 0}
            
        distances = []
        for i in range(len(route.waypoints) - 1):
            wp1 = route.waypoints[i]
            wp2 = route.waypoints[i + 1]
            
            # 计算距离（米）
            lat1, lon1 = wp1.lat, wp1.lon
            lat2, lon2 = wp2.lat, wp2.lon
            
            meters_per_deg_lat = 111320.0
            meters_per_deg_lon = 111320.0 * math.cos(math.radians((lat1 + lat2) / 2))
            
            dx = (lon2 - lon1) * meters_per_deg_lon
            dy = (lat2 - lat1) * meters_per_deg_lat
            distance = math.sqrt(dx * dx + dy * dy)
            
            distances.append(distance)
            
        return {
            "mean": statistics.mean(distances),
            "median": statistics.median(distances),
            "max": max(distances),
            "min": min(distances),
            "count": len(distances)
        }
        
    def run_benchmark(self, test_configs: List[Dict[str, Any]]) -> None:
        """运行基准测试"""
        
        for config in test_configs:
            print(f"\n运行测试: {config['name']}")
            print("-" * 50)
            
            # 设置测试环境
            planner = self.setup_test_environment(config.get('num_ais_targets', 10))
            current_position = config.get('current_position', (31.23, 121.508))
            
            # 测量规划时间
            print("测量规划时间...")
            time_stats = self.measure_planning_time(planner, current_position)
            print(f"  平均时间: {time_stats['mean']:.3f}秒")
            print(f"  最小/最大: {time_stats['min']:.3f}/{time_stats['max']:.3f}秒")
            
            # 获取一次路径用于粒度测量
            route = planner.update_dynamic_route(current_position)
            
            # 测量路径粒度
            print("测量路径粒度...")
            granularity_stats = self.measure_route_granularity(route)
            print(f"  平均间距: {granularity_stats['mean']:.1f}米")
            print(f"  最大间距: {granularity_stats['max']:.1f}米")
            print(f"  路径点数: {granularity_stats['count']}")
            
            # 记录结果
            test_result = {
                "name": config['name'],
                "config": config,
                "planning_time": time_stats,
                "granularity": granularity_stats,
                "timestamp": datetime.now().isoformat()
            }
            
            self.results["tests"].append(test_result)
            
            # 性能判定
            print("\n性能评估:")
            if time_stats['mean'] < 3.0:
                print("  ✓ 规划时间满足要求 (<3秒)")
            else:
                print("  ✗ 规划时间超标 (>3秒)")
                
            if granularity_stats['max'] <= 600:  # 当前版本预期较粗
                print("  ✓ 路径粒度可接受")
            else:
                print("  ✗ 路径粒度过粗")
                
    def save_results(self, filename: str = None) -> None:
        """保存测试结果"""
        if filename is None:
            filename = f"benchmark_results_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
            
        output_path = Path(__file__).parent / filename
        with open(output_path, 'w') as f:
            json.dump(self.results, f, indent=2)
            
        print(f"\n结果已保存到: {output_path}")
        
    def compare_versions(self, v1_file: str, v2_file: str) -> None:
        """对比两个版本的性能"""
        # 加载结果
        with open(v1_file, 'r') as f:
            v1_results = json.load(f)
        with open(v2_file, 'r') as f:
            v2_results = json.load(f)
            
        print("\n版本对比分析")
        print("=" * 60)
        print(f"V1: {v1_results['version']} ({v1_results['timestamp']})")
        print(f"V2: {v2_results['version']} ({v2_results['timestamp']})")
        print("-" * 60)
        
        # 对比每个测试
        for v1_test, v2_test in zip(v1_results['tests'], v2_results['tests']):
            print(f"\n测试: {v1_test['name']}")
            
            # 规划时间对比
            v1_time = v1_test['planning_time']['mean']
            v2_time = v2_test['planning_time']['mean']
            time_improve = (v1_time - v2_time) / v1_time * 100
            
            print(f"  规划时间: {v1_time:.3f}s → {v2_time:.3f}s ({time_improve:+.1f}%)")
            
            # 粒度对比
            v1_gran = v1_test['granularity']['mean']
            v2_gran = v2_test['granularity']['mean']
            gran_improve = (v1_gran - v2_gran) / v1_gran * 100
            
            print(f"  路径粒度: {v1_gran:.1f}m → {v2_gran:.1f}m ({gran_improve:+.1f}%)")


def main():
    """主测试函数"""
    benchmark = PerformanceBenchmark()
    
    # 定义测试配置
    test_configs = [
        {
            "name": "基础场景 - 10个AIS目标",
            "num_ais_targets": 10,
            "current_position": (31.23, 121.508)
        },
        {
            "name": "复杂场景 - 20个AIS目标",
            "num_ais_targets": 20,
            "current_position": (31.23, 121.508)
        },
        {
            "name": "极限场景 - 50个AIS目标",
            "num_ais_targets": 50,
            "current_position": (31.23, 121.508)
        }
    ]
    
    # 运行基准测试
    print("动态路径规划性能基准测试")
    print("=" * 60)
    print(f"开始时间: {datetime.now()}")
    
    benchmark.run_benchmark(test_configs)
    
    # 保存结果
    benchmark.save_results()
    
    print("\n" + "=" * 60)
    print("测试完成！")
    
    # 总结
    print("\n性能总结:")
    for test in benchmark.results["tests"]:
        print(f"- {test['name']}: {test['planning_time']['mean']:.3f}s, {test['granularity']['mean']:.1f}m")


if __name__ == "__main__":
    main()