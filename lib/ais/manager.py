"""
AIS管理器 - 核心管理组件
"""

from typing import Dict, List, Optional, Callable, Tuple
from datetime import datetime, timedelta
from lib.ais import AISTarget
from lib.ais.parser import AISParser
import threading
import time

class AISManager:
    """AIS数据管理器"""
    
    def __init__(self):
        self.targets: Dict[str, AISTarget] = {}
        self.subscribers: List[Callable] = []
        self._running = False
        self._update_thread = None
        self._last_update = datetime.utcnow()
        
    def start(self):
        """启动AIS管理器"""
        if not self._running:
            self._running = True
            self._update_thread = threading.Thread(target=self._update_loop)
            self._update_thread.daemon = True
            self._update_thread.start()
            print("AIS管理器已启动")
    
    def stop(self):
        """停止AIS管理器"""
        self._running = False
        if self._update_thread:
            self._update_thread.join(timeout=1)
        print("AIS管理器已停止")
    
    def _update_loop(self):
        """更新循环"""
        while self._running:
            # 更新AIS数据
            self.update_targets()
            
            # 通知订阅者
            self._notify_subscribers()
            
            # 等待1秒
            time.sleep(1)
    
    def update_targets(self):
        """更新所有AIS目标"""
        # 获取最新数据
        new_targets = AISParser.get_all_targets()
        
        # 更新目标字典
        for target in new_targets:
            # 模拟位置更新
            if target.mmsi in self.targets and target.sog > 0:
                self._update_position(target)
            
            self.targets[target.mmsi] = target
        
        self._last_update = datetime.utcnow()
    
    def _update_position(self, target: AISTarget):
        """更新目标位置（简单模拟）"""
        import math
        
        # 计算时间差
        time_diff = 1.0  # 1秒
        
        # 计算位移（海里）
        distance_nm = target.sog * time_diff / 3600
        
        # 转换为经纬度变化
        lat_change = distance_nm * math.cos(math.radians(target.cog)) / 60
        lon_change = distance_nm * math.sin(math.radians(target.cog)) / (60 * math.cos(math.radians(target.position[0])))
        
        # 更新位置
        new_lat = target.position[0] + lat_change
        new_lon = target.position[1] + lon_change
        target.position = (new_lat, new_lon)
    
    def get_target(self, mmsi: str) -> Optional[AISTarget]:
        """获取指定MMSI的目标"""
        return self.targets.get(mmsi)
    
    def get_all_targets(self) -> List[AISTarget]:
        """获取所有目标"""
        return list(self.targets.values())
    
    def get_targets_in_range(self, center: Tuple[float, float], range_nm: float) -> List[AISTarget]:
        """获取指定范围内的目标"""
        import math
        
        targets_in_range = []
        center_lat, center_lon = center
        
        for target in self.targets.values():
            # 计算距离
            lat_diff = target.position[0] - center_lat
            lon_diff = target.position[1] - center_lon
            
            lat_dist = lat_diff * 60
            lon_dist = lon_diff * 60 * math.cos(math.radians(center_lat))
            distance = math.sqrt(lat_dist**2 + lon_dist**2)
            
            if distance <= range_nm:
                targets_in_range.append(target)
        
        return targets_in_range
    
    def subscribe(self, callback: Callable):
        """订阅AIS更新"""
        self.subscribers.append(callback)
    
    def unsubscribe(self, callback: Callable):
        """取消订阅"""
        if callback in self.subscribers:
            self.subscribers.remove(callback)
    
    def _notify_subscribers(self):
        """通知所有订阅者"""
        for callback in self.subscribers:
            try:
                callback(self.targets)
            except Exception as e:
                print(f"通知订阅者失败: {e}")
    
    def get_statistics(self) -> Dict:
        """获取统计信息"""
        return {
            'total_targets': len(self.targets),
            'last_update': self._last_update.isoformat(),
            'running': self._running,
            'targets_by_status': self._count_by_status(),
            'targets_by_type': self._count_by_type()
        }
    
    def _count_by_status(self) -> Dict[str, int]:
        """按状态统计"""
        counts = {}
        for target in self.targets.values():
            status = str(target.nav_status.name)
            counts[status] = counts.get(status, 0) + 1
        return counts
    
    def _count_by_type(self) -> Dict[str, int]:
        """按类型统计"""
        counts = {}
        for target in self.targets.values():
            if target.ship_type:
                ship_type = str(target.ship_type.name)
                counts[ship_type] = counts.get(ship_type, 0) + 1
        return counts