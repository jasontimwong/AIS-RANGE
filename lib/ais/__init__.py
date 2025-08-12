"""
AIS (Automatic Identification System) Module
动态避碰系统核心组件
"""

from dataclasses import dataclass
from typing import Tuple, Optional, Dict, Any
from datetime import datetime
from enum import IntEnum

class NavStatus(IntEnum):
    """航行状态枚举"""
    UNDER_WAY = 0
    AT_ANCHOR = 1
    NOT_UNDER_COMMAND = 2
    RESTRICTED_MANEUVERABILITY = 3
    CONSTRAINED_BY_DRAUGHT = 4
    MOORED = 5
    AGROUND = 6
    FISHING = 7
    SAILING = 8

class ShipType(IntEnum):
    """船舶类型枚举"""
    NOT_AVAILABLE = 0
    FISHING = 30
    TOWING = 31
    DREDGING = 33
    DIVING = 34
    MILITARY = 35
    SAILING = 36
    PLEASURE_CRAFT = 37
    HIGH_SPEED = 40
    PASSENGER = 60
    CARGO = 70
    TANKER = 80
    OTHER = 90

@dataclass
class AISTarget:
    """AIS目标数据结构"""
    mmsi: str                           # 海上移动识别码
    timestamp: datetime                  # 数据时间戳
    position: Tuple[float, float]        # (lat, lon) in degrees
    sog: float                          # Speed over ground (knots)
    cog: float                          # Course over ground (degrees)
    heading: float                      # True heading (degrees)
    nav_status: NavStatus               # Navigation status
    ship_type: Optional[ShipType] = None
    name: Optional[str] = None
    call_sign: Optional[str] = None
    destination: Optional[str] = None
    eta: Optional[datetime] = None
    draught: Optional[float] = None     # Meters
    dimensions: Optional[Dict[str, float]] = None  # to_bow, to_stern, to_port, to_starboard
    
    def __post_init__(self):
        """验证数据有效性"""
        assert -90 <= self.position[0] <= 90, f"Invalid latitude: {self.position[0]}"
        assert -180 <= self.position[1] <= 180, f"Invalid longitude: {self.position[1]}"
        assert 0 <= self.sog <= 102.3, f"Invalid SOG: {self.sog}"
        assert 0 <= self.cog <= 360, f"Invalid COG: {self.cog}"
        assert 0 <= self.heading <= 360, f"Invalid heading: {self.heading}"
    
    @property
    def length(self) -> Optional[float]:
        """获取船长"""
        if self.dimensions:
            return self.dimensions.get('to_bow', 0) + self.dimensions.get('to_stern', 0)
        return None
    
    @property
    def width(self) -> Optional[float]:
        """获取船宽"""
        if self.dimensions:
            return self.dimensions.get('to_port', 0) + self.dimensions.get('to_starboard', 0)
        return None
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            'mmsi': self.mmsi,
            'timestamp': self.timestamp.isoformat(),
            'lat': self.position[0],
            'lon': self.position[1],
            'sog': self.sog,
            'cog': self.cog,
            'heading': self.heading,
            'nav_status': self.nav_status.value,
            'ship_type': self.ship_type.value if self.ship_type else None,
            'name': self.name,
            'destination': self.destination,
            'draught': self.draught,
            'length': self.length,
            'width': self.width
        }