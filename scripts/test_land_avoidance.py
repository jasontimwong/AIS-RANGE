#!/usr/bin/env python3
"""
测试路径是否正确避开陆地
"""

import requests
import json
import math

def test_route(start_lat, start_lon, end_lat, end_lon, route_name):
    """测试一条路线"""
    print(f"\n测试路线: {route_name}")
    print(f"起点: ({start_lat}, {start_lon})")
    print(f"终点: ({end_lat}, {end_lon})")
    
    # 请求路径规划
    response = requests.post(
        "http://localhost:8000/api/route/plan_full",
        json={
            "start": {"lat": start_lat, "lon": start_lon},
            "goal": {"lat": end_lat, "lon": end_lon}
        }
    )
    
    if response.status_code != 200:
        print(f"❌ 路径规划失败: {response.status_code}")
        return None
    
    data = response.json()
    coords = data.get("coords", [])
    
    print(f"✓ 路径规划成功: {len(coords)} 个航点")
    print(f"  规划时间: {data.get('planning_time_s', 0):.3f}秒")
    
    # 分析路径是否避开了主要陆地
    land_areas = {
        "中国大陆": {"min_lon": 110, "max_lon": 123, "min_lat": 20, "max_lat": 41},
        "台湾": {"min_lon": 120, "max_lon": 122, "min_lat": 22, "max_lat": 25.5},
        "菲律宾": {"min_lon": 119, "max_lon": 126, "min_lat": 5, "max_lat": 20},
        "越南": {"min_lon": 102, "max_lon": 109, "min_lat": 9, "max_lat": 23},
    }
    
    # 检查路径点是否穿过陆地
    for i, coord in enumerate(coords):
        lon, lat = coord[0], coord[1]
        for land_name, bounds in land_areas.items():
            if (bounds["min_lon"] < lon < bounds["max_lon"] and 
                bounds["min_lat"] < lat < bounds["max_lat"]):
                # 更精细的检查 - 允许沿海航行
                if land_name == "中国大陆":
                    # 检查是否在沿海区域（经度接近海岸线）
                    if not (lon > 121 or lat < 23):  # 东海岸或南海岸
                        print(f"  ⚠️ 航点 {i+1} 可能穿过{land_name}: ({lat:.2f}, {lon:.2f})")
    
    return coords

def main():
    print("=" * 60)
    print("亚太地区海上路径避障测试")
    print("=" * 60)
    
    # 测试几条典型航线
    test_routes = [
        (31.23, 121.508, 22.3, 114.2, "上海 → 香港"),
        (31.23, 121.508, 1.265, 103.851, "上海 → 新加坡"),
        (22.3, 114.2, 1.265, 103.851, "香港 → 新加坡"),
        (35.0, 129.0, 1.265, 103.851, "釜山 → 新加坡"),
    ]
    
    for start_lat, start_lon, end_lat, end_lon, name in test_routes:
        coords = test_route(start_lat, start_lon, end_lat, end_lon, name)
        
        if coords and len(coords) > 1:
            # 计算总距离
            total_dist = 0
            for i in range(len(coords) - 1):
                lon1, lat1 = coords[i]
                lon2, lat2 = coords[i+1]
                
                # Haversine formula
                R = 6371  # Earth radius in km
                dlat = math.radians(lat2 - lat1)
                dlon = math.radians(lon2 - lon1)
                a = math.sin(dlat/2)**2 + math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) * math.sin(dlon/2)**2
                c = 2 * math.atan2(math.sqrt(a), math.sqrt(1-a))
                dist = R * c
                total_dist += dist
            
            print(f"  总航程: {total_dist:.1f} km")
    
    print("\n" + "=" * 60)
    print("测试完成")
    print("=" * 60)

if __name__ == "__main__":
    main()