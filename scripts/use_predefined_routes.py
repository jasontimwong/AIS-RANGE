#!/usr/bin/env python3
"""
使用预定义的安全航线进行路径规划
避免复杂的海图数据处理
"""

import json
import math
from pathlib import Path

# 尝试导入TSS感知路径规划
try:
    from scripts.tss_aware_routing import generate_tss_aware_route, classify_route
    TSS_AVAILABLE = True
except ImportError:
    TSS_AVAILABLE = False

# 预定义的安全航线
SAFE_ROUTES = {
    "shanghai_singapore": {
        "name": "Shanghai to Singapore",
        "waypoints": [
            [121.508, 31.230],  # 上海港
            [121.650, 31.100],  # 长江口外
            [121.800, 30.850],  # 舟山群岛东侧
            [122.100, 30.200],  # 东海开阔水域
            [122.500, 28.500],  # 避开台湾北部
            [121.900, 26.800],  # 台湾海峡北口
            [119.500, 24.000],  # 台湾海峡西侧
            [118.000, 22.300],  # 台湾海峡南部
            [116.000, 19.500],  # 进入南海
            [113.500, 16.000],  # 南海北部
            [111.000, 13.000],  # 南海中部
            [109.000, 10.000],  # 避开越南，南沙西侧
            [107.000, 7.000],   # 纳土纳群岛北侧
            [105.500, 4.500],   # 避开马来半岛
            [104.500, 2.500],   # 新加坡海峡西入口
            [103.851, 1.265]    # 新加坡港
        ]
    },
    "shanghai_hongkong": {
        "name": "Shanghai to Hong Kong",
        "waypoints": [
            [121.508, 31.230],
            [121.700, 30.900],
            [122.000, 30.300],
            [122.200, 29.500],
            [122.100, 28.200],
            [121.500, 26.500],
            [120.300, 24.800],
            [118.500, 23.200],
            [116.500, 22.500],
            [114.200, 22.300]
        ]
    },
    "shanghai_manila": {
        "name": "Shanghai to Manila",
        "waypoints": [
            [121.508, 31.230],
            [121.700, 30.500],
            [122.100, 29.000],
            [122.500, 27.000],
            [122.200, 25.000],
            [121.500, 23.000],
            [120.500, 21.000],
            [119.800, 19.000],
            [120.200, 17.000],
            [120.600, 15.500],
            [120.980, 14.600]
        ]
    },
    "shanghai_busan": {
        "name": "Shanghai to Busan",
        "waypoints": [
            [121.508, 31.230],
            [122.000, 32.000],
            [123.500, 33.000],
            [125.500, 34.000],
            [127.500, 34.500],
            [128.500, 35.000],
            [129.040, 35.100]
        ]
    },
    "shanghai_yokohama": {
        "name": "Shanghai to Yokohama", 
        "waypoints": [
            [121.508, 31.230],
            [123.000, 32.500],
            [125.500, 33.500],
            [128.000, 34.200],
            [131.000, 34.800],
            [134.500, 35.200],
            [137.000, 35.300],
            [139.640, 35.440]
        ]
    },
    "singapore_sydney": {
        "name": "Singapore to Sydney",  
        "waypoints": [
            [103.851, 1.265],
            [105.000, -2.000],
            [107.500, -5.500],
            [110.000, -8.000],
            [113.000, -11.000],
            [116.500, -15.000],
            [120.000, -20.000],
            [125.000, -25.000],
            [130.000, -28.000],
            [135.000, -31.000],
            [140.000, -32.500],
            [145.000, -33.500],
            [150.000, -33.700],
            [151.209, -33.865]
        ]
    },
    "hongkong_singapore": {
        "name": "Hong Kong to Singapore",
        "waypoints": [
            [114.200, 22.300],
            [113.500, 20.500],
            [112.200, 18.000],
            [110.500, 15.500],
            [108.500, 12.500],
            [106.500, 9.500],
            [105.000, 6.500],
            [104.500, 3.200],  # 修正：避开印尼陆地
            [103.851, 1.265]   # 修正：新加坡正确坐标
        ]
    },
    "ningbo_malacca": {
        "name": "Ningbo to Malacca",
        "waypoints": [
            [122.200, 29.950],
            [121.800, 28.500],
            [120.500, 26.000],
            [118.500, 23.000],
            [116.000, 19.500],
            [113.500, 16.000],
            [111.000, 12.500],
            [108.500, 9.000],
            [106.000, 5.500],
            [104.800, 3.800],  # 修正：避开马来西亚陆地
            [99.000, 1.000]    # 修正：马六甲西南安全海域
        ]
    },
    "qingdao_busan": {
        "name": "Qingdao to Busan", 
        "waypoints": [
            [120.380, 36.070],
            [122.000, 36.500],
            [124.000, 36.800],
            [126.500, 36.500],
            [128.000, 35.800],
            [129.040, 35.100]
        ]
    },
    "tianjin_yokohama": {
        "name": "Tianjin to Yokohama",
        "waypoints": [
            [117.750, 39.000],
            [120.000, 38.500],
            [123.000, 37.500],
            [126.500, 36.800],
            [130.000, 36.200],
            [133.500, 35.800],
            [137.000, 35.500],
            [139.640, 35.440]
        ]
    },
    "shenzhen_singapore": {
        "name": "Shenzhen to Singapore",
        "waypoints": [
            [114.100, 22.500],  # Shenzhen Port
            [113.800, 21.500],  # 担杆列岛南侧，离岸进入南海
            [112.000, 19.000],  # 南海北部开阔水域
            [111.000, 16.000],  # 西沙群岛东侧安全水域
            [110.000, 13.000],  # 南海中部深水区
            [108.500, 10.000],  # 避开越南南部，南沙西侧
            [107.000, 7.000],   # 纳土纳群岛北侧
            [105.500, 4.500],   # 避开马来半岛，准备进入新加坡海峡
            [104.500, 2.500],   # 新加坡海峡西入口
            [103.851, 1.265]    # Singapore Port (正确坐标)
        ]
    },
    "guangzhou_jakarta": {
        "name": "Guangzhou to Jakarta",
        "waypoints": [
            [113.250, 23.100],  # Guangzhou Port
            [112.500, 21.500],  # 离岸进入南海
            [110.800, 19.000],  # 南海西部
            [108.500, 16.000],  # 避开海南岛
            [106.500, 12.500],  # 南海南部
            [105.000, 9.000],   # 避开越南
            [104.500, 5.500],   # 纳土纳海
            [105.500, 2.000],   # 避开新加坡
            [106.000, -2.000],  # 邦加海峡
            [106.500, -4.500],  # 爪哇海
            [106.870, -6.100]   # Jakarta Port
        ]
    },
    "xiamen_manila": {
        "name": "Xiamen to Manila",
        "waypoints": [
            [118.080, 24.480],  # Xiamen Port
            [118.500, 23.500],  # 台湾海峡南部
            [119.200, 22.000],  # 避开台湾南端
            [119.800, 20.500],  # 巴士海峡
            [120.200, 19.000],  # 进入菲律宾海
            [120.500, 17.500],  # 吕宋岛西侧
            [120.600, 16.000],  # 沿吕宋岛西岸
            [120.700, 14.400]   # Manila Port (外锚地)
        ]
    }
}

def find_best_route(start_lat, start_lon, end_lat, end_lon):
    """根据起点和终点找到最合适的预定义航线"""
    # 智能匹配：先精确匹配，再模糊匹配
    best_route = None
    min_distance = float('inf')
    EXACT_THRESHOLD = 2.0  # 精确匹配阈值
    FUZZY_THRESHOLD = 5.0  # 模糊匹配阈值
    
    # 第一步：精确匹配
    for route_id, route in SAFE_ROUTES.items():
        waypoints = route["waypoints"]
        # 检查起点和终点的距离
        start_dist = ((waypoints[0][0] - start_lon)**2 + (waypoints[0][1] - start_lat)**2)**0.5
        end_dist = ((waypoints[-1][0] - end_lon)**2 + (waypoints[-1][1] - end_lat)**2)**0.5
        
        # 也可以反向
        start_dist_rev = ((waypoints[-1][0] - start_lon)**2 + (waypoints[-1][1] - start_lat)**2)**0.5
        end_dist_rev = ((waypoints[0][0] - end_lon)**2 + (waypoints[0][1] - end_lat)**2)**0.5
        
        total_dist = min(start_dist + end_dist, start_dist_rev + end_dist_rev)
        
        # 精确匹配
        if total_dist < min_distance and total_dist < EXACT_THRESHOLD:
            min_distance = total_dist
            if start_dist_rev + end_dist_rev < start_dist + end_dist:
                best_route = {
                    "name": route["name"] + " (reversed)",
                    "waypoints": list(reversed(waypoints))
                }
            else:
                best_route = route
    
    # 如果精确匹配成功，返回结果
    if best_route:
        return best_route
    
    # 第二步：模糊匹配 - 基于区域相似性
    # 定义主要港口区域
    major_ports = {
        "shanghai": (31.23, 121.508),
        "singapore": (1.265, 103.851),
        "hongkong": (22.3, 114.2),
        "malacca": (2.2, 102.25),
        "busan": (35.1, 129.04),
        "yokohama": (35.44, 139.64),
        "manila": (14.6, 120.98),
        "ningbo": (29.95, 122.2),
        "qingdao": (36.07, 120.38),
        "tianjin": (39.0, 117.75),
    }
    
    def get_nearest_port(lat, lon):
        """找到最近的主要港口"""
        min_dist = float('inf')
        nearest_port = None
        for port_name, (port_lat, port_lon) in major_ports.items():
            dist = ((port_lat - lat)**2 + (port_lon - lon)**2)**0.5
            if dist < min_dist:
                min_dist = dist
                nearest_port = port_name
        return nearest_port if min_dist < FUZZY_THRESHOLD else None
    
    # 识别起点和终点最接近的港口
    start_port = get_nearest_port(start_lat, start_lon)
    end_port = get_nearest_port(end_lat, end_lon)
    
    if start_port and end_port:
        # 尝试找到连接这两个港口的路径
        route_combinations = [
            f"{start_port}_{end_port}",
            f"{end_port}_{start_port}"
        ]
        
        for combo in route_combinations:
            if combo in SAFE_ROUTES:
                route = SAFE_ROUTES[combo]
                if combo.startswith(end_port):
                    return {
                        "name": route["name"] + " (reversed for fuzzy match)",
                        "waypoints": list(reversed(route["waypoints"]))
                    }
                else:
                    return {
                        "name": route["name"] + " (fuzzy match)",
                        "waypoints": route["waypoints"]
                    }
    
    return None


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
    if not land_data:
        return False
        
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

def load_land_data():
    """加载陆地数据"""
    try:
        with open('/Users/jasonwong/planner/data/asia_pacific_land.json', 'r') as f:
            return json.load(f)
    except:
        return None

def generate_safe_route(start_lat, start_lon, end_lat, end_lon, num_points=30):
    """生成避开陆地的安全路径"""
    land_data = load_land_data()
    
    waypoints = []
    
    for i in range(num_points):
        t = i / (num_points - 1)
        
        # 线性插值
        lat = start_lat + t * (end_lat - start_lat)
        lon = start_lon + t * (end_lon - start_lon)
        
        # 检查是否在陆地上
        if is_coordinate_on_land(lat, lon, land_data):
            # 如果在陆地上，尝试调整到海上
            adjusted = False
            # 方法1：向南/北偏移
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

def generate_optimal_route(start_lat, start_lon, end_lat, end_lon, num_points=30):
    """生成最优路径：优先使用TSS感知路径，回退到安全路径"""
    # 第一优先级：TSS感知路径规划
    if TSS_AVAILABLE:
        try:
            route_type = classify_route(start_lat, start_lon, end_lat, end_lon)
            if route_type != "other":  # 如果是已知的主要航线类型
                tss_route = generate_tss_aware_route(start_lat, start_lon, end_lat, end_lon)
                if len(tss_route['waypoints']) > 2:  # TSS路径有效
                    return tss_route
        except Exception as e:
            print(f"TSS路径生成失败: {e}")
    
    # 第二优先级：智能安全路径
    return generate_safe_route(start_lat, start_lon, end_lat, end_lon, num_points)

def generate_great_circle_route(start_lat, start_lon, end_lat, end_lon, num_points=50):
    """生成大圆航线作为通用后备方案"""
    
    lat1, lon1 = math.radians(start_lat), math.radians(start_lon)
    lat2, lon2 = math.radians(end_lat), math.radians(end_lon)
    
    # 计算大圆距离
    d = 2 * math.asin(math.sqrt(
        math.sin((lat2-lat1)/2)**2 + 
        math.cos(lat1) * math.cos(lat2) * math.sin((lon2-lon1)/2)**2
    ))
    
    waypoints = []
    for i in range(num_points):
        f = i / (num_points - 1)
        if d > 0.001:  # 避免除以零
            a = math.sin((1-f)*d) / math.sin(d)
            b = math.sin(f*d) / math.sin(d)
        else:
            a = 1 - f
            b = f
            
        x = a * math.cos(lat1) * math.cos(lon1) + b * math.cos(lat2) * math.cos(lon2)
        y = a * math.cos(lat1) * math.sin(lon1) + b * math.cos(lat2) * math.sin(lon2)
        z = a * math.sin(lat1) + b * math.sin(lat2)
        
        lat = math.atan2(z, math.sqrt(x*x + y*y))
        lon = math.atan2(y, x)
        
        waypoints.append([math.degrees(lon), math.degrees(lat)])
    
    return {
        "name": f"Great Circle Route",
        "waypoints": waypoints
    }

if __name__ == "__main__":
    # 测试
    route = find_best_route(31.23, 121.508, 22.3, 114.2)
    if route:
        print(f"Found route: {route['name']}")
        print(f"Waypoints: {len(route['waypoints'])}")