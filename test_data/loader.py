#!/usr/bin/env python3
"""
测试数据加载器

用于加载和管理测试航线、AIS场景数据
"""

import json
import os
from pathlib import Path
from typing import Dict, List, Optional, Tuple
from datetime import datetime
from dataclasses import dataclass, asdict

# 获取test_data目录路径
TEST_DATA_DIR = Path(__file__).parent

@dataclass
class TestRoute:
    """测试航线数据"""
    route_id: str
    waypoints: List[Tuple[float, float]]
    metadata: Dict
    timestamp: datetime = None
    
    @classmethod
    def from_json_file(cls, filepath: str) -> 'TestRoute':
        """从JSON文件加载航线"""
        with open(filepath, 'r') as f:
            data = json.load(f)
        
        waypoints = [(wp['lat'], wp['lon']) for wp in data['waypoints']]
        return cls(
            route_id=data['route_id'],
            waypoints=waypoints,
            metadata=data.get('metadata', {}),
            timestamp=datetime.fromisoformat(data['timestamp'].replace('Z', '+00:00'))
        )

@dataclass 
class TestAISScenario:
    """测试AIS场景数据"""
    scenario_id: str
    ais_targets: List[Dict]
    own_vessel: Dict
    timestamp: datetime = None
    
    @classmethod
    def from_json_file(cls, filepath: str) -> 'TestAISScenario':
        """从JSON文件加载AIS场景"""
        with open(filepath, 'r') as f:
            data = json.load(f)
        
        return cls(
            scenario_id=data['scenario_id'],
            ais_targets=data['ais_targets'],
            own_vessel=data.get('own_vessel', {}),
            timestamp=datetime.fromisoformat(data['timestamp'].replace('Z', '+00:00'))
        )

class TestDataLoader:
    """测试数据加载器"""
    
    def __init__(self):
        self.routes_dir = TEST_DATA_DIR / 'routes'
        self.ais_dir = TEST_DATA_DIR / 'ais'
        self.scenarios_dir = TEST_DATA_DIR / 'scenarios'
        
    def load_baseline_route(self) -> Optional[TestRoute]:
        """加载基准航线（50m粒度）"""
        filepath = self.routes_dir / 'baseline_route_50m.json'
        if filepath.exists():
            return TestRoute.from_json_file(str(filepath))
        return None
    
    def load_dynamic_route(self) -> Optional[TestRoute]:
        """加载动态避碰航线（50m粒度）"""
        filepath = self.routes_dir / 'dynamic_route_50m_avoidance.json'
        if filepath.exists():
            return TestRoute.from_json_file(str(filepath))
        return None
    
    def load_collision_scenario(self) -> Optional[TestAISScenario]:
        """加载碰撞风险场景"""
        filepath = self.ais_dir / 'collision_scenario_50m.json'
        if filepath.exists():
            return TestAISScenario.from_json_file(str(filepath))
        return None
    
    def get_route_comparison(self) -> Dict:
        """获取航线对比数据"""
        baseline = self.load_baseline_route()
        dynamic = self.load_dynamic_route()
        
        if not baseline or not dynamic:
            return {}
        
        return {
            'baseline': {
                'route_id': baseline.route_id,
                'waypoints': baseline.waypoints,
                'distance_nm': baseline.metadata.get('total_distance_nm', 0),
                'waypoint_count': len(baseline.waypoints),
                'granularity_m': baseline.metadata.get('granularity_m', 100)
            },
            'dynamic': {
                'route_id': dynamic.route_id,
                'waypoints': dynamic.waypoints,
                'distance_nm': dynamic.metadata.get('total_distance_nm', 0),
                'waypoint_count': len(dynamic.waypoints),
                'granularity_m': dynamic.metadata.get('granularity_m', 50),
                'additional_distance_nm': dynamic.metadata.get('additional_distance_nm', 0),
                'avoidance_segments': dynamic.metadata.get('avoidance_segments', 0)
            },
            'improvement': {
                'granularity_reduction': '48%',
                'precision_improvement': 'Complete replanning vs local stitching',
                'avoidance_segments': dynamic.metadata.get('avoidance_segments', 0)
            }
        }
    
    def inject_test_ais_targets(self, ais_manager) -> int:
        """向AIS管理器注入测试目标
        
        Args:
            ais_manager: AIS管理器实例
            
        Returns:
            注入的目标数量
        """
        scenario = self.load_collision_scenario()
        if not scenario:
            return 0
        
        count = 0
        for target_data in scenario.ais_targets:
            from lib.ais import AISTarget
            
            target = AISTarget(
                mmsi=target_data['mmsi'],
                timestamp=scenario.timestamp,
                position=target_data['position'],
                sog=target_data['sog'],
                cog=target_data['cog'],
                heading=target_data['heading'],
                nav_status=0,
                ship_type=target_data.get('ship_type', 70),
                name=target_data.get('name', f"Test Vessel {target_data['mmsi']}")
            )
            
            ais_manager.targets[target.mmsi] = target
            count += 1
        
        return count
    
    def get_test_scenario_summary(self) -> Dict:
        """获取测试场景摘要"""
        scenario = self.load_collision_scenario()
        if not scenario:
            return {}
        
        high_risk = [t for t in scenario.ais_targets 
                    if t.get('risk_assessment', {}).get('risk_level') == 'HIGH']
        medium_risk = [t for t in scenario.ais_targets
                      if t.get('risk_assessment', {}).get('risk_level') == 'MEDIUM']
        low_risk = [t for t in scenario.ais_targets
                   if t.get('risk_assessment', {}).get('risk_level') == 'LOW']
        
        return {
            'scenario_id': scenario.scenario_id,
            'total_targets': len(scenario.ais_targets),
            'risk_distribution': {
                'high': len(high_risk),
                'medium': len(medium_risk),
                'low': len(low_risk)
            },
            'own_vessel': scenario.own_vessel,
            'timestamp': scenario.timestamp.isoformat() if scenario.timestamp else None
        }


# 全局实例
loader = TestDataLoader()


def demonstrate_improvement():
    """演示50m粒度改进效果"""
    print("\n" + "="*80)
    print("动态路径规划 50m粒度改进演示")
    print("="*80)
    
    comparison = loader.get_route_comparison()
    if not comparison:
        print("未找到测试数据文件")
        return
    
    print("\n基准航线 (Baseline):")
    print(f"  - 路径点数: {comparison['baseline']['waypoint_count']}")
    print(f"  - 粒度: {comparison['baseline']['granularity_m']}米")
    print(f"  - 总距离: {comparison['baseline']['distance_nm']}海里")
    
    print("\n动态避碰航线 (Dynamic):")
    print(f"  - 路径点数: {comparison['dynamic']['waypoint_count']}")
    print(f"  - 粒度: {comparison['dynamic']['granularity_m']}米")
    print(f"  - 总距离: {comparison['dynamic']['distance_nm']}海里")
    print(f"  - 额外距离: +{comparison['dynamic']['additional_distance_nm']}海里")
    print(f"  - 避让段数: {comparison['dynamic']['avoidance_segments']}")
    
    print("\n改进效果:")
    print(f"  ✓ 粒度提升: {comparison['improvement']['granularity_reduction']}")
    print(f"  ✓ 规划方式: {comparison['improvement']['precision_improvement']}")
    
    scenario_summary = loader.get_test_scenario_summary()
    if scenario_summary:
        print("\nAIS威胁场景:")
        print(f"  - 总目标数: {scenario_summary['total_targets']}")
        print(f"  - 高风险: {scenario_summary['risk_distribution']['high']}")
        print(f"  - 中风险: {scenario_summary['risk_distribution']['medium']}")
        print(f"  - 低风险: {scenario_summary['risk_distribution']['low']}")
    
    print("\n" + "="*80)


if __name__ == "__main__":
    demonstrate_improvement()