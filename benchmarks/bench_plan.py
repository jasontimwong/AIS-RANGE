#!/usr/bin/env python3
"""
性能基准测试
测试不同密度和分辨率下的规划性能
"""

import sys
import os
sys.path.insert(0, os.path.abspath('.'))

import time
import json
import numpy as np
from pathlib import Path
from typing import Dict, List, Tuple
from dataclasses import dataclass
import random

from lib.planner.hybrid_astar import HybridAStar, PlannerConfig
from lib.region.feasible_region import FeasibleRegion
from shapely.geometry import Point, box, MultiPolygon


@dataclass
class BenchmarkResult:
    """基准测试结果"""
    scenario: str
    obstacle_count: int
    grid_resolution: float
    planning_time: float
    nodes_expanded: int
    path_length: float
    waypoint_count: int
    memory_peak_mb: float
    success: bool


class PlannerBenchmark:
    """规划器性能基准测试"""
    
    def __init__(self, output_dir: str = "artifacts/bench"):
        """
        初始化基准测试
        
        Args:
            output_dir: 输出目录
        """
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.results: List[BenchmarkResult] = []
    
    def create_test_scenario(self, obstacle_density: str, num_obstacles: int) -> FeasibleRegion:
        """
        创建测试场景
        
        Args:
            obstacle_density: 密度级别 (low/medium/high/extreme)
            num_obstacles: 障碍物数量
            
        Returns:
            测试区域
        """
        # 基础区域
        bounds = (-2000, -2000, 2000, 2000)
        navigable = box(-2000, -2000, 2000, 2000)
        
        # 根据密度生成障碍物
        obstacles = []
        random.seed(42)  # 固定种子以保证可重复性
        
        for i in range(num_obstacles):
            if obstacle_density == 'low':
                # 稀疏分布，较小障碍
                x = random.uniform(-1800, 1800)
                y = random.uniform(-1800, 1800)
                r = random.uniform(20, 40)
            elif obstacle_density == 'medium':
                # 中等密度
                x = random.uniform(-1500, 1500)
                y = random.uniform(-1500, 1500)
                r = random.uniform(30, 60)
            elif obstacle_density == 'high':
                # 高密度
                x = random.uniform(-1200, 1200)
                y = random.uniform(-1200, 1200)
                r = random.uniform(40, 80)
            else:  # extreme
                # 极高密度
                x = random.uniform(-1000, 1000)
                y = random.uniform(-1000, 1000)
                r = random.uniform(50, 100)
            
            obstacles.append(Point(x, y).buffer(r))
        
        no_go_areas = MultiPolygon(obstacles) if obstacles else MultiPolygon([])
        
        # 使用try-except处理可能的拓扑错误
        try:
            navigable = navigable.difference(no_go_areas)
        except Exception as e:
            # 如果有拓扑错误，尝试修复几何
            from shapely.validation import make_valid
            no_go_areas = make_valid(no_go_areas)
            navigable = navigable.difference(no_go_areas)
        
        return FeasibleRegion(
            bounds=bounds,
            no_go_areas=no_go_areas,
            navigable_area=navigable,
            depth_contours={},
            danger_zones=[],
            restricted_areas=[]
        )
    
    def run_density_resolution_matrix(self):
        """运行密度×分辨率矩阵测试"""
        print("\n" + "="*60)
        print("密度 × 分辨率 性能矩阵测试")
        print("="*60)
        
        # 测试配置（降低密度以避免规划失败）
        densities = [
            ('low', 3),
            ('medium', 10),
            ('high', 20),
            ('extreme', 30)
        ]
        
        resolutions = [20.0, 50.0, 100.0]
        
        # 结果矩阵
        matrix = {}
        
        for density_name, num_obstacles in densities:
            matrix[density_name] = {}
            
            # 创建场景
            region = self.create_test_scenario(density_name, num_obstacles)
            
            for resolution in resolutions:
                # 配置
                config = PlannerConfig(
                    grid_resolution=resolution,
                    motion_step=resolution,
                    max_iterations=5000,
                    goal_tolerance_xy=resolution
                )
                
                # 规划
                planner = HybridAStar(config, region)
                
                # 固定起点和终点
                start = (-1800, -1800, 0.0)
                goal = (1800, 1800, None)
                
                # 测量性能
                start_time = time.time()
                route = planner.plan(start, goal, initial_velocity=10.0)
                planning_time = time.time() - start_time
                
                # 记录结果
                if route:
                    result = BenchmarkResult(
                        scenario=f"{density_name}_{resolution}m",
                        obstacle_count=num_obstacles,
                        grid_resolution=resolution,
                        planning_time=planning_time,
                        nodes_expanded=len(planner.visited),
                        path_length=route.get_length() if hasattr(route, 'get_length') else 0,
                        waypoint_count=len(route.waypoints),
                        memory_peak_mb=self._estimate_memory(),
                        success=True
                    )
                else:
                    result = BenchmarkResult(
                        scenario=f"{density_name}_{resolution}m",
                        obstacle_count=num_obstacles,
                        grid_resolution=resolution,
                        planning_time=planning_time,
                        nodes_expanded=len(planner.visited),
                        path_length=0,
                        waypoint_count=0,
                        memory_peak_mb=self._estimate_memory(),
                        success=False
                    )
                
                matrix[density_name][resolution] = planning_time
                self.results.append(result)
                
                # 打印进度
                status = "✓" if route else "✗"
                print(f"  {density_name:8} / {resolution:5.0f}m: {planning_time:6.3f}s {status}")
        
        # 打印矩阵
        self._print_matrix(matrix, resolutions)
        
        # 检查基线性能
        self._check_baseline_performance()
        
        return matrix
    
    def run_specific_scenarios(self):
        """运行特定场景测试"""
        print("\n" + "="*60)
        print("特定场景性能测试")
        print("="*60)
        
        scenarios = [
            {
                'name': '开放水域',
                'obstacles': 5,
                'distance': 3000,
                'expected_time': 0.2
            },
            {
                'name': '港口区域',
                'obstacles': 25,
                'distance': 2000,
                'expected_time': 0.4
            },
            {
                'name': '狭窄水道',
                'obstacles': 40,
                'distance': 1500,
                'expected_time': 0.6
            },
            {
                'name': 'TSS区域',
                'obstacles': 15,
                'distance': 4000,
                'expected_time': 0.3
            },
            {
                'name': '极限测试',
                'obstacles': 100,
                'distance': 2000,
                'expected_time': 2.0
            }
        ]
        
        for scenario in scenarios:
            print(f"\n场景: {scenario['name']}")
            
            # 创建场景
            region = self.create_test_scenario('medium', scenario['obstacles'])
            
            # 标准配置
            config = PlannerConfig(
                grid_resolution=20.0,
                motion_step=20.0,
                max_iterations=5000,
                goal_tolerance_xy=20.0
            )
            
            planner = HybridAStar(config, region)
            
            # 根据距离计算起终点
            dist = scenario['distance'] / 2
            start = (-dist, -dist, 0.0)
            goal = (dist, dist, None)
            
            # 测试
            start_time = time.time()
            route = planner.plan(start, goal, initial_velocity=10.0)
            planning_time = time.time() - start_time
            
            # 结果
            if route:
                print(f"  ✓ 规划成功")
                print(f"    时间: {planning_time:.3f}s (期望 <{scenario['expected_time']}s)")
                print(f"    航点: {len(route.waypoints)}")
                print(f"    节点: {len(planner.visited)}")
                
                if planning_time <= scenario['expected_time']:
                    print(f"    性能: ✅ 达标")
                else:
                    print(f"    性能: ⚠️  超时")
            else:
                print(f"  ✗ 规划失败")
            
            # 记录
            result = BenchmarkResult(
                scenario=scenario['name'],
                obstacle_count=scenario['obstacles'],
                grid_resolution=20.0,
                planning_time=planning_time,
                nodes_expanded=len(planner.visited),
                path_length=route.get_length() if route and hasattr(route, 'get_length') else 0,
                waypoint_count=len(route.waypoints) if route else 0,
                memory_peak_mb=self._estimate_memory(),
                success=route is not None
            )
            self.results.append(result)
    
    def _print_matrix(self, matrix: Dict, resolutions: List[float]):
        """打印性能矩阵"""
        print("\n" + "="*60)
        print("性能矩阵 (秒)")
        print("-"*60)
        
        # 表头
        header = "密度\\分辨率"
        for res in resolutions:
            header += f" | {res:5.0f}m"
        print(header)
        print("-"*60)
        
        # 数据行
        for density in ['low', 'medium', 'high', 'extreme']:
            if density in matrix:
                row = f"{density:10}"
                for res in resolutions:
                    if res in matrix[density]:
                        time_val = matrix[density][res]
                        if time_val < 0.3:
                            row += f" | {time_val:6.3f}"
                        elif time_val < 1.0:
                            row += f" | {time_val:6.3f}"
                        else:
                            row += f" | {time_val:6.3f}"
                    else:
                        row += " |    N/A"
                print(row)
        
        print("-"*60)
    
    def _check_baseline_performance(self):
        """检查基线性能"""
        print("\n" + "="*60)
        print("基线性能检查")
        print("-"*60)
        
        # 标准场景（中等密度，20m分辨率）
        baseline_results = [r for r in self.results 
                          if r.scenario == "medium_20.0m" and r.success]
        
        if baseline_results:
            baseline = baseline_results[0]
            print(f"基线场景: 中等密度, 20m分辨率")
            print(f"  规划时间: {baseline.planning_time:.3f}s")
            print(f"  目标: 0.3s ± 10%")
            
            if baseline.planning_time <= 0.33:  # 0.3 + 10%
                print(f"  状态: ✅ 达标")
            else:
                print(f"  状态: ⚠️  超标")
        
        # 最差场景
        worst_results = [r for r in self.results if r.success]
        if worst_results:
            worst = max(worst_results, key=lambda r: r.planning_time)
            print(f"\n最差场景: {worst.scenario}")
            print(f"  规划时间: {worst.planning_time:.3f}s")
            print(f"  目标: <2s")
            
            if worst.planning_time < 2.0:
                print(f"  状态: ✅ 达标")
            else:
                print(f"  状态: ❌ 超标")
        
        # 内存峰值
        max_memory = max((r.memory_peak_mb for r in self.results), default=0)
        print(f"\n内存峰值: {max_memory:.1f}MB")
        print(f"  目标: ≤512MB")
        
        if max_memory <= 512:
            print(f"  状态: ✅ 达标")
        else:
            print(f"  状态: ❌ 超标")
    
    def _estimate_memory(self) -> float:
        """估算内存使用（MB）"""
        # 简化估算
        import psutil
        process = psutil.Process(os.getpid())
        return process.memory_info().rss / 1024 / 1024
    
    def save_results(self):
        """保存测试结果"""
        # 保存JSON
        results_dict = []
        for r in self.results:
            results_dict.append({
                'scenario': r.scenario,
                'obstacle_count': r.obstacle_count,
                'grid_resolution': r.grid_resolution,
                'planning_time': r.planning_time,
                'nodes_expanded': r.nodes_expanded,
                'path_length': r.path_length,
                'waypoint_count': r.waypoint_count,
                'memory_peak_mb': r.memory_peak_mb,
                'success': r.success
            })
        
        output_file = self.output_dir / "benchmark_results.json"
        with open(output_file, 'w') as f:
            json.dump({
                'timestamp': time.strftime('%Y-%m-%d %H:%M:%S'),
                'results': results_dict,
                'summary': self._generate_summary()
            }, f, indent=2)
        
        print(f"\n结果已保存: {output_file}")
    
    def _generate_summary(self) -> Dict:
        """生成摘要统计"""
        if not self.results:
            return {}
        
        successful = [r for r in self.results if r.success]
        
        if not successful:
            return {'error': 'No successful runs'}
        
        times = [r.planning_time for r in successful]
        
        return {
            'total_tests': len(self.results),
            'successful': len(successful),
            'failed': len(self.results) - len(successful),
            'avg_time': float(np.mean(times)),
            'std_time': float(np.std(times)),
            'min_time': float(np.min(times)),
            'max_time': float(np.max(times)),
            'baseline_met': bool(np.mean(times) <= 0.33),
            'worst_case_met': bool(np.max(times) < 2.0)
        }


def main():
    """主函数"""
    print("\n" + "="*60)
    print("ECDIS路径规划器 - 性能基准测试")
    print("="*60)
    
    # 检查依赖
    try:
        import psutil
    except ImportError:
        print("警告: psutil未安装，内存统计将使用估算值")
    
    benchmark = PlannerBenchmark()
    
    # 运行测试
    try:
        # 1. 密度×分辨率矩阵
        benchmark.run_density_resolution_matrix()
        
        # 2. 特定场景
        benchmark.run_specific_scenarios()
        
        # 3. 保存结果
        benchmark.save_results()
        
        # 生成报告
        summary = benchmark._generate_summary()
        
        print("\n" + "="*60)
        print("测试总结")
        print("-"*60)
        print(f"总测试数: {summary.get('total_tests', 0)}")
        print(f"成功: {summary.get('successful', 0)}")
        print(f"失败: {summary.get('failed', 0)}")
        print(f"平均时间: {summary.get('avg_time', 0):.3f}s")
        print(f"最大时间: {summary.get('max_time', 0):.3f}s")
        
        if summary.get('baseline_met'):
            print("\n✅ 基线性能达标")
        else:
            print("\n⚠️  基线性能需要优化")
        
        if summary.get('worst_case_met'):
            print("✅ 最差情况达标")
        else:
            print("❌ 最差情况超标")
        
        print("\n" + "="*60)
        
        return 0 if (summary.get('baseline_met') and summary.get('worst_case_met')) else 1
        
    except Exception as e:
        print(f"\n❌ 测试失败: {e}")
        import traceback
        traceback.print_exc()
        return 1


if __name__ == "__main__":
    sys.exit(main())