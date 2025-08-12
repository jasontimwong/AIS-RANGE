"""
AIS数据解析器 - 将模拟数据转换为AISTarget对象
"""

from typing import List, Dict, Any
from datetime import datetime
from lib.ais import AISTarget, NavStatus, ShipType
from lib.ais.ais_simulator_data import AIS_SIMULATION_VESSELS

class AISParser:
    """AIS数据解析器"""
    
    @staticmethod
    def parse_simulation_vessel(vessel_data: Dict[str, Any]) -> AISTarget:
        """解析模拟船只数据为AISTarget"""
        
        # 映射船舶类型
        type_map = {
            "cargo": ShipType.CARGO,
            "tanker": ShipType.TANKER,
            "passenger": ShipType.PASSENGER,
            "fishing": ShipType.FISHING,
            "other": ShipType.OTHER
        }
        
        # 创建AISTarget
        target = AISTarget(
            mmsi=vessel_data["mmsi"],
            timestamp=datetime.utcnow(),
            position=(vessel_data["position"][1], vessel_data["position"][0]),  # (lat, lon)
            sog=float(vessel_data["speed"]),
            cog=float(vessel_data["course"]),
            heading=float(vessel_data["heading"]),
            nav_status=NavStatus(vessel_data["nav_status"]),
            ship_type=type_map.get(vessel_data["type"], ShipType.OTHER),
            name=vessel_data["name"],
            destination=vessel_data["destination"],
            draught=vessel_data.get("draught"),
            dimensions={
                'to_bow': vessel_data["length"] // 2,
                'to_stern': vessel_data["length"] - vessel_data["length"] // 2,
                'to_port': vessel_data["width"] // 2,
                'to_starboard': vessel_data["width"] - vessel_data["width"] // 2
            }
        )
        
        return target
    
    @staticmethod
    def get_all_targets() -> List[AISTarget]:
        """获取所有模拟AIS目标"""
        targets = []
        for vessel_data in AIS_SIMULATION_VESSELS:
            try:
                target = AISParser.parse_simulation_vessel(vessel_data)
                targets.append(target)
            except Exception as e:
                print(f"解析船只 {vessel_data.get('mmsi', 'unknown')} 失败: {e}")
        return targets
    
    @staticmethod
    def get_targets_in_area(center_lat: float, center_lon: float, 
                           radius_nm: float) -> List[AISTarget]:
        """获取指定区域内的AIS目标"""
        import math
        
        targets = []
        all_targets = AISParser.get_all_targets()
        
        for target in all_targets:
            # 计算距离（简化计算）
            lat_diff = target.position[0] - center_lat
            lon_diff = target.position[1] - center_lon
            
            # 转换为海里（1度纬度约60海里）
            lat_dist = lat_diff * 60
            lon_dist = lon_diff * 60 * math.cos(math.radians(center_lat))
            distance = math.sqrt(lat_dist**2 + lon_dist**2)
            
            if distance <= radius_nm:
                targets.append(target)
        
        return targets