"""
S-421路由交换格式导出器
实现RTZ到S-421的单向导出（IEC 63173-1标准）
"""

import json
import xml.etree.ElementTree as ET
from typing import Dict, List, Optional, Any
from datetime import datetime
from pathlib import Path
import logging

from lib.planner.hybrid_astar import Route

logger = logging.getLogger(__name__)

# S-421命名空间
S421_NAMESPACES = {
    's421': 'http://www.iho.int/S421/1.0',
    'gml': 'http://www.opengis.net/gml/3.2',
    'xlink': 'http://www.w3.org/1999/xlink',
    'xsi': 'http://www.w3.org/2001/XMLSchema-instance'
}

# RTZ到S-421字段映射
RTZ_TO_S421_MAPPING = {
    # 航线属性
    'routeName': 'routeName',
    'routeAuthor': 'routeAuthor',
    'routeStatus': 'routeStatus',
    'validityPeriodStart': 'validFrom',
    'validityPeriodStop': 'validTo',
    
    # 航点属性
    'waypoint_id': 'waypointID',
    'waypoint_name': 'waypointName',
    'position_lat': 'latitude',
    'position_lon': 'longitude',
    'plannedSpeed': 'plannedSpeed',
    'speedMin': 'minimumSpeed',
    'speedMax': 'maximumSpeed',
    'turnRadius': 'turnRadius',
    'portsideXTD': 'crossTrackDistancePort',
    'starboardXTD': 'crossTrackDistanceStarboard',
    
    # 腿段属性
    'geometryType': 'legGeometryType',
    'starttimeEta': 'estimatedTimeOfArrival'
}


class S421Exporter:
    """S-421导出器"""
    
    def __init__(self):
        """初始化导出器"""
        self.schema_version = "1.0.0"
        self.producer = "ECDIS-PLANNER"
        
    def export(self, route: Route, output_path: str, metadata: Optional[Dict] = None) -> bool:
        """
        导出路径到S-421格式
        
        Args:
            route: 路径对象
            output_path: 输出文件路径
            metadata: 额外元数据
            
        Returns:
            是否成功导出
        """
        try:
            logger.info(f"导出S-421到: {output_path}")
            
            # 创建S-421根元素
            root = self._create_root_element()
            
            # 添加路由信息
            route_elem = self._create_route_element(route, metadata)
            root.append(route_elem)
            
            # 创建XML树
            tree = ET.ElementTree(root)
            
            # 格式化并保存
            self._indent_xml(root)
            tree.write(output_path, encoding='utf-8', xml_declaration=True)
            
            # 验证导出的文件
            if self._validate_s421(output_path):
                logger.info("S-421导出成功并通过验证")
                return True
            else:
                logger.warning("S-421导出完成但验证失败")
                return False
                
        except Exception as e:
            logger.error(f"S-421导出失败: {e}")
            return False
    
    def _create_root_element(self) -> ET.Element:
        """创建S-421根元素"""
        root = ET.Element(
            '{http://www.iho.int/S421/1.0}Dataset',
            attrib={
                '{http://www.w3.org/2001/XMLSchema-instance}schemaLocation': 
                'http://www.iho.int/S421/1.0 S421.xsd'
            }
        )
        
        # 注册命名空间
        for prefix, uri in S421_NAMESPACES.items():
            ET.register_namespace(prefix, uri)
        
        # 添加数据集元数据
        metadata = ET.SubElement(root, '{http://www.iho.int/S421/1.0}DatasetMetadata')
        ET.SubElement(metadata, 'datasetID').text = f"S421_{datetime.now().strftime('%Y%m%d%H%M%S')}"
        ET.SubElement(metadata, 'datasetName').text = "ECDIS Route Plan"
        ET.SubElement(metadata, 'datasetProducer').text = self.producer
        ET.SubElement(metadata, 'datasetProductionDate').text = datetime.now().isoformat()
        ET.SubElement(metadata, 'schemaVersion').text = self.schema_version
        
        return root
    
    def _create_route_element(self, route: Route, metadata: Optional[Dict]) -> ET.Element:
        """创建路由元素"""
        route_elem = ET.Element('{http://www.iho.int/S421/1.0}Route')
        
        # 路由标识
        route_id = metadata.get('route_id', f"route_{datetime.now().strftime('%Y%m%d%H%M%S')}")
        ET.SubElement(route_elem, 'routeID').text = route_id
        
        # 路由信息
        route_info = ET.SubElement(route_elem, 'routeInfo')
        ET.SubElement(route_info, 'routeName').text = metadata.get('name', 'Planned Route')
        ET.SubElement(route_info, 'routeAuthor').text = metadata.get('author', self.producer)
        ET.SubElement(route_info, 'routeStatus').text = metadata.get('status', 'planned')
        
        # 验证信息
        validation = ET.SubElement(route_info, 'routeValidation')
        ET.SubElement(validation, 'validated').text = 'true'
        ET.SubElement(validation, 'validationTime').text = datetime.now().isoformat()
        ET.SubElement(validation, 'validationAuthority').text = 'ECDIS-PLANNER'
        
        # 航点列表
        waypoints_elem = ET.SubElement(route_elem, '{http://www.iho.int/S421/1.0}waypoints')
        
        for i, (x, y) in enumerate(route.waypoints):
            wp_elem = self._create_waypoint_element(
                index=i,
                lon=x,
                lat=y,
                heading=route.headings[i] if i < len(route.headings) else 0,
                speed=route.velocities[i] if i < len(route.velocities) else 10.0
            )
            waypoints_elem.append(wp_elem)
        
        # 腿段列表
        legs_elem = ET.SubElement(route_elem, '{http://www.iho.int/S421/1.0}routeLegs')
        
        for i in range(len(route.waypoints) - 1):
            leg_elem = self._create_leg_element(
                index=i,
                from_wp=i,
                to_wp=i+1,
                geometry_type='Loxodrome'  # 默认恒向线
            )
            legs_elem.append(leg_elem)
        
        # 扩展信息（非对称字段）
        extensions = ET.SubElement(route_elem, 'extensions')
        self._add_extensions(extensions, route, metadata)
        
        return route_elem
    
    def _create_waypoint_element(self, index: int, lon: float, lat: float, 
                                 heading: float, speed: float) -> ET.Element:
        """创建航点元素"""
        wp_elem = ET.Element('waypoint')
        
        # 航点ID
        ET.SubElement(wp_elem, 'waypointID').text = f"WP{index+1:03d}"
        ET.SubElement(wp_elem, 'waypointName').text = f"Waypoint {index+1}"
        
        # 位置
        position = ET.SubElement(wp_elem, 'position')
        ET.SubElement(position, 'latitude').text = f"{lat:.6f}"
        ET.SubElement(position, 'longitude').text = f"{lon:.6f}"
        
        # 计划速度
        ET.SubElement(wp_elem, 'plannedSpeed').text = f"{speed:.1f}"
        ET.SubElement(wp_elem, 'speedUnit').text = "m/s"
        
        # 航向
        ET.SubElement(wp_elem, 'plannedCourse').text = f"{heading:.1f}"
        
        # 转向半径（如果需要）
        if index > 0:
            ET.SubElement(wp_elem, 'turnRadius').text = "100.0"  # 默认100米
        
        # XTD限制
        ET.SubElement(wp_elem, 'crossTrackDistancePort').text = "185.2"  # 0.1 NM
        ET.SubElement(wp_elem, 'crossTrackDistanceStarboard').text = "185.2"
        
        return wp_elem
    
    def _create_leg_element(self, index: int, from_wp: int, to_wp: int, 
                           geometry_type: str) -> ET.Element:
        """创建腿段元素"""
        leg_elem = ET.Element('routeLeg')
        
        # 腿段ID
        ET.SubElement(leg_elem, 'legID').text = f"LEG{index+1:03d}"
        
        # 起止航点
        ET.SubElement(leg_elem, 'startWaypointID').text = f"WP{from_wp+1:03d}"
        ET.SubElement(leg_elem, 'endWaypointID').text = f"WP{to_wp+1:03d}"
        
        # 几何类型
        ET.SubElement(leg_elem, 'legGeometryType').text = geometry_type
        
        # 安全走廊
        ET.SubElement(leg_elem, 'safetyCorridor').text = "370.4"  # 0.2 NM
        
        return leg_elem
    
    def _add_extensions(self, extensions_elem: ET.Element, route: Route, 
                       metadata: Optional[Dict]):
        """添加扩展信息（非对称字段）"""
        # ECDIS规划器特定信息
        planner_ext = ET.SubElement(extensions_elem, 'plannerExtension')
        ET.SubElement(planner_ext, 'plannerVersion').text = "1.0.0"
        ET.SubElement(planner_ext, 'algorithmType').text = "HybridAStar"
        ET.SubElement(planner_ext, 'totalCost').text = f"{route.total_cost:.2f}"
        
        # 合规信息
        if metadata and 'compliance' in metadata:
            compliance_ext = ET.SubElement(extensions_elem, 'complianceExtension')
            for standard, status in metadata['compliance'].items():
                item = ET.SubElement(compliance_ext, 'complianceItem')
                ET.SubElement(item, 'standard').text = standard
                ET.SubElement(item, 'status').text = status
        
        # 优化参数
        optimization_ext = ET.SubElement(extensions_elem, 'optimizationExtension')
        ET.SubElement(optimization_ext, 'optimizationCriteria').text = "MinimumDistance"
        ET.SubElement(optimization_ext, 'safetyMargin').text = "1.5"
    
    def _indent_xml(self, elem: ET.Element, level: int = 0):
        """格式化XML缩进"""
        indent = "\n" + "  " * level
        if len(elem):
            if not elem.text or not elem.text.strip():
                elem.text = indent + "  "
            if not elem.tail or not elem.tail.strip():
                elem.tail = indent
            for child in elem:
                self._indent_xml(child, level + 1)
            if not child.tail or not child.tail.strip():
                child.tail = indent
        else:
            if level and (not elem.tail or not elem.tail.strip()):
                elem.tail = indent
    
    def _validate_s421(self, file_path: str) -> bool:
        """
        验证S-421文件
        
        Args:
            file_path: S-421文件路径
            
        Returns:
            是否有效
        """
        try:
            # 基础XML验证
            tree = ET.parse(file_path)
            root = tree.getroot()
            
            # 检查必需元素
            required_elements = [
                './/{http://www.iho.int/S421/1.0}DatasetMetadata',
                './/{http://www.iho.int/S421/1.0}Route',
                './/{http://www.iho.int/S421/1.0}waypoints',
                './/{http://www.iho.int/S421/1.0}routeLegs'
            ]
            
            for xpath in required_elements:
                if root.find(xpath) is None:
                    logger.error(f"缺少必需元素: {xpath}")
                    return False
            
            # 检查航点数量（waypoint元素可能没有命名空间）
            waypoints = root.findall('.//waypoint')
            if len(waypoints) < 2:
                # 尝试带命名空间查找
                waypoints = root.findall('.//{http://www.iho.int/S421/1.0}waypoint')
                if len(waypoints) < 2:
                    logger.error(f"航点数量少于2个: {len(waypoints)}")
                    return False
            
            logger.info(f"S-421验证通过: {len(waypoints)} 个航点")
            return True
            
        except Exception as e:
            logger.error(f"S-421验证失败: {e}")
            return False
    
    def create_schema_file(self, output_path: str):
        """
        创建S-421 JSON Schema文件
        
        Args:
            output_path: Schema文件路径
        """
        schema = {
            "$schema": "http://json-schema.org/draft-07/schema#",
            "$id": "https://ecdis-planner.io/schemas/s421_route.v1.json",
            "title": "S421Route",
            "description": "S-421 Route Exchange Format (IEC 63173-1)",
            "type": "object",
            "required": ["routeID", "routeInfo", "waypoints", "routeLegs"],
            "properties": {
                "routeID": {
                    "type": "string",
                    "pattern": "^[A-Za-z0-9_-]+$"
                },
                "routeInfo": {
                    "type": "object",
                    "required": ["routeName", "routeAuthor", "routeStatus"],
                    "properties": {
                        "routeName": {"type": "string"},
                        "routeAuthor": {"type": "string"},
                        "routeStatus": {
                            "type": "string",
                            "enum": ["planned", "validated", "active", "completed"]
                        },
                        "routeValidation": {
                            "type": "object",
                            "properties": {
                                "validated": {"type": "boolean"},
                                "validationTime": {
                                    "type": "string",
                                    "format": "date-time"
                                },
                                "validationAuthority": {"type": "string"}
                            }
                        }
                    }
                },
                "waypoints": {
                    "type": "array",
                    "minItems": 2,
                    "items": {
                        "type": "object",
                        "required": ["waypointID", "position"],
                        "properties": {
                            "waypointID": {"type": "string"},
                            "waypointName": {"type": "string"},
                            "position": {
                                "type": "object",
                                "required": ["latitude", "longitude"],
                                "properties": {
                                    "latitude": {
                                        "type": "number",
                                        "minimum": -90,
                                        "maximum": 90
                                    },
                                    "longitude": {
                                        "type": "number",
                                        "minimum": -180,
                                        "maximum": 180
                                    }
                                }
                            },
                            "plannedSpeed": {"type": "number", "minimum": 0},
                            "plannedCourse": {
                                "type": "number",
                                "minimum": 0,
                                "maximum": 360
                            },
                            "turnRadius": {"type": "number", "minimum": 0},
                            "crossTrackDistancePort": {"type": "number", "minimum": 0},
                            "crossTrackDistanceStarboard": {"type": "number", "minimum": 0}
                        }
                    }
                },
                "routeLegs": {
                    "type": "array",
                    "minItems": 1,
                    "items": {
                        "type": "object",
                        "required": ["legID", "startWaypointID", "endWaypointID"],
                        "properties": {
                            "legID": {"type": "string"},
                            "startWaypointID": {"type": "string"},
                            "endWaypointID": {"type": "string"},
                            "legGeometryType": {
                                "type": "string",
                                "enum": ["Loxodrome", "Orthodrome", "Other"]
                            },
                            "safetyCorridor": {"type": "number", "minimum": 0}
                        }
                    }
                },
                "extensions": {
                    "type": "object",
                    "description": "扩展字段用于非对称信息"
                }
            }
        }
        
        with open(output_path, 'w') as f:
            json.dump(schema, f, indent=2)
        
        logger.info(f"创建S-421 Schema: {output_path}")