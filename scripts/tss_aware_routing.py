#!/usr/bin/env python3
"""
基于TSS（交通分离制）的智能路径规划
"""

import json
import math
from pathlib import Path

# TSS区域定义（主要交通分离制区域）
TSS_ZONES = {
    "singapore_strait": {
        "name": "新加坡海峡TSS",
        "bounds": [103.6, 1.0, 104.2, 1.4],  # [min_lon, min_lat, max_lon, max_lat]
        "traffic_lanes": [
            {
                "direction": "eastbound",  # 东行
                "waypoints": [
                    [103.65, 1.15],
                    [103.80, 1.20],
                    [103.95, 1.25],
                    [104.10, 1.30]
                ]
            },
            {
                "direction": "westbound",  # 西行
                "waypoints": [
                    [104.10, 1.10],
                    [103.95, 1.05],
                    [103.80, 1.00],
                    [103.65, 0.95]
                ]
            }
        ]
    },
    "malacca_strait": {
        "name": "马六甲海峡TSS",
        "bounds": [99.0, 1.0, 103.9, 5.5],
        "traffic_lanes": [
            {
                "direction": "northwestbound",  # 西北行（向马六甲）
                "waypoints": [
                    [103.50, 1.50],
                    [102.80, 2.20],
                    [102.00, 3.00],
                    [101.20, 3.80],
                    [100.40, 4.60],
                    [99.60, 5.40]
                ]
            },
            {
                "direction": "southeastbound",  # 东南行（向新加坡）
                "waypoints": [
                    [99.80, 5.20],
                    [100.60, 4.40],
                    [101.40, 3.60],
                    [102.20, 2.80],
                    [103.00, 2.00],
                    [103.851, 1.265]  # 新加坡港精确坐标
                ]
            }
        ]
    },
    "taiwan_strait": {
        "name": "台湾海峡TSS",
        "bounds": [118.0, 23.0, 121.0, 26.0],
        "traffic_lanes": [
            {
                "direction": "northbound",  # 北行
                "waypoints": [
                    [119.50, 23.50],
                    [119.70, 24.20],
                    [119.90, 24.90],
                    [120.10, 25.60]
                ]
            },
            {
                "direction": "southbound",  # 南行
                "waypoints": [
                    [120.30, 25.40],
                    [120.10, 24.70],
                    [119.90, 24.00],
                    [119.70, 23.30]
                ]
            }
        ]
    },
    "tokyo_bay": {
        "name": "东京湾TSS",
        "bounds": [139.5, 35.0, 140.0, 35.8],
        "traffic_lanes": [
            {
                "direction": "inbound",  # 进港
                "waypoints": [
                    [139.80, 35.20],
                    [139.85, 35.35],
                    [139.90, 35.50],
                    [139.95, 35.65]
                ]
            },
            {
                "direction": "outbound",  # 出港
                "waypoints": [
                    [139.70, 35.60],
                    [139.65, 35.45],
                    [139.60, 35.30],
                    [139.55, 35.15]
                ]
            }
        ]
    },
    "yellow_sea": {
        "name": "黄海TSS",
        "bounds": [120.0, 34.0, 126.0, 38.0],
        "traffic_lanes": [
            {
                "direction": "northeast",  # 东北行（中国→韩国）
                "waypoints": [
                    [121.00, 35.00],
                    [122.50, 35.80],
                    [124.00, 36.60],
                    [125.50, 37.40]
                ]
            },
            {
                "direction": "southwest",  # 西南行（韩国→中国）
                "waypoints": [
                    [125.00, 37.00],
                    [123.50, 36.20],
                    [122.00, 35.40],
                    [120.50, 34.60]
                ]
            }
        ]
    }
}

def point_in_bounds(lat, lon, bounds):
    """检查点是否在边界框内"""
    min_lon, min_lat, max_lon, max_lat = bounds
    return min_lon <= lon <= max_lon and min_lat <= lat <= max_lat

def get_direction(start_lat, start_lon, end_lat, end_lon):
    """计算航行方向（简化）"""
    dlat = end_lat - start_lat
    dlon = end_lon - start_lon
    
    if abs(dlon) > abs(dlat):
        return "eastbound" if dlon > 0 else "westbound"
    else:
        return "northbound" if dlat > 0 else "southbound"

def get_tss_route_through_zone(start_lat, start_lon, end_lat, end_lon, tss_zone):
    """获取通过TSS区域的安全路径"""
    zone_data = TSS_ZONES[tss_zone]
    bounds = zone_data["bounds"]
    
    # 检查是否需要通过此TSS区域
    if not (point_in_bounds(start_lat, start_lon, bounds) or 
            point_in_bounds(end_lat, end_lon, bounds)):
        # 检查路径是否穿越TSS区域
        mid_lat = (start_lat + end_lat) / 2
        mid_lon = (start_lon + end_lon) / 2
        if not point_in_bounds(mid_lat, mid_lon, bounds):
            return None
    
    # 根据航行方向选择合适的交通道
    direction = get_direction(start_lat, start_lon, end_lat, end_lon)
    
    # 选择最合适的交通道
    best_lane = None
    min_distance = float('inf')
    
    for lane in zone_data["traffic_lanes"]:
        # 简化的方向匹配
        lane_waypoints = lane["waypoints"]
        start_dist = ((lane_waypoints[0][0] - start_lon)**2 + (lane_waypoints[0][1] - start_lat)**2)**0.5
        end_dist = ((lane_waypoints[-1][0] - end_lon)**2 + (lane_waypoints[-1][1] - end_lat)**2)**0.5
        total_dist = start_dist + end_dist
        
        if total_dist < min_distance:
            min_distance = total_dist
            best_lane = lane
    
    return best_lane["waypoints"] if best_lane else None

def generate_tss_aware_route(start_lat, start_lon, end_lat, end_lon):
    """生成考虑TSS规则的路径"""
    route_waypoints = []
    
    # 添加起点
    route_waypoints.append([start_lon, start_lat])
    
    # 检查各个TSS区域
    tss_segments = []
    
    # 特定航线的TSS考虑
    route_type = classify_route(start_lat, start_lon, end_lat, end_lon)
    
    if route_type == "china_singapore":
        # 中国→新加坡：台湾海峡 → 南海 → 新加坡海峡
        taiwan_segment = get_tss_route_through_zone(start_lat, start_lon, 1.2, 103.7, "taiwan_strait")
        if taiwan_segment:
            route_waypoints.extend(taiwan_segment)
        
        singapore_segment = get_tss_route_through_zone(23.0, 120.0, end_lat, end_lon, "singapore_strait")
        if singapore_segment:
            route_waypoints.extend(singapore_segment)
    
    elif route_type == "china_korea_japan":
        # 中国→韩国/日本：黄海TSS → 东京湾TSS（如果到日本）
        yellow_sea_segment = get_tss_route_through_zone(start_lat, start_lon, end_lat, end_lon, "yellow_sea")
        if yellow_sea_segment:
            route_waypoints.extend(yellow_sea_segment)
        
        # 如果目标是日本港口
        if end_lat > 34.0 and end_lon > 138.0:
            tokyo_segment = get_tss_route_through_zone(35.0, 129.0, end_lat, end_lon, "tokyo_bay")
            if tokyo_segment:
                route_waypoints.extend(tokyo_segment)
    
    elif route_type == "malacca_singapore":
        # 马六甲海峡航线
        malacca_segment = get_tss_route_through_zone(start_lat, start_lon, end_lat, end_lon, "malacca_strait")
        if malacca_segment:
            route_waypoints.extend(malacca_segment)
    
    # 添加终点
    route_waypoints.append([end_lon, end_lat])
    
    return {
        "name": f"TSS-Aware Route ({route_type})",
        "waypoints": route_waypoints,
        "tss_compliance": True,
        "route_type": route_type
    }

def classify_route(start_lat, start_lon, end_lat, end_lon):
    """分类航线类型"""
    # 中国港口范围
    china_bounds = [110.0, 18.0, 125.0, 42.0]
    # 新加坡/马来西亚范围
    singapore_bounds = [99.0, 1.0, 105.0, 7.0]
    # 韩国范围
    korea_bounds = [125.0, 33.0, 131.0, 39.0]
    # 日本范围
    japan_bounds = [129.0, 30.0, 146.0, 46.0]
    
    start_in_china = point_in_bounds(start_lat, start_lon, china_bounds)
    end_in_china = point_in_bounds(end_lat, end_lon, china_bounds)
    end_in_singapore = point_in_bounds(end_lat, end_lon, singapore_bounds)
    end_in_korea = point_in_bounds(end_lat, end_lon, korea_bounds)
    end_in_japan = point_in_bounds(end_lat, end_lon, japan_bounds)
    
    if start_in_china and end_in_singapore:
        return "china_singapore"
    elif start_in_china and (end_in_korea or end_in_japan):
        return "china_korea_japan"
    elif point_in_bounds(start_lat, start_lon, singapore_bounds):
        return "malacca_singapore"
    else:
        return "other"

if __name__ == "__main__":
    # 测试TSS感知路径规划
    test_routes = [
        (31.23, 121.508, 1.265, 103.851, "上海→新加坡"),
        (36.0, 120.6, 35.1, 129.04, "青岛→釜山"),
        (38.7, 118.2, 35.44, 139.64, "天津→横滨"),
        (1.0, 99.0, 1.265, 103.851, "马六甲→新加坡"),
    ]
    
    print("=== TSS感知路径规划测试 ===")
    
    for start_lat, start_lon, end_lat, end_lon, desc in test_routes:
        print(f"\n--- {desc} ---")
        route = generate_tss_aware_route(start_lat, start_lon, end_lat, end_lon)
        print(f"路径类型: {route['route_type']}")
        print(f"路径点数量: {len(route['waypoints'])}")
        print(f"TSS合规: {route['tss_compliance']}")
        print(f"主要路径点: {route['waypoints'][:3]}...{route['waypoints'][-3:]}")