"""
CPA/TCPA计算器 - 扩展现有CPA功能支持AIS目标
"""

from typing import Tuple, Optional, List
from dataclasses import dataclass
import math
from lib.ais import AISTarget

@dataclass
class CPAResult:
    """CPA计算结果"""
    target_mmsi: str
    cpa: float  # 最近会遇距离（海里）
    tcpa: float  # 到达CPA的时间（分钟）
    bearing: float  # 目标方位（度）
    range: float  # 当前距离（海里）
    risk_level: str  # 风险等级: HIGH, MEDIUM, LOW, SAFE

class AISCPACalculator:
    """AIS目标CPA计算器"""
    
    @staticmethod
    def calculate_cpa(own_lat: float, own_lon: float, own_sog: float, own_cog: float,
                     target: AISTarget) -> CPAResult:
        """
        计算与AIS目标的CPA/TCPA
        """
        # 转换单位：节转米/秒
        own_speed_ms = own_sog * 0.514444
        target_speed_ms = target.sog * 0.514444
        
        # 计算相对位置（米）
        lat_diff = target.position[0] - own_lat
        lon_diff = target.position[1] - own_lon
        
        # 简化计算：转换为米
        dx = lon_diff * 111320 * math.cos(math.radians(own_lat))
        dy = lat_diff * 111320
        
        # 当前距离（米）
        current_range = math.sqrt(dx**2 + dy**2)
        
        # 计算速度分量
        own_vx = own_speed_ms * math.sin(math.radians(own_cog))
        own_vy = own_speed_ms * math.cos(math.radians(own_cog))
        
        target_vx = target_speed_ms * math.sin(math.radians(target.cog))
        target_vy = target_speed_ms * math.cos(math.radians(target.cog))
        
        # 相对速度
        dvx = target_vx - own_vx
        dvy = target_vy - own_vy
        
        # 相对速度大小
        dv = math.sqrt(dvx**2 + dvy**2)
        
        if dv < 0.1:  # 几乎无相对运动
            cpa = current_range
            tcpa = float('inf')
        else:
            # TCPA计算（秒）
            tcpa_seconds = -(dx * dvx + dy * dvy) / (dvx**2 + dvy**2)
            
            if tcpa_seconds < 0:  # 已经过了CPA点
                cpa = current_range
                tcpa = 0
            else:
                # CPA距离
                future_dx = dx + dvx * tcpa_seconds
                future_dy = dy + dvy * tcpa_seconds
                cpa = math.sqrt(future_dx**2 + future_dy**2)
                tcpa = tcpa_seconds / 60  # 转换为分钟
        
        # 计算方位
        bearing = math.degrees(math.atan2(dx, dy)) % 360
        
        # 转换为海里
        cpa_nm = cpa / 1852
        range_nm = current_range / 1852
        
        # 评估风险等级
        risk_level = AISCPACalculator._assess_risk(cpa_nm, tcpa)
        
        return CPAResult(
            target_mmsi=target.mmsi,
            cpa=round(cpa_nm, 2),
            tcpa=round(tcpa, 1),
            bearing=round(bearing, 1),
            range=round(range_nm, 2),
            risk_level=risk_level
        )
    
    @staticmethod
    def _assess_risk(cpa_nm: float, tcpa_minutes: float) -> str:
        """评估碰撞风险等级"""
        if tcpa_minutes < 0 or tcpa_minutes == float('inf'):
            return "SAFE"
        
        if cpa_nm < 0.5 and tcpa_minutes < 12:
            return "HIGH"
        elif cpa_nm < 1.0 and tcpa_minutes < 20:
            return "MEDIUM"
        elif cpa_nm < 2.0 and tcpa_minutes < 30:
            return "LOW"
        else:
            return "SAFE"
    
    @staticmethod
    def calculate_multiple_cpa(own_lat: float, own_lon: float, own_sog: float, own_cog: float,
                              targets: List[AISTarget]) -> List[CPAResult]:
        """批量计算CPA"""
        results = []
        for target in targets:
            result = AISCPACalculator.calculate_cpa(own_lat, own_lon, own_sog, own_cog, target)
            results.append(result)
        
        # 按风险等级和TCPA排序
        risk_order = {"HIGH": 0, "MEDIUM": 1, "LOW": 2, "SAFE": 3}
        results.sort(key=lambda x: (risk_order[x.risk_level], x.tcpa if x.tcpa != float('inf') else 999))
        
        return results