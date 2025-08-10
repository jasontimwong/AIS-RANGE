"""
增量重规划性能测试
"""

import sys
import os
sys.path.insert(0, os.path.abspath('.'))

import time
import numpy as np
import random
from pathlib import Path
import json
from typing import Tuple, List, Dict
# import matplotlib.pyplot as plt  # 可选依赖
from shapely.geometry import Point, box, MultiPolygon

from lib.planner.incremental_replan import IncrementalReplanner, ChangeEvent
from lib.planner.hybrid_astar import PlannerConfig
from lib.region.feasible_region import FeasibleRegion


class IncrementalReplanBenchmark:
    """增量重规划基准测试"""
    
    def __init__(self):
        """初始化测试"""
        self.results = []
        self.output_dir = Path("artifacts") / "bench"
        self.output_dir.mkdir(parents=True, exist_ok=True)
    
    def setup_test_environment(self) -> Tuple:
        """设置测试环境"""
        # 创建测试区域
        bounds = (-1000, -1000, 1000, 1000)
        navigable = box(-1000, -1000, 1000, 1000)
        
        # 添加一些初始障碍
        obstacles = []
        for _ in range(5):
            x = random.uniform(-800, 800)
            y = random.uniform(-800, 800)
            r = random.uniform(20, 50)
            obstacles.append(Point(x, y).buffer(r))
        
        no_go_areas = MultiPolygon(obstacles) if obstacles else MultiPolygon([])
        navigable = navigable.difference(no_go_areas)
        
        region = FeasibleRegion(
            bounds=bounds,
            no_go_areas=no_go_areas,
            navigable_area=navigable,
            depth_contours={},
            danger_zones=[],
            restricted_areas=[]
        )
        
        config = PlannerConfig(
            grid_resolution=20.0,
            motion_step=20.0,
            max_iterations=2000,
            goal_tolerance_xy=20.0
        )
        
        return config, region
    
    def test_incremental_performance(self):
        """测试增量重规划性能"""
        print("\n增量重规划性能测试")
        print("="*60)
        
        config, region = self.setup_test_environment()
        replanner = IncrementalReplanner(config, region)
        
        # 初始规划
        start = (-900, -900, 0.0)
        goal = (900, 900, None)
        
        print("\n1. 初始规划...")
        initial_route = replanner.plan_initial(start, goal)
        if not initial_route:
            print("初始规划失败")
            return
        
        print(f"   ✓ 初始路径: {len(initial_route.waypoints)} 航点")
        
        # 测试10个随机扰动
        replan_times = []
        scenarios = []
        
        print("\n2. 测试随机扰动...")
        for i in range(10):
            # 生成随机变更
            changes = self._generate_random_changes(i)
            scenario = f"扰动{i+1}"
            
            # 执行增量重规划
            start_time = time.time()
            new_route = replanner.replan_incremental(changes)
            elapsed = time.time() - start_time
            
            replan_times.append(elapsed)
            scenarios.append(scenario)
            
            status = "✓" if new_route else "✗"
            print(f"   {status} {scenario}: {elapsed:.3f}s")
            
            # 记录结果
            self.results.append({
                'scenario': scenario,
                'changes': len(changes),
                'time': elapsed,
                'success': new_route is not None,
                'type': 'incremental'
            })
        
        # 计算统计
        avg_time = np.mean(replan_times)
        std_time = np.std(replan_times)
        min_time = np.min(replan_times)
        max_time = np.max(replan_times)
        under_300ms = sum(1 for t in replan_times if t < 0.3)
        
        print(f"\n3. 性能统计:")
        print(f"   平均时间: {avg_time:.3f}s")
        print(f"   标准差: {std_time:.3f}s")
        print(f"   最小/最大: {min_time:.3f}s / {max_time:.3f}s")
        print(f"   <0.3s比例: {under_300ms}/10 ({under_300ms*10}%)")
        
        # 验收标准检查
        print(f"\n4. 验收标准:")
        if avg_time <= 0.3:
            print(f"   ✓ 平均时间 {avg_time:.3f}s ≤ 0.3s")
        else:
            print(f"   ✗ 平均时间 {avg_time:.3f}s > 0.3s")
        
        # 获取性能统计
        stats = replanner.get_performance_stats()
        print(f"\n5. 规划器统计:")
        print(f"   完整重规划: {stats['full_replans']}")
        print(f"   增量重规划: {stats['incremental_replans']}")
        print(f"   缓存命中: {stats['cache_hits']}")
        print(f"   缓存未中: {stats['cache_misses']}")
        
        # 保存结果
        self._save_results(replan_times, scenarios)
        
        return avg_time <= 0.3
    
    def test_comparison_full_vs_incremental(self):
        """对比完整重规划与增量重规划"""
        print("\n完整 vs 增量重规划对比")
        print("="*60)
        
        config, region = self.setup_test_environment()
        
        # 测试场景
        test_cases = [
            {'name': '小扰动', 'num_changes': 1, 'radius': 20},
            {'name': '中扰动', 'num_changes': 3, 'radius': 30},
            {'name': '大扰动', 'num_changes': 5, 'radius': 50}
        ]
        
        comparison_results = []
        
        for case in test_cases:
            print(f"\n测试: {case['name']}")
            
            # 初始化两个规划器
            full_planner = IncrementalReplanner(config, region)
            incr_planner = IncrementalReplanner(config, region)
            
            # 初始规划
            start = (-900, -900, 0.0)
            goal = (900, 900, None)
            
            full_planner.plan_initial(start, goal)
            incr_planner.plan_initial(start, goal)
            
            # 生成变更
            changes = []
            for _ in range(case['num_changes']):
                x = random.uniform(-500, 500)
                y = random.uniform(-500, 500)
                changes.append(ChangeEvent(
                    type='obstacle_added',
                    location=(x, y),
                    radius=case['radius']
                ))
            
            # 完整重规划
            start_time = time.time()
            full_route = full_planner._fallback_to_full_replan(None, None)
            full_time = time.time() - start_time
            
            # 增量重规划
            start_time = time.time()
            incr_route = incr_planner.replan_incremental(changes)
            incr_time = time.time() - start_time
            
            # 计算加速比
            speedup = full_time / incr_time if incr_time > 0 else 0
            
            print(f"  完整重规划: {full_time:.3f}s")
            print(f"  增量重规划: {incr_time:.3f}s")
            print(f"  加速比: {speedup:.2f}x")
            
            comparison_results.append({
                'case': case['name'],
                'full_time': full_time,
                'incr_time': incr_time,
                'speedup': speedup
            })
        
        # 生成对比图
        self._plot_comparison(comparison_results)
        
        return comparison_results
    
    def test_scalability(self):
        """测试可扩展性"""
        print("\n可扩展性测试")
        print("="*60)
        
        obstacle_counts = [5, 10, 20, 40]
        times = []
        
        for num_obstacles in obstacle_counts:
            config, region = self.setup_test_environment()
            
            # 添加更多障碍
            for _ in range(num_obstacles - 5):
                x = random.uniform(-800, 800)
                y = random.uniform(-800, 800)
                obs = Point(x, y).buffer(30)
                region.no_go_areas = region.no_go_areas.union(obs)
            
            replanner = IncrementalReplanner(config, region)
            
            # 初始规划
            start = (-900, -900, 0.0)
            goal = (900, 900, None)
            replanner.plan_initial(start, goal)
            
            # 测试增量重规划
            changes = self._generate_random_changes(num_obstacles)
            
            start_time = time.time()
            replanner.replan_incremental(changes)
            elapsed = time.time() - start_time
            
            times.append(elapsed)
            print(f"  {num_obstacles} 障碍物: {elapsed:.3f}s")
        
        # 检查扩展性
        if times[-1] < times[0] * 4:
            print(f"\n✓ 良好的扩展性: 40障碍物仅需 {times[-1]/times[0]:.1f}x 时间")
        else:
            print(f"\n✗ 扩展性问题: 40障碍物需要 {times[-1]/times[0]:.1f}x 时间")
        
        return times
    
    def _generate_random_changes(self, seed: int = 0) -> List[ChangeEvent]:
        """生成随机变更"""
        random.seed(seed)
        changes = []
        
        num_changes = random.randint(1, 3)
        for _ in range(num_changes):
            change_type = random.choice(['obstacle_added', 'obstacle_removed', 'cost_changed'])
            
            x = random.uniform(-500, 500)
            y = random.uniform(-500, 500)
            
            if change_type in ['obstacle_added', 'obstacle_removed']:
                changes.append(ChangeEvent(
                    type=change_type,
                    location=(x, y),
                    radius=random.uniform(10, 30)
                ))
            else:
                changes.append(ChangeEvent(
                    type=change_type,
                    location=(x, y),
                    old_value=1.0,
                    new_value=random.uniform(1.5, 3.0)
                ))
        
        return changes
    
    def _save_results(self, times: List[float], scenarios: List[str]):
        """保存测试结果"""
        # 保存JSON
        results = {
            'times': times,
            'scenarios': scenarios,
            'avg_time': np.mean(times),
            'std_time': np.std(times),
            'min_time': np.min(times),
            'max_time': np.max(times),
            'under_300ms_ratio': sum(1 for t in times if t < 0.3) / len(times)
        }
        
        json_path = self.output_dir / "incr_replan_results.json"
        with open(json_path, 'w') as f:
            json.dump(results, f, indent=2)
        
        # 生成性能曲线
        self._plot_performance_curve(times, scenarios)
        
        print(f"\n结果已保存: {json_path}")
    
    def _plot_performance_curve(self, times: List[float], scenarios: List[str]):
        """绘制性能曲线（文本版）"""
        print("\n性能曲线数据:")
        print("-" * 40)
        for i, (scenario, time) in enumerate(zip(scenarios, times)):
            bar_len = int(time * 100)  # 缩放到合适长度
            bar = "█" * min(bar_len, 50)
            marker = " ⚠️" if time > 0.3 else " ✓"
            print(f"{scenario:8} [{time:.3f}s] {bar}{marker}")
        print("-" * 40)
    
    def _plot_comparison(self, results: List[Dict]):
        """绘制对比图（文本版）"""
        print("\n重规划时间对比:")
        print("-" * 50)
        print(f"{'场景':<10} {'完整(s)':<10} {'增量(s)':<10} {'加速比':<10}")
        print("-" * 50)
        
        for r in results:
            speedup_marker = "🚀" if r['speedup'] > 2 else "✓" if r['speedup'] > 1 else "⚠️"
            print(f"{r['case']:<10} {r['full_time']:<10.3f} {r['incr_time']:<10.3f} {r['speedup']:<8.1f}x {speedup_marker}")
        
        print("-" * 50)




if __name__ == "__main__":
    # 运行基准测试
    benchmark = IncrementalReplanBenchmark()
    
    print("增量重规划基准测试")
    print("="*60)
    
    # 性能测试
    passed = benchmark.test_incremental_performance()
    
    # 对比测试
    benchmark.test_comparison_full_vs_incremental()
    
    # 可扩展性测试
    benchmark.test_scalability()
    
    print("\n" + "="*60)
    if passed:
        print("✅ 增量重规划性能达标！")
    else:
        print("⚠️ 性能未达标，需要优化")