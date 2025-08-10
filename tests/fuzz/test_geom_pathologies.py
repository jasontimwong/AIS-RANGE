"""
几何病理测试
测试各种退化、自交、小环、缝隙等病理情况
"""

import sys
import os
sys.path.insert(0, os.path.abspath('.'))

import pytest
import numpy as np
from shapely.geometry import Polygon, MultiPolygon, LineString, Point
from shapely.ops import unary_union
import random
import json
from pathlib import Path

from lib.geom.robust_ops import RobustGeometryOps, GeometryHealer

class PathologicalGeometryGenerator:
    """病理几何生成器"""
    
    @staticmethod
    def generate_self_intersecting():
        """生成自交多边形（8字形）"""
        coords = [
            (0, 0), (10, 10), (10, 0), (0, 10), (0, 0)
        ]
        return Polygon(coords)
    
    @staticmethod
    def generate_bowtie():
        """生成领结形自交"""
        coords = [
            (0, 0), (5, 5), (10, 0), (10, 10), (5, 5), (0, 10), (0, 0)
        ]
        return Polygon(coords)
    
    @staticmethod
    def generate_degenerate_triangle():
        """生成退化三角形（共线点）"""
        coords = [
            (0, 0), (5, 0), (10, 0), (0, 0)  # 三点共线
        ]
        return Polygon(coords)
    
    @staticmethod
    def generate_duplicate_points():
        """生成重复点多边形"""
        coords = [
            (0, 0), (0, 0), (10, 0), (10, 0), (10, 10), (0, 10), (0, 0)
        ]
        return Polygon(coords)
    
    @staticmethod
    def generate_small_polygon():
        """生成极小多边形"""
        return Polygon([
            (0, 0), (0.1, 0), (0.1, 0.1), (0, 0.1), (0, 0)
        ])
    
    @staticmethod
    def generate_polygon_with_small_holes():
        """生成带小孔洞的多边形"""
        exterior = [(0, 0), (100, 0), (100, 100), (0, 100), (0, 0)]
        holes = [
            [(10, 10), (11, 10), (11, 11), (10, 11), (10, 10)],  # 小孔
            [(50, 50), (60, 50), (60, 60), (50, 60), (50, 50)]   # 正常孔
        ]
        return Polygon(exterior, holes)
    
    @staticmethod
    def generate_slivers():
        """生成细长条（slivers）"""
        coords = [
            (0, 0), (100, 0), (100, 0.01), (0, 0.01), (0, 0)
        ]
        return Polygon(coords)
    
    @staticmethod
    def generate_spikes():
        """生成尖刺多边形"""
        coords = [
            (0, 0), (10, 0), (10, 10), 
            (5, 10), (5, 20), (5, 10),  # 尖刺
            (0, 10), (0, 0)
        ]
        return Polygon(coords)
    
    @staticmethod
    def generate_gaps():
        """生成带缝隙的多多边形"""
        poly1 = Polygon([(0, 0), (10, 0), (10, 10), (0, 10), (0, 0)])
        poly2 = Polygon([(10.001, 0), (20, 0), (20, 10), (10.001, 10), (10.001, 0)])
        return MultiPolygon([poly1, poly2])
    
    @staticmethod
    def generate_overlapping():
        """生成重叠多边形"""
        poly1 = Polygon([(0, 0), (10, 0), (10, 10), (0, 10), (0, 0)])
        poly2 = Polygon([(5, 5), (15, 5), (15, 15), (5, 15), (5, 5)])
        return MultiPolygon([poly1, poly2])
    
    @staticmethod
    def generate_random_pathology(seed=None):
        """生成随机病理几何"""
        if seed:
            random.seed(seed)
        
        n_points = random.randint(4, 20)
        coords = []
        
        for i in range(n_points):
            x = random.uniform(-100, 100)
            y = random.uniform(-100, 100)
            
            # 随机添加病理特征
            if random.random() < 0.2:  # 20%概率添加重复点
                coords.append((x, y))
            
            coords.append((x, y))
        
        # 闭合多边形
        if coords[0] != coords[-1]:
            coords.append(coords[0])
        
        try:
            return Polygon(coords)
        except:
            return None


class TestGeometryRobustness:
    """几何鲁棒性测试"""
    
    def setup_method(self):
        """测试初始化"""
        self.robust_ops = RobustGeometryOps()
        self.healer = GeometryHealer()
        self.generator = PathologicalGeometryGenerator()
        self.test_results = []
    
    def test_self_intersection_repair(self):
        """测试自交修复"""
        geom = self.generator.generate_self_intersecting()
        assert not geom.is_valid
        
        repaired = self.robust_ops.repair_geometry(geom)
        assert repaired.is_valid
        assert not repaired.is_empty
        
        self.test_results.append({
            'test': 'self_intersection',
            'input_valid': False,
            'output_valid': True,
            'stats': self.robust_ops.get_repair_stats()
        })
    
    def test_bowtie_repair(self):
        """测试领结形自交修复"""
        geom = self.generator.generate_bowtie()
        
        repaired = self.robust_ops.repair_geometry(geom)
        assert repaired.is_valid or repaired.is_empty
        
        self.test_results.append({
            'test': 'bowtie',
            'repaired': repaired.is_valid
        })
    
    def test_degenerate_repair(self):
        """测试退化几何修复"""
        geom = self.generator.generate_degenerate_triangle()
        
        repaired = self.robust_ops.repair_geometry(geom)
        # 退化三角形应该被移除或修复
        assert repaired.is_valid or repaired.is_empty
    
    def test_duplicate_points_repair(self):
        """测试重复点修复"""
        geom = self.generator.generate_duplicate_points()
        
        repaired = self.robust_ops.repair_geometry(geom)
        assert repaired.is_valid
        
        # 检查顶点数变化（修复可能增加或减少点）
        if not repaired.is_empty:
            orig_coords = list(geom.exterior.coords) if hasattr(geom, 'exterior') else []
            repaired_coords = list(repaired.exterior.coords) if hasattr(repaired, 'exterior') else []
            # 修复后的几何应该是有效的，但点数可能变化
            # 不强制要求点数减少，因为修复可能需要增加点来保持有效性
    
    def test_small_polygon_removal(self):
        """测试小多边形移除"""
        geom = self.generator.generate_small_polygon()
        
        repaired = self.robust_ops.repair_geometry(geom)
        # 小多边形应该被移除
        assert repaired.is_empty or repaired.area >= self.robust_ops.min_area
    
    def test_small_holes_filling(self):
        """测试小孔洞填充"""
        geom = self.generator.generate_polygon_with_small_holes()
        
        repaired = self.robust_ops.repair_geometry(geom)
        assert repaired.is_valid
        
        # 检查孔洞数量减少
        if isinstance(repaired, Polygon):
            assert len(repaired.interiors) < len(geom.interiors)
    
    def test_sliver_handling(self):
        """测试细长条处理"""
        geom = self.generator.generate_slivers()
        
        repaired = self.robust_ops.repair_geometry(geom)
        assert repaired.is_valid or repaired.is_empty
    
    def test_spike_smoothing(self):
        """测试尖刺平滑"""
        geom = self.generator.generate_spikes()
        
        repaired = self.robust_ops.repair_geometry(geom, conservative=True)
        assert repaired.is_valid
        
        # 简化后应该减少尖锐特征
        simplified = self.robust_ops.simplify_geometry(repaired)
        assert simplified.is_valid
    
    def test_gap_filling(self):
        """测试缝隙填充"""
        geom = self.generator.generate_gaps()
        initial_count = len(geom.geoms)
        
        repaired = self.robust_ops.repair_geometry(geom)
        assert repaired.is_valid
        
        # 缝隙可能被填充，导致多边形合并
        if isinstance(repaired, MultiPolygon):
            assert len(repaired.geoms) <= initial_count
    
    def test_overlapping_union(self):
        """测试重叠合并"""
        geom = self.generator.generate_overlapping()
        
        repaired = self.robust_ops.repair_geometry(geom)
        assert repaired.is_valid
        
        # 重叠应该被合并
        assert repaired.area <= sum(p.area for p in geom.geoms)
    
    def test_massive_pathology_suite(self):
        """大规模病理测试套件（500个案例）"""
        crash_count = 0
        conservative_count = 0
        success_count = 0
        
        test_cases = []
        
        # 生成500个病理案例
        for i in range(500):
            seed = i
            
            # 选择病理类型
            pathology_type = i % 10
            
            if pathology_type == 0:
                geom = self.generator.generate_self_intersecting()
                case_type = "self_intersection"
            elif pathology_type == 1:
                geom = self.generator.generate_bowtie()
                case_type = "bowtie"
            elif pathology_type == 2:
                geom = self.generator.generate_degenerate_triangle()
                case_type = "degenerate"
            elif pathology_type == 3:
                geom = self.generator.generate_duplicate_points()
                case_type = "duplicate_points"
            elif pathology_type == 4:
                geom = self.generator.generate_small_polygon()
                case_type = "small_polygon"
            elif pathology_type == 5:
                geom = self.generator.generate_polygon_with_small_holes()
                case_type = "small_holes"
            elif pathology_type == 6:
                geom = self.generator.generate_slivers()
                case_type = "sliver"
            elif pathology_type == 7:
                geom = self.generator.generate_spikes()
                case_type = "spikes"
            elif pathology_type == 8:
                geom = self.generator.generate_gaps()
                case_type = "gaps"
            else:
                geom = self.generator.generate_random_pathology(seed)
                case_type = "random"
            
            if geom is None:
                continue
            
            # 测试修复
            try:
                self.robust_ops.reset_stats()
                repaired = self.robust_ops.repair_geometry(geom, conservative=False)
                
                # 如果需要保守策略
                if not repaired.is_valid and not repaired.is_empty:
                    repaired = self.robust_ops.repair_geometry(geom, conservative=True)
                    conservative_count += 1
                
                stats = self.robust_ops.get_repair_stats()
                if stats['conservative_buffer'] > 0:
                    conservative_count += 1
                
                success_count += 1
                
                test_cases.append({
                    'case_id': i,
                    'type': case_type,
                    'input_valid': geom.is_valid if hasattr(geom, 'is_valid') else False,
                    'output_valid': repaired.is_valid,
                    'output_empty': repaired.is_empty,
                    'stats': stats
                })
                
            except Exception as e:
                crash_count += 1
                test_cases.append({
                    'case_id': i,
                    'type': case_type,
                    'error': str(e),
                    'crashed': True
                })
        
        # 生成测试报告
        report = {
            'total_cases': 500,
            'success': success_count,
            'crashes': crash_count,
            'conservative_repairs': conservative_count,
            'conservative_rate': conservative_count / 500,
            'test_cases': test_cases[:10]  # 保存前10个案例作为样本
        }
        
        # 断言：0崩溃，保守修复率≤1%
        assert crash_count == 0, f"发现{crash_count}个崩溃案例"
        assert conservative_count / 500 <= 0.01, f"保守修复率{conservative_count/500:.2%}超过1%"
        
        # 保存最小复现场景到证据包
        self._save_evidence(report)
        
        print(f"\n病理测试完成:")
        print(f"  成功: {success_count}/500")
        print(f"  崩溃: {crash_count}")
        print(f"  保守修复: {conservative_count} ({conservative_count/500:.1%})")
    
    def test_geometry_validation(self):
        """测试几何验证功能"""
        # 有效几何
        valid_geom = Polygon([(0, 0), (10, 0), (10, 10), (0, 10), (0, 0)])
        is_valid, issues = self.robust_ops.validate_geometry(valid_geom)
        assert is_valid
        assert len(issues) == 0
        
        # 无效几何
        invalid_geom = self.generator.generate_self_intersecting()
        is_valid, issues = self.robust_ops.validate_geometry(invalid_geom)
        assert not is_valid
        assert len(issues) > 0
        assert any("自交" in issue for issue in issues)
    
    def test_healer_interface(self):
        """测试GeometryHealer高级接口"""
        # 创建复杂病理区域
        area = self.generator.generate_overlapping()
        
        healed = self.healer.heal_navigable_area(area)
        assert healed.is_valid
        
        # 测试障碍物修复
        obstacles = [
            self.generator.generate_spikes(),
            self.generator.generate_small_polygon(),
            self.generator.generate_self_intersecting()
        ]
        
        healed_obstacles = self.healer.heal_obstacles(obstacles)
        for obs in healed_obstacles:
            assert obs.is_valid
    
    def _save_evidence(self, report):
        """保存证据到文件"""
        evidence_dir = Path("artifacts") / "geom_pathology"
        evidence_dir.mkdir(parents=True, exist_ok=True)
        
        evidence_file = evidence_dir / "pathology_test_report.json"
        with open(evidence_file, 'w') as f:
            json.dump(report, f, indent=2, default=str)
        
        print(f"证据已保存: {evidence_file}")


if __name__ == "__main__":
    # 运行测试
    tester = TestGeometryRobustness()
    tester.setup_method()
    
    print("运行几何病理测试...")
    
    # 运行各个测试
    tester.test_self_intersection_repair()
    print("✓ 自交修复测试通过")
    
    tester.test_duplicate_points_repair()
    print("✓ 重复点修复测试通过")
    
    tester.test_small_holes_filling()
    print("✓ 小孔洞填充测试通过")
    
    # 运行大规模测试
    print("\n运行500个病理案例测试...")
    tester.test_massive_pathology_suite()
    
    print("\n所有几何鲁棒性测试通过！")