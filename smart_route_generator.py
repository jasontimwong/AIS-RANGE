#!/usr/bin/env python3
"""
智能路径生成器 - 考虑陆地避障的路径规划
"""
import json
import math
import sys
import os
sys.path.append('/Users/jasonwong/planner')

def point_in_polygon(lat, lon, polygon_coords):
    """检查点是否在多边形内（射线法）"""
    x, y = lon, lat
    n = len(polygon_coords)
    inside = False

    p1x, p1y = polygon_coords[0]
    for i in range(1, n + 1):
        p2x, p2y = polygon_coords[i % n]
        if y > min(p1y, p2y):
            if y <= max(p1y, p2y):
                if x <= max(p1x, p2x):
                    if p1y != p2y:
                        xinters = (y - p1y) * (p2x - p1x) / (p2y - p1y) + p1x
                    if p1x == p2x or x <= xinters:
                        inside = not inside
        p1x, p1y = p2x, p2y

    return inside

def is_coordinate_on_land(lat, lon, land_data):
    """检查坐标是否在陆地上"""
    for feature in land_data['features']:
        geometry = feature['geometry']
        
        if geometry['type'] == 'Polygon':
            if point_in_polygon(lat, lon, geometry['coordinates'][0]):
                return True
        elif geometry['type'] == 'MultiPolygon':
            for polygon in geometry['coordinates']:
                if point_in_polygon(lat, lon, polygon[0]):
                    return True
    return False

def generate_safe_route(start_lat, start_lon, end_lat, end_lon, land_data, num_points=30):
    """生成避开陆地的安全路径"""
    # 首先尝试直线路径
    waypoints = []
    
    for i in range(num_points):
        t = i / (num_points - 1)
        
        # 线性插值
        lat = start_lat + t * (end_lat - start_lat)
        lon = start_lon + t * (end_lon - start_lon)
        
        # 检查是否在陆地上
        if is_coordinate_on_land(lat, lon, land_data):
            # 如果在陆地上，尝试调整到海上
            # 方法1：向南偏移（通常海洋在南边）
            adjusted = False
            for offset in [0.5, 1.0, 1.5, 2.0, -0.5, -1.0, -1.5, -2.0]:
                new_lat = lat + offset
                if not is_coordinate_on_land(new_lat, lon, land_data):
                    waypoints.append([lon, new_lat])
                    adjusted = True
                    break
            
            # 方法2：向东/西偏移
            if not adjusted:
                for offset in [0.5, 1.0, 1.5, 2.0, -0.5, -1.0, -1.5, -2.0]:
                    new_lon = lon + offset
                    if not is_coordinate_on_land(lat, new_lon, land_data):
                        waypoints.append([new_lon, lat])
                        adjusted = True
                        break
            
            # 方法3：如果仍然调整不了，跳过这个点
            if not adjusted:
                continue
        else:
            waypoints.append([lon, lat])
    
    return {
        "name": "Smart Safe Route",
        "waypoints": waypoints
    }

def load_land_data():
    """加载陆地数据"""
    try:
        with open('/Users/jasonwong/planner/data/asia_pacific_land.json', 'r') as f:
            return json.load(f)
    except FileNotFoundError:
        print("警告: 未找到陆地数据文件")
        return None

if __name__ == "__main__":
    # 测试智能路径生成
    land_data = load_land_data()
    
    print("=== 测试智能路径生成 ===")
    
    test_routes = [
        (31.23, 121.508, 1.265, 103.851, "上海->新加坡"),
        (22.3, 114.2, 1.265, 103.851, "香港->新加坡"),
        (29.95, 122.2, 2.2, 102.25, "宁波->马六甲"),
    ]
    
    for start_lat, start_lon, end_lat, end_lon, desc in test_routes:
        print(f"\n--- {desc} ---")
        route = generate_safe_route(start_lat, start_lon, end_lat, end_lon, land_data)
        print(f"生成路径: {route['name']}")
        print(f"路径点数量: {len(route['waypoints'])}")
        
        # 验证路径不穿越陆地
        land_crossings = 0
        for waypoint in route['waypoints']:
            lon, lat = waypoint
            if is_coordinate_on_land(lat, lon, land_data):
                land_crossings += 1
        
        if land_crossings == 0:
            print("✅ 路径安全，无陆地穿越")
        else:
            print(f"⚠️ 仍有 {land_crossings} 个路径点穿越陆地")