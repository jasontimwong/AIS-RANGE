"""
AIS Simulator Data - 模拟在上海-新加坡航线上的船只
生成对我们航线构成潜在威胁的AIS目标
"""

from typing import List, Dict, Any
from datetime import datetime, timedelta
import math

# 关键交汇点的AIS模拟船只数据
AIS_SIMULATION_VESSELS = [
    # 1. 长江口区域 - 横穿航道的渡轮
    {
        "mmsi": "413000001",
        "name": "YANGTZE FERRY 1",
        "type": "passenger",
        "position": [122.2, 31.1],  # 横穿我们的航线
        "course": 270,  # 向西
        "speed": 12,
        "heading": 270,
        "length": 120,
        "width": 20,
        "draught": 4.5,
        "destination": "CHONGMING",
        "nav_status": 0  # Under way using engine
    },
    
    # 2. 东海区域 - 渔船群
    {
        "mmsi": "412000001",
        "name": "DONGHAI FISH 23",
        "type": "fishing",
        "position": [122.6, 30.4],
        "course": 45,
        "speed": 6,
        "heading": 45,
        "length": 35,
        "width": 8,
        "draught": 3.0,
        "destination": "FISHING AREA",
        "nav_status": 7  # Engaged in fishing
    },
    {
        "mmsi": "412000002",
        "name": "DONGHAI FISH 45",
        "type": "fishing",
        "position": [122.4, 30.6],
        "course": 180,
        "speed": 4,
        "heading": 180,
        "length": 30,
        "width": 7,
        "draught": 2.8,
        "destination": "FISHING AREA",
        "nav_status": 7
    },
    
    # 3. 台湾海峡 - 对遇的集装箱船
    {
        "mmsi": "477000001",
        "name": "HONG KONG EXPRESS",
        "type": "cargo",
        "position": [119.3, 23.7],
        "course": 20,  # 向北，对遇态势
        "speed": 18,
        "heading": 20,
        "length": 280,
        "width": 42,
        "draught": 12.5,
        "destination": "SHANGHAI",
        "nav_status": 0
    },
    
    # 4. 台湾海峡 - 右舷交叉的油轮
    {
        "mmsi": "563000001", 
        "name": "SINGAPORE TANKER",
        "type": "tanker",
        "position": [120.0, 24.8],
        "course": 240,  # 从右舷交叉
        "speed": 14,
        "heading": 240,
        "length": 330,
        "width": 60,
        "draught": 18.0,
        "destination": "KAOHSIUNG",
        "nav_status": 0
    },
    
    # 5. 南海北部 - 追越态势的散货船
    {
        "mmsi": "636000001",
        "name": "LIBERIA BULK",
        "type": "cargo",
        "position": [116.4, 20.6],
        "course": 200,  # 同向但速度慢
        "speed": 10,
        "heading": 200,
        "length": 225,
        "width": 32,
        "draught": 14.2,
        "destination": "SINGAPORE",
        "nav_status": 0
    },
    
    # 6. 南海中部 - 锚泊的VLCC
    {
        "mmsi": "538000001",
        "name": "MARSHAL GIANT",
        "type": "tanker",
        "position": [114.6, 17.9],
        "course": 0,
        "speed": 0,
        "heading": 135,
        "length": 380,
        "width": 68,
        "draught": 22.0,
        "destination": "ANCHORED",
        "nav_status": 1  # At anchor
    },
    
    # 7. 马六甲海峡入口 - 密集交通
    {
        "mmsi": "566000001",
        "name": "SINGAPORE CONTAINER",
        "type": "cargo",
        "position": [104.3, 3.6],
        "course": 120,
        "speed": 16,
        "heading": 120,
        "length": 366,
        "width": 48,
        "draught": 15.5,
        "destination": "PORT KLANG",
        "nav_status": 0
    },
    {
        "mmsi": "355000001",
        "name": "PANAMA CARRIER",
        "type": "cargo",
        "position": [104.7, 3.4],
        "course": 290,
        "speed": 15,
        "heading": 290,
        "length": 294,
        "width": 32,
        "draught": 13.0,
        "destination": "COLOMBO",
        "nav_status": 0
    },
    
    # 8. 马六甲海峡内 - 限制航速区
    {
        "mmsi": "219000001",
        "name": "MAERSK SINGAPORE",
        "type": "cargo",
        "position": [103.95, 1.9],
        "course": 180,
        "speed": 12,  # 限速区域
        "heading": 180,
        "length": 353,
        "width": 45,
        "draught": 14.5,
        "destination": "SINGAPORE",
        "nav_status": 0
    },
    
    # 9. 新加坡港外 - 等待引航的船只
    {
        "mmsi": "235000001",
        "name": "LONDON TRADER",
        "type": "cargo",
        "position": [103.88, 1.25],
        "course": 0,
        "speed": 2,  # 缓慢移动
        "heading": 90,
        "length": 200,
        "width": 28,
        "draught": 11.0,
        "destination": "SINGAPORE PILOT",
        "nav_status": 4  # Constrained by draught
    },
    
    # 10. 紧急情况 - NUC船只（失控）
    {
        "mmsi": "999000001",
        "name": "EMERGENCY VESSEL",
        "type": "other",
        "position": [108.2, 8.8],
        "course": 135,  # 漂流方向
        "speed": 3,
        "heading": 90,  # 船首向与航向不一致
        "length": 180,
        "width": 25,
        "draught": 9.0,
        "destination": "NOT UNDER CMD",
        "nav_status": 2  # Not under command
    }
]

def generate_ais_messages(base_time: datetime = None) -> List[Dict[str, Any]]:
    """
    生成NMEA格式的AIS消息
    """
    if base_time is None:
        base_time = datetime.utcnow()
    
    messages = []
    for vessel in AIS_SIMULATION_VESSELS:
        # Message Type 1/2/3: Position Report
        msg = {
            "msg_type": 1,
            "repeat": 0,
            "mmsi": vessel["mmsi"],
            "nav_status": vessel["nav_status"],
            "rot": 0,  # Rate of turn
            "sog": vessel["speed"],
            "position_accuracy": 1,
            "lon": vessel["position"][0],
            "lat": vessel["position"][1],
            "cog": vessel["course"],
            "heading": vessel["heading"],
            "timestamp": base_time.isoformat(),
            "maneuver": 0,
            "spare": 0,
            "raim": 0,
            "radio": 0
        }
        messages.append(msg)
        
        # Message Type 5: Static and Voyage Related Data
        static_msg = {
            "msg_type": 5,
            "repeat": 0,
            "mmsi": vessel["mmsi"],
            "ais_version": 0,
            "imo": f"IMO{vessel['mmsi'][:7]}",
            "call_sign": f"CALL{vessel['mmsi'][-4:]}",
            "vessel_name": vessel["name"],
            "ship_type": _get_ship_type_code(vessel["type"]),
            "dimensions": {
                "to_bow": vessel["length"] // 2,
                "to_stern": vessel["length"] // 2,
                "to_port": vessel["width"] // 2,
                "to_starboard": vessel["width"] // 2
            },
            "draught": vessel["draught"],
            "destination": vessel["destination"],
            "eta": (base_time + timedelta(hours=2)).isoformat(),
            "timestamp": base_time.isoformat()
        }
        messages.append(static_msg)
    
    return messages

def _get_ship_type_code(vessel_type: str) -> int:
    """获取AIS船舶类型代码"""
    type_map = {
        "cargo": 70,
        "tanker": 80,
        "passenger": 60,
        "fishing": 30,
        "other": 90
    }
    return type_map.get(vessel_type, 90)

def update_vessel_positions(time_delta_seconds: float) -> None:
    """
    更新船只位置（用于动态模拟）
    """
    for vessel in AIS_SIMULATION_VESSELS:
        if vessel["speed"] > 0:
            # 计算位移（海里）
            distance_nm = vessel["speed"] * time_delta_seconds / 3600
            
            # 转换为经纬度变化
            lat_change = distance_nm * math.cos(math.radians(vessel["course"])) / 60
            lon_change = distance_nm * math.sin(math.radians(vessel["course"])) / (60 * math.cos(math.radians(vessel["position"][1])))
            
            # 更新位置
            vessel["position"][0] += lon_change
            vessel["position"][1] += lat_change

# 危险船只标记（用于测试碰撞风险）
HIGH_RISK_VESSELS = ["413000001", "477000001", "563000001", "999000001"]
MEDIUM_RISK_VESSELS = ["412000001", "412000002", "636000001"]