#!/usr/bin/env python3
"""
港口路径规划服务 Port Route Planning Service
支持全球主要港口之间的路径规划
"""

import json
import math
from typing import Dict, List, Tuple, Optional
from datetime import datetime
from pathlib import Path
import sys

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from service.route_planner_service import RoutePlannerService


class PortRoutePlanner:
    """港口路径规划器"""
    
    def __init__(self):
        """初始化港口规划器"""
        self.route_service = RoutePlannerService()
        self.ports_data = self._load_ports_data()
        
    def _load_ports_data(self) -> Dict:
        """加载港口数据"""
        ports_file = Path("data/ports/world_ports.json")
        if ports_file.exists():
            with open(ports_file, 'r', encoding='utf-8') as f:
                return json.load(f)
        return {"ports": {}, "regions": {}}
    
    def list_ports_by_region(self, region: Optional[str] = None) -> List[Dict]:
        """按区域列出港口"""
        ports_list = []
        
        if region and region in self.ports_data["regions"]:
            # 列出特定区域的港口
            port_codes = self.ports_data["regions"][region]
            for country_ports in self.ports_data["ports"].values():
                for port_data in country_ports.values():
                    if port_data["code"] in port_codes:
                        ports_list.append(port_data)
        else:
            # 列出所有港口
            for country, country_ports in self.ports_data["ports"].items():
                for city, port_data in country_ports.items():
                    port_data["country"] = country
                    port_data["city"] = city
                    ports_list.append(port_data)
        
        return sorted(ports_list, key=lambda x: x["name"])
    
    def get_port_by_code(self, port_code: str) -> Optional[Dict]:
        """根据港口代码获取港口信息"""
        for country_ports in self.ports_data["ports"].values():
            for port_data in country_ports.values():
                if port_data["code"] == port_code:
                    return port_data
        return None
    
    def search_ports(self, keyword: str) -> List[Dict]:
        """搜索港口"""
        keyword_lower = keyword.lower()
        results = []
        
        for country, country_ports in self.ports_data["ports"].items():
            for city, port_data in country_ports.items():
                # 搜索港口名称、城市、国家或代码
                if (keyword_lower in port_data["name"].lower() or
                    keyword_lower in city.lower() or
                    keyword_lower in country.lower() or
                    keyword_lower in port_data["code"].lower()):
                    
                    port_info = port_data.copy()
                    port_info["country"] = country
                    port_info["city"] = city
                    results.append(port_info)
        
        return results
    
    def plan_port_route(self, 
                       origin_code: str, 
                       dest_code: str,
                       **options) -> Dict:
        """
        规划港口间路径
        
        Args:
            origin_code: 起始港口代码
            dest_code: 目的港口代码
            options: 可选参数
        
        Returns:
            规划结果
        """
        # 获取港口信息
        origin_port = self.get_port_by_code(origin_code)
        dest_port = self.get_port_by_code(dest_code)
        
        if not origin_port:
            return {
                "status": "error",
                "message": f"起始港口 {origin_code} 未找到"
            }
        
        if not dest_port:
            return {
                "status": "error",
                "message": f"目的港口 {dest_code} 未找到"
            }
        
        print(f"\n🚢 规划港口航线:")
        print(f"  起点: {origin_port['name']} ({origin_code})")
        print(f"  终点: {dest_port['name']} ({dest_code})")
        
        # 使用基础路径规划服务
        result = self.route_service.plan_route(
            origin_port["lat"], origin_port["lon"],
            dest_port["lat"], dest_port["lon"],
            **options
        )
        
        # 添加港口信息
        if result["status"] == "success":
            result["ports"] = {
                "origin": origin_port,
                "destination": dest_port
            }
            
            # 计算大圆距离用于参考
            gc_distance = self._calculate_great_circle_distance(
                origin_port["lat"], origin_port["lon"],
                dest_port["lat"], dest_port["lon"]
            )
            result["route"]["great_circle_nm"] = round(gc_distance, 1)
        
        return result
    
    def _calculate_great_circle_distance(self, lat1: float, lon1: float, 
                                        lat2: float, lon2: float) -> float:
        """计算大圆距离（海里）"""
        # 转换为弧度
        lat1_rad = math.radians(lat1)
        lon1_rad = math.radians(lon1)
        lat2_rad = math.radians(lat2)
        lon2_rad = math.radians(lon2)
        
        # Haversine公式
        dlat = lat2_rad - lat1_rad
        dlon = lon2_rad - lon1_rad
        
        a = (math.sin(dlat/2)**2 + 
             math.cos(lat1_rad) * math.cos(lat2_rad) * 
             math.sin(dlon/2)**2)
        c = 2 * math.asin(math.sqrt(a))
        
        # 地球半径（海里）
        R = 3440.065
        return R * c
    
    def suggest_routes(self, origin_code: str) -> List[Dict]:
        """推荐常用航线"""
        suggestions = []
        
        # 定义常用航线
        popular_routes = [
            ("USSFO", "USOAK", "旧金山湾区内部"),
            ("USSFO", "USLAX", "美西海岸南北"),
            ("USLAX", "CNSHA", "跨太平洋主航线"),
            ("CNSHA", "SGSIN", "亚洲区域航线"),
            ("SGSIN", "AEJEA", "亚洲-中东航线"),
            ("NLRTM", "DEHAM", "北欧区域航线"),
            ("USNYC", "GBLON", "跨大西洋航线"),
            ("CNSHA", "NLRTM", "亚欧航线"),
            ("BRSSZ", "CNSHA", "南美-亚洲航线"),
            ("AUSYD", "SGSIN", "澳洲-亚洲航线")
        ]
        
        for route_origin, route_dest, description in popular_routes:
            if route_origin == origin_code:
                dest_port = self.get_port_by_code(route_dest)
                if dest_port:
                    distance = self._calculate_great_circle_distance(
                        self.get_port_by_code(route_origin)["lat"],
                        self.get_port_by_code(route_origin)["lon"],
                        dest_port["lat"],
                        dest_port["lon"]
                    )
                    
                    suggestions.append({
                        "origin_code": route_origin,
                        "dest_code": route_dest,
                        "dest_name": dest_port["name"],
                        "description": description,
                        "distance_nm": round(distance, 1)
                    })
        
        # 如果没有预定义的，推荐同区域的其他港口
        if not suggestions:
            origin_port = self.get_port_by_code(origin_code)
            if origin_port:
                # 找到起始港口所在区域
                for region, codes in self.ports_data["regions"].items():
                    if origin_code in codes:
                        # 推荐同区域的其他港口
                        for code in codes[:5]:  # 最多推荐5个
                            if code != origin_code:
                                port = self.get_port_by_code(code)
                                if port:
                                    distance = self._calculate_great_circle_distance(
                                        origin_port["lat"], origin_port["lon"],
                                        port["lat"], port["lon"]
                                    )
                                    
                                    suggestions.append({
                                        "origin_code": origin_code,
                                        "dest_code": code,
                                        "dest_name": port["name"],
                                        "description": f"{region}区域航线",
                                        "distance_nm": round(distance, 1)
                                    })
                        break
        
        return sorted(suggestions, key=lambda x: x["distance_nm"])


def interactive_port_planner():
    """交互式港口路径规划"""
    print("\n" + "="*60)
    print("   🚢 港口路径规划系统")
    print("   Port Route Planning System")
    print("="*60)
    
    planner = PortRoutePlanner()
    
    # 显示区域选择
    print("\n📍 选择区域 Select Region:")
    print("-" * 40)
    regions = list(planner.ports_data["regions"].keys())
    for i, region in enumerate(regions, 1):
        port_count = len(planner.ports_data["regions"][region])
        print(f"{i:2}. {region} ({port_count}个港口)")
    print(f"{len(regions)+1:2}. 搜索港口")
    print(f"{len(regions)+2:2}. 显示所有港口")
    
    choice = input(f"\n选择 (1-{len(regions)+2}): ")
    
    # 处理选择
    ports_list = []
    if choice.isdigit():
        choice_num = int(choice)
        if 1 <= choice_num <= len(regions):
            selected_region = regions[choice_num - 1]
            ports_list = planner.list_ports_by_region(selected_region)
            print(f"\n{selected_region} 港口列表:")
        elif choice_num == len(regions) + 1:
            keyword = input("输入搜索关键词: ")
            ports_list = planner.search_ports(keyword)
            print(f"\n搜索结果 '{keyword}':")
        else:
            ports_list = planner.list_ports_by_region()
            print("\n所有港口:")
    
    if not ports_list:
        print("未找到港口")
        return
    
    # 显示港口列表
    print("-" * 40)
    for i, port in enumerate(ports_list[:20], 1):  # 最多显示20个
        print(f"{i:2}. [{port['code']}] {port['name']}")
    
    if len(ports_list) > 20:
        print(f"... 还有 {len(ports_list)-20} 个港口")
    
    # 选择起始港口
    print("\n" + "="*40)
    origin_idx = input("选择起始港口 (序号): ")
    if not origin_idx.isdigit() or int(origin_idx) < 1 or int(origin_idx) > len(ports_list):
        print("无效选择")
        return
    
    origin_port = ports_list[int(origin_idx) - 1]
    print(f"✅ 起点: {origin_port['name']} ({origin_port['code']})")
    
    # 显示推荐航线
    suggestions = planner.suggest_routes(origin_port['code'])
    if suggestions:
        print("\n💡 推荐航线:")
        for i, route in enumerate(suggestions[:5], 1):
            print(f"  {i}. {route['dest_name']} - {route['description']} ({route['distance_nm']} nm)")
        
        use_suggestion = input("\n使用推荐航线? (1-5/n): ")
        if use_suggestion.isdigit() and 1 <= int(use_suggestion) <= len(suggestions):
            dest_code = suggestions[int(use_suggestion) - 1]["dest_code"]
            dest_port = planner.get_port_by_code(dest_code)
        else:
            # 选择目的港口
            dest_idx = input("选择目的港口 (序号): ")
            if not dest_idx.isdigit() or int(dest_idx) < 1 or int(dest_idx) > len(ports_list):
                print("无效选择")
                return
            dest_port = ports_list[int(dest_idx) - 1]
    else:
        # 选择目的港口
        dest_idx = input("选择目的港口 (序号): ")
        if not dest_idx.isdigit() or int(dest_idx) < 1 or int(dest_idx) > len(ports_list):
            print("无效选择")
            return
        dest_port = ports_list[int(dest_idx) - 1]
    
    print(f"✅ 终点: {dest_port['name']} ({dest_port['code']})")
    
    # 执行规划
    print("\n" + "="*40)
    print("开始规划...")
    print("="*40)
    
    result = planner.plan_port_route(origin_port['code'], dest_port['code'])
    
    if result["status"] == "success":
        # 显示结果
        print("\n📊 规划结果:")
        print("-" * 40)
        print(f"✅ 状态: 成功")
        print(f"🚢 航线: {origin_port['name']} → {dest_port['name']}")
        print(f"📍 航点数: {result['route']['total_waypoints']}")
        print(f"📏 规划距离: {result['route']['distance_nm']} 海里")
        print(f"📐 大圆距离: {result['route']['great_circle_nm']} 海里")
        print(f"⏱️  预计时间: {result['route']['eta_hours']} 小时")
        print(f"⚡ 船速: {result['vessel']['speed_kts']} 节")
        
        print("\n🔍 验证结果:")
        print(f"  TSS合规: {'✅ 通过' if result['validation']['tss_compliant'] else '❌ 未通过'}")
        print(f"  规则验证: {result['validation']['rules_passed']}/16 通过")
        
        # 导出选项
        print("\n" + "="*40)
        export = input("是否导出路径? (y/n): ")
        if export.lower() == 'y':
            filename = f"route_{origin_port['code']}_{dest_port['code']}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
            with open(filename, 'w', encoding='utf-8') as f:
                json.dump(result, f, indent=2, ensure_ascii=False)
            print(f"✅ 已导出到: {filename}")
    else:
        print(f"\n❌ 规划失败: {result.get('message', '未知错误')}")
    
    print("\n✅ 规划完成!")


if __name__ == "__main__":
    # 直接运行时启动交互式规划
    interactive_port_planner()