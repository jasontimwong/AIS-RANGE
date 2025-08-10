#!/usr/bin/env python3
"""
S-164 IHO测试数据集运行器
执行标准测试场景的加载→规划→校核→证据包流程
"""

import argparse
import sys
import os
import json
import time
from pathlib import Path
from datetime import datetime

# 添加项目路径
sys.path.insert(0, os.path.abspath('.'))

from lib.enc.s57_reader import S57Reader
from lib.enc.s101_adapter import S101Adapter
from lib.region.feasible_region import FeasibleRegion
from lib.region.tss_layers import TSSZones
from lib.planner.hybrid_astar import HybridAStar, PlannerConfig
from lib.checks.route_checker import RouteChecker
from lib.io.rtz import RTZConverter
from tools.evidence_pack import EvidencePackGenerator

# S-164测试场景定义
S164_SCENARIOS = {
    'open_water_tss': {
        'name': 'Open Water TSS',
        'description': 'Traffic Separation Scheme in open waters',
        'start': (-122.8, 37.8, 0.0),
        'goal': (-122.4, 37.85, None),
        'vessel_draft': 12.0,
        'safety_depth': 15.0,
        'expected_checks': {
            'tss_compliance': True,
            'safety_depth': True,
            'min_time_s': 300,
            'max_time_s': 600
        }
    },
    'coastal_shallow': {
        'name': 'Coastal Shallow Waters',
        'description': 'Navigation in shallow coastal waters with obstacles',
        'start': (-122.6, 37.75, 0.0),
        'goal': (-122.45, 37.78, None),
        'vessel_draft': 8.0,
        'safety_depth': 10.0,
        'expected_checks': {
            'safety_contour': True,
            'obstacle_avoidance': True,
            'min_clearance_m': 50,
            'max_time_s': 480
        }
    },
    'harbor_approach': {
        'name': 'Harbor Approach',
        'description': 'Approach to harbor with speed restrictions',
        'start': (-122.5, 37.77, 0.0),
        'goal': (-122.42, 37.79, None),
        'vessel_draft': 10.0,
        'safety_depth': 12.0,
        'expected_checks': {
            'speed_limits': True,
            'anchorage_avoidance': True,
            'min_cpa_m': 100,
            'max_time_s': 720
        }
    }
}


class S164TestRunner:
    """S-164测试运行器"""
    
    def __init__(self, scenario_name: str, enc_path: str, output_dir: str):
        """
        初始化测试运行器
        
        Args:
            scenario_name: 场景名称
            enc_path: ENC数据路径
            output_dir: 输出目录
        """
        self.scenario_name = scenario_name
        self.scenario = S164_SCENARIOS.get(scenario_name)
        if not self.scenario:
            raise ValueError(f"Unknown scenario: {scenario_name}")
        
        self.enc_path = Path(enc_path)
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)
        
        self.test_results = {
            'scenario': scenario_name,
            'timestamp': datetime.now().isoformat(),
            'status': 'pending'
        }
    
    def run(self) -> bool:
        """
        运行测试场景
        
        Returns:
            是否成功
        """
        print(f"\n{'='*60}")
        print(f"S-164 测试场景: {self.scenario['name']}")
        print(f"描述: {self.scenario['description']}")
        print(f"{'='*60}\n")
        
        try:
            # 1. 加载ENC数据
            print("1. 加载ENC数据...")
            region = self._load_enc_data()
            
            # 2. 执行路径规划
            print("2. 执行路径规划...")
            route, plan_time = self._plan_route(region)
            
            # 3. 执行合规检查
            print("3. 执行合规检查...")
            validation_report = self._validate_route(route, region)
            
            # 4. 生成证据包
            print("4. 生成证据包...")
            evidence_path = self._generate_evidence(route, validation_report)
            
            # 5. 检查验收标准
            print("5. 检查验收标准...")
            passed = self._check_acceptance(validation_report, plan_time)
            
            self.test_results['status'] = 'passed' if passed else 'failed'
            self.test_results['planning_time'] = plan_time
            self.test_results['validation_summary'] = {
                'total_checks': validation_report.total_checks,
                'passed': validation_report.passed_checks,
                'failed': validation_report.failed_checks,
                'is_valid': validation_report.is_valid
            }
            
            # 保存测试结果
            self._save_results()
            
            print(f"\n测试结果: {'✅ 通过' if passed else '❌ 失败'}")
            return passed
            
        except Exception as e:
            print(f"测试失败: {e}")
            self.test_results['status'] = 'error'
            self.test_results['error'] = str(e)
            self._save_results()
            return False
    
    def _load_enc_data(self) -> FeasibleRegion:
        """加载ENC数据"""
        # 尝试使用S-101适配器
        if self.enc_path.suffix == '.s101':
            adapter = S101Adapter()
            adapter.load_s101(str(self.enc_path))
            region_data = adapter.get_feasible_region()
        else:
            # 使用S-57读取器
            reader = S57Reader(str(self.enc_path))
            reader.load()
            region_data = reader.get_feasible_region()
        
        # 创建可行域
        region = FeasibleRegion(
            bounds=region_data.get('bounds', (-123, 37.5, -122, 38)),
            no_go_areas=region_data.get('no_go_areas'),
            navigable_area=region_data.get('navigable_area'),
            depth_contours=region_data.get('depth_contours', {}),
            danger_zones=[],
            restricted_areas=[]
        )
        
        # 添加TSS信息
        if region_data.get('tss_zones'):
            region.tss_zones = TSSZones()
            for zone in region_data['tss_zones']:
                region.tss_zones.add_zone(
                    zone['geometry'],
                    zone.get('direction', 0),
                    zone.get('type', 'lane')
                )
        
        print(f"  ✓ 加载完成: 可航区域 {region.navigable_area.area:.2f} m²")
        return region
    
    def _plan_route(self, region: FeasibleRegion):
        """执行路径规划"""
        config = PlannerConfig(
            grid_resolution=50.0,
            motion_step=50.0,
            max_iterations=5000,
            goal_tolerance_xy=50.0
        )
        
        planner = HybridAStar(config, region)
        
        start_time = time.time()
        route = planner.plan(
            start=self.scenario['start'],
            goal=self.scenario['goal'],
            initial_velocity=10.0
        )
        plan_time = time.time() - start_time
        
        if route:
            print(f"  ✓ 规划成功: {len(route.waypoints)} 个航点, 耗时 {plan_time:.2f}s")
            
            # 保存路径
            rtz_converter = RTZConverter()
            rtz_path = self.output_dir / f"{self.scenario_name}_route.rtz"
            rtz_converter.write_rtz(route, str(rtz_path))
        else:
            raise RuntimeError("路径规划失败")
        
        return route, plan_time
    
    def _validate_route(self, route, region: FeasibleRegion):
        """验证路径合规性"""
        checker = RouteChecker(
            feasible_region=region,
            safety_depth=self.scenario['safety_depth'],
            xtd_limit=185.2,  # 0.1 NM
            min_cpa=100.0
        )
        
        report = checker.validate_route(route, route_name=self.scenario_name)
        
        print(f"  ✓ 检查完成: {report.passed_checks}/{report.total_checks} 通过")
        
        # 保存验证报告
        report_path = self.output_dir / f"{self.scenario_name}_validation.json"
        with open(report_path, 'w') as f:
            f.write(report.to_json())
        
        # 输出关键条款引用
        self._print_clause_refs(report)
        
        return report
    
    def _print_clause_refs(self, report):
        """打印条款引用"""
        all_checks = (report.safety_checks + report.tss_checks + 
                     report.geometry_checks + report.speed_checks)
        
        clause_summary = {}
        for check in all_checks:
            for clause in check.clause_refs:
                key = f"{clause['standard']} {clause['clause']}"
                if key not in clause_summary:
                    clause_summary[key] = {
                        'requirement': clause['requirement'],
                        'compliant': 0,
                        'non_compliant': 0
                    }
                
                if clause.get('status') == 'COMPLIANT':
                    clause_summary[key]['compliant'] += 1
                else:
                    clause_summary[key]['non_compliant'] += 1
        
        if clause_summary:
            print("\n  条款合规情况:")
            for clause, stats in clause_summary.items():
                status = "✓" if stats['non_compliant'] == 0 else "✗"
                print(f"    {status} {clause}: {stats['requirement']}")
    
    def _generate_evidence(self, route, validation_report):
        """生成证据包"""
        generator = EvidencePackGenerator(output_dir=str(self.output_dir))
        
        # 保存路径和验证结果
        route_id = f"s164_{self.scenario_name}_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        
        evidence_path = generator.generate(route_id=route_id)
        print(f"  ✓ 证据包: {evidence_path}")
        
        return evidence_path
    
    def _check_acceptance(self, report, plan_time) -> bool:
        """检查验收标准"""
        expected = self.scenario['expected_checks']
        passed = True
        
        print("\n  验收标准检查:")
        
        # 检查规划时间
        if 'max_time_s' in expected:
            if plan_time <= expected['max_time_s']:
                print(f"    ✓ 规划时间: {plan_time:.2f}s ≤ {expected['max_time_s']}s")
            else:
                print(f"    ✗ 规划时间: {plan_time:.2f}s > {expected['max_time_s']}s")
                passed = False
        
        # 检查TSS合规
        if expected.get('tss_compliance'):
            tss_passed = all(c.status.value == 'pass' for c in report.tss_checks)
            if tss_passed:
                print(f"    ✓ TSS合规: 通过")
            else:
                print(f"    ✗ TSS合规: 失败")
                passed = False
        
        # 检查安全深度
        if expected.get('safety_depth'):
            safety_passed = all(c.status.value in ['pass', 'info'] 
                               for c in report.safety_checks)
            if safety_passed:
                print(f"    ✓ 安全深度: 通过")
            else:
                print(f"    ✗ 安全深度: 失败")
                passed = False
        
        # 检查最小间隙
        if 'min_clearance_m' in expected:
            min_clearance = report.metrics.get('min_clearance_m', 0)
            if min_clearance >= expected['min_clearance_m']:
                print(f"    ✓ 最小间隙: {min_clearance:.1f}m ≥ {expected['min_clearance_m']}m")
            else:
                print(f"    ✗ 最小间隙: {min_clearance:.1f}m < {expected['min_clearance_m']}m")
                passed = False
        
        return passed
    
    def _save_results(self):
        """保存测试结果"""
        results_path = self.output_dir / f"{self.scenario_name}_results.json"
        with open(results_path, 'w') as f:
            json.dump(self.test_results, f, indent=2)


def main():
    """主函数"""
    parser = argparse.ArgumentParser(description='S-164测试运行器')
    parser.add_argument('--scenario', required=True, 
                       choices=list(S164_SCENARIOS.keys()),
                       help='测试场景名称')
    parser.add_argument('--enc-path', required=True, help='ENC数据路径')
    parser.add_argument('--output', required=True, help='输出目录')
    
    args = parser.parse_args()
    
    # 检查feature flag
    if os.environ.get('FEATURE_FLAG_S164', 'false').lower() != 'true':
        print("S-164测试未启用 (FEATURE_FLAG_S164=false)")
        return 0
    
    runner = S164TestRunner(args.scenario, args.enc_path, args.output)
    success = runner.run()
    
    return 0 if success else 1


if __name__ == "__main__":
    sys.exit(main())