#!/usr/bin/env python3
"""
测试动态路径规划API
"""

import requests
import json
import time

# API base URL
BASE_URL = "http://localhost:8000"

def test_dynamic_route():
    """测试动态路径规划完整流程"""
    
    print("=" * 50)
    print("动态路径规划API测试")
    print("=" * 50)
    
    # 1. 初始化路径
    print("\n1. 初始化路径...")
    waypoints = [
        {"lat": 31.23, "lon": 121.508},    # 上海
        {"lat": 31.0, "lon": 122.0},       # 东海
        {"lat": 30.5, "lon": 122.5},       # 继续东海
        {"lat": 29.5, "lon": 123.0},       # 南下
    ]
    
    response = requests.post(
        f"{BASE_URL}/api/route/initialize",
        json={"waypoints": waypoints}
    )
    
    if response.status_code == 200:
        data = response.json()
        print(f"✅ 初始化成功: {data}")
    else:
        print(f"❌ 初始化失败: {response.status_code} - {response.text}")
        return
    
    # 2. 获取动态路径
    print("\n2. 获取动态路径...")
    time.sleep(1)  # 等待初始化完成
    
    response = requests.get(
        f"{BASE_URL}/api/route/dynamic",
        params={"current_lat": 31.23, "current_lon": 121.508}
    )
    
    if response.status_code == 200:
        data = response.json()
        print(f"✅ 获取成功:")
        print(f"   - 状态: {data['status']}")
        print(f"   - 威胁数量: {data.get('threat_count', 0)}")
        
        if 'route_comparison' in data:
            comparison = data['route_comparison']
            print(f"   - 原始路径点数: {len(comparison.get('original_route', []))}")
            print(f"   - 动态路径点数: {len(comparison.get('dynamic_route', []))}")
            print(f"   - 避让点数: {len(comparison.get('avoidance_points', []))}")
            print(f"   - 活跃威胁: {comparison.get('active_threats', [])}")
            
            if comparison.get('avoidance_points'):
                print("\n   避让点坐标:")
                for i, point in enumerate(comparison['avoidance_points'], 1):
                    print(f"     {i}. {point}")
    else:
        print(f"❌ 获取失败: {response.status_code} - {response.text}")
        return
    
    # 3. 获取AIS目标
    print("\n3. 查询AIS目标...")
    response = requests.get(
        f"{BASE_URL}/api/ais/targets",
        params={"lat": 31.23, "lon": 121.508, "range_nm": 100}
    )
    
    if response.status_code == 200:
        data = response.json()
        targets = data.get('targets', data) if isinstance(data, dict) else data
        print(f"✅ 发现 {len(targets)} 个AIS目标")
        for i, target in enumerate(targets):
            if i >= 3:  # 只显示前3个
                break
            print(f"   - {target['name']} (MMSI: {target['mmsi']})")
            print(f"     位置: ({target['lat']:.3f}, {target['lon']:.3f})")
            print(f"     速度: {target['sog']} 节, 航向: {target['cog']}°")
    
    print("\n" + "=" * 50)
    print("测试完成!")
    print("=" * 50)

if __name__ == "__main__":
    test_dynamic_route()