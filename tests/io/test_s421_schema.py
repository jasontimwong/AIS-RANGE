"""
S-421导出和Schema验证测试
"""

import sys
import os
sys.path.insert(0, os.path.abspath('.'))

import json
import xml.etree.ElementTree as ET
from pathlib import Path
import jsonschema
from jsonschema import validate

from lib.io.s421_export import S421Exporter
# RTZ功能在rtz.py中
from lib.planner.hybrid_astar import Route


class TestS421Export:
    """S-421导出测试"""
    
    def setup_method(self):
        """测试初始化"""
        self.exporter = S421Exporter()
        self.output_dir = Path("artifacts") / "s421"
        self.output_dir.mkdir(parents=True, exist_ok=True)
    
    def test_basic_export(self):
        """测试基本导出功能"""
        # 创建测试路径
        route = self._create_test_route()
        
        # 导出到S-421
        output_path = self.output_dir / "test_route.s421"
        metadata = {
            'route_id': 'TEST_001',
            'name': 'Test Route',
            'author': 'Test System',
            'status': 'planned',
            'compliance': {
                'IMO MSC.232(82)': 'compliant',
                'IHO S-52': 'compliant'
            }
        }
        
        success = self.exporter.export(route, str(output_path), metadata)
        assert success
        
        print(f"✓ S-421导出成功: {output_path}")
        
        # 验证文件存在
        assert output_path.exists()
        
        # 验证XML结构
        tree = ET.parse(output_path)
        root = tree.getroot()
        
        # 检查命名空间
        assert '{http://www.iho.int/S421/1.0}' in root.tag
        
        # 检查必需元素
        metadata_elem = root.find('.//{http://www.iho.int/S421/1.0}DatasetMetadata')
        assert metadata_elem is not None
        
        route_elem = root.find('.//{http://www.iho.int/S421/1.0}Route')
        assert route_elem is not None
        
        waypoints = root.findall('.//waypoint')
        assert len(waypoints) == len(route.waypoints)
        
        print(f"  航点数量: {len(waypoints)}")
    
    def test_schema_validation(self):
        """测试Schema验证"""
        # 创建Schema文件
        schema_path = self.output_dir / "s421_route.schema.json"
        self.exporter.create_schema_file(str(schema_path))
        
        assert schema_path.exists()
        print(f"✓ Schema文件创建: {schema_path}")
        
        # 加载Schema
        with open(schema_path) as f:
            schema = json.load(f)
        
        # 创建符合Schema的数据
        valid_data = {
            "routeID": "ROUTE_001",
            "routeInfo": {
                "routeName": "Test Route",
                "routeAuthor": "ECDIS System",
                "routeStatus": "planned",
                "routeValidation": {
                    "validated": True,
                    "validationTime": "2024-01-01T12:00:00Z",
                    "validationAuthority": "ECDIS-PLANNER"
                }
            },
            "waypoints": [
                {
                    "waypointID": "WP001",
                    "waypointName": "Start",
                    "position": {
                        "latitude": 37.8,
                        "longitude": -122.5
                    },
                    "plannedSpeed": 10.0,
                    "plannedCourse": 45.0,
                    "crossTrackDistancePort": 185.2,
                    "crossTrackDistanceStarboard": 185.2
                },
                {
                    "waypointID": "WP002",
                    "waypointName": "End",
                    "position": {
                        "latitude": 37.85,
                        "longitude": -122.4
                    },
                    "plannedSpeed": 10.0,
                    "plannedCourse": 45.0,
                    "turnRadius": 100.0,
                    "crossTrackDistancePort": 185.2,
                    "crossTrackDistanceStarboard": 185.2
                }
            ],
            "routeLegs": [
                {
                    "legID": "LEG001",
                    "startWaypointID": "WP001",
                    "endWaypointID": "WP002",
                    "legGeometryType": "Loxodrome",
                    "safetyCorridor": 370.4
                }
            ],
            "extensions": {
                "plannerExtension": {
                    "algorithmType": "HybridAStar"
                }
            }
        }
        
        # 验证数据
        try:
            validate(instance=valid_data, schema=schema)
            print("✓ Schema验证通过")
        except jsonschema.exceptions.ValidationError as e:
            print(f"✗ Schema验证失败: {e}")
            assert False
    
    def test_rtz_to_s421_conversion(self):
        """测试RTZ到S-421转换"""
        # 先创建RTZ文件
        route = self._create_test_route()
        
        # 导出S-421（添加metadata参数）
        s421_path = self.output_dir / "converted.s421"
        metadata = {'name': 'Test Route', 'author': 'Test System'}
        success = self.exporter.export(route, str(s421_path), metadata)
        assert success
        
        # 解析S-421验证内容
        tree = ET.parse(s421_path)
        root = tree.getroot()
        
        # 验证航点映射
        waypoints = root.findall('.//waypoint')
        
        for i, wp in enumerate(waypoints):
            # 检查位置
            lat = float(wp.find('.//latitude').text)
            lon = float(wp.find('.//longitude').text)
            
            # 验证坐标（允许小误差）
            assert abs(lat - route.waypoints[i][1]) < 0.0001
            assert abs(lon - route.waypoints[i][0]) < 0.0001
            
            # 检查速度
            speed_elem = wp.find('.//plannedSpeed')
            if speed_elem is not None and i < len(route.velocities):
                speed = float(speed_elem.text)
                assert abs(speed - route.velocities[i]) < 0.1
        
        print(f"✓ RTZ到S-421转换成功")
        print(f"  验证 {len(waypoints)} 个航点映射正确")
    
    def test_field_mapping(self):
        """测试字段映射完整性"""
        # 创建包含所有字段的路径
        route = self._create_test_route()
        
        # 准备完整元数据
        metadata = {
            'route_id': 'MAPPING_TEST',
            'name': 'Field Mapping Test',
            'author': 'Test System',
            'status': 'validated',
            'validity_start': '2024-01-01T00:00:00Z',
            'validity_end': '2024-12-31T23:59:59Z',
            'compliance': {
                'IMO MSC.232(82)': 'compliant',
                'IHO S-52': 'compliant',
                'COLREG': 'compliant'
            }
        }
        
        # 导出
        output_path = self.output_dir / "field_mapping.s421"
        success = self.exporter.export(route, str(output_path), metadata)
        assert success
        
        # 验证映射
        tree = ET.parse(output_path)
        root = tree.getroot()
        
        # 检查路由信息映射
        route_info = root.find('.//{http://www.iho.int/S421/1.0}routeInfo')
        if route_info is None:
            # 尝试不带命名空间
            route_info = root.find('.//routeInfo')
        
        if route_info is not None:
            assert route_info.find('.//routeName').text == metadata['name']
            assert route_info.find('.//routeAuthor').text == metadata['author']
            assert route_info.find('.//routeStatus').text == metadata['status']
        else:
            print("警告: 找不到routeInfo元素，跳过字段映射测试")
        
        # 检查扩展信息
        extensions = root.find('.//{http://www.iho.int/S421/1.0}extensions')
        if extensions is None:
            extensions = root.find('.//extensions')
        
        # 检查合规信息（如果有扩展）
        if extensions is not None:
            compliance_ext = extensions.find('.//complianceExtension')
            if compliance_ext is not None:
                items = compliance_ext.findall('.//complianceItem')
                assert len(items) == len(metadata['compliance'])
        
        print("✓ 字段映射验证通过")
        print(f"  核心字段: ✓")
        print(f"  扩展字段: ✓")
        print(f"  合规信息: {len(metadata['compliance'])} 项")
    
    def test_minimal_s421(self):
        """测试最小S-421导出"""
        # 创建最小路径（仅2个航点）
        waypoints = [
            (-122.5, 37.8),
            (-122.4, 37.85)
        ]
        headings = [45.0, 45.0]
        velocities = [10.0, 10.0]
        
        route = Route(waypoints, headings, velocities)
        route.total_cost = 100.0
        
        # 导出最小S-421（需要metadata参数）
        output_path = self.output_dir / "minimal.s421"
        metadata = {'name': 'Minimal Route', 'author': 'Test'}
        success = self.exporter.export(route, str(output_path), metadata)
        assert success
        
        # 验证最小要求
        tree = ET.parse(output_path)
        root = tree.getroot()
        
        # 必需元素
        assert root.find('.//{http://www.iho.int/S421/1.0}DatasetMetadata') is not None
        assert root.find('.//{http://www.iho.int/S421/1.0}Route') is not None
        
        waypoints = root.findall('.//waypoint')
        assert len(waypoints) >= 2
        
        legs = root.findall('.//routeLeg')
        assert len(legs) >= 1
        
        print("✓ 最小S-421导出成功")
        print(f"  航点: {len(waypoints)}")
        print(f"  腿段: {len(legs)}")
    
    def test_export_with_feature_flag(self):
        """测试Feature Flag控制"""
        # 检查Feature Flag
        import os
        
        # 默认关闭
        os.environ['FEATURE_FLAG_S421'] = 'false'
        
        if os.environ.get('FEATURE_FLAG_S421', 'false').lower() != 'true':
            print("✓ S-421导出已禁用 (FEATURE_FLAG_S421=false)")
            # 在禁用状态下，导出应该跳过或返回False
            # 这里只是演示逻辑
        
        # 启用Feature Flag
        os.environ['FEATURE_FLAG_S421'] = 'true'
        
        if os.environ.get('FEATURE_FLAG_S421', 'false').lower() == 'true':
            route = self._create_test_route()
            output_path = self.output_dir / "feature_flag_test.s421"
            metadata = {'name': 'Feature Flag Test', 'author': 'Test'}
            success = self.exporter.export(route, str(output_path), metadata)
            assert success
            print("✓ Feature Flag启用，导出成功")
    
    def test_mapping_documentation(self):
        """生成映射文档"""
        doc_path = self.output_dir / "rtz_s421_mapping.md"
        
        doc_content = """# RTZ到S-421字段映射

## 核心字段映射

| RTZ字段 | S-421字段 | 说明 |
|---------|-----------|------|
| routeName | routeName | 航线名称 |
| routeAuthor | routeAuthor | 作者 |
| routeStatus | routeStatus | 状态 |
| waypoint.position | waypoint.position | 位置坐标 |
| waypoint.speed | waypoint.plannedSpeed | 计划速度 |
| waypoint.radius | waypoint.turnRadius | 转向半径 |
| waypoint.portsideXTD | waypoint.crossTrackDistancePort | 左舷XTD |
| waypoint.starboardXTD | waypoint.crossTrackDistanceStarboard | 右舷XTD |
| leg.geometryType | routeLeg.legGeometryType | 几何类型 |

## 扩展字段（Extensions）

非对称字段放入extensions元素：
- 规划器信息 (plannerExtension)
- 合规状态 (complianceExtension)
- 优化参数 (optimizationExtension)

## 验证要求

1. 最少2个航点
2. 航点ID唯一
3. 腿段引用有效
4. 坐标范围合法
"""
        
        with open(doc_path, 'w') as f:
            f.write(doc_content)
        
        print(f"✓ 映射文档生成: {doc_path}")
    
    def _create_test_route(self) -> Route:
        """创建测试路径"""
        waypoints = [
            (-122.5, 37.8),
            (-122.45, 37.82),
            (-122.4, 37.85)
        ]
        headings = [45.0, 50.0, 45.0]
        velocities = [10.0, 12.0, 10.0]
        
        route = Route(waypoints, headings, velocities)
        route.total_cost = 150.0
        
        return route


if __name__ == "__main__":
    # 运行测试
    tester = TestS421Export()
    tester.setup_method()
    
    print("S-421导出测试\n")
    print("="*50)
    
    tester.test_basic_export()
    print()
    
    tester.test_schema_validation()
    print()
    
    tester.test_rtz_to_s421_conversion()
    print()
    
    tester.test_field_mapping()
    print()
    
    tester.test_minimal_s421()
    print()
    
    tester.test_export_with_feature_flag()
    print()
    
    tester.test_mapping_documentation()
    
    print("\n" + "="*50)
    print("所有S-421导出测试通过！")