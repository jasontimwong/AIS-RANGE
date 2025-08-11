"""
Sensor Failover and Degradation Management
Handles sensor failures with graceful degradation
"""

import numpy as np
from dataclasses import dataclass, field
from typing import List, Dict, Any, Optional, Callable
from datetime import datetime, timedelta
from enum import Enum
import logging

logger = logging.getLogger(__name__)


class SensorStatus(Enum):
    """Sensor operational status"""
    HEALTHY = "healthy"
    DEGRADED = "degraded"
    FAILED = "failed"
    RECOVERING = "recovering"


class DataQuality(Enum):
    """Data quality levels"""
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"
    INVALID = "invalid"


@dataclass
class SensorReading:
    """Single sensor reading with metadata"""
    sensor_id: str
    value: Any
    timestamp: datetime
    quality: DataQuality
    confidence: float  # 0 to 1
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class SensorConfig:
    """Sensor configuration"""
    sensor_id: str
    sensor_type: str  # 'gps', 'radar', 'ais', 'depth', 'gyro'
    priority: int  # Higher number = higher priority
    health_threshold: float = 0.7
    timeout_seconds: float = 5.0
    min_update_rate_hz: float = 1.0
    redundancy_group: Optional[str] = None


class SensorHealthMonitor:
    """Monitor sensor health and data quality"""
    
    def __init__(self, window_size: int = 100):
        """
        Initialize health monitor.
        
        Args:
            window_size: Number of samples for statistics
        """
        self.window_size = window_size
        self.sensor_history: Dict[str, List[SensorReading]] = {}
        self.sensor_status: Dict[str, SensorStatus] = {}
        self.last_update: Dict[str, datetime] = {}
        
    def update(self, reading: SensorReading) -> SensorStatus:
        """
        Update sensor health based on new reading.
        
        Args:
            reading: New sensor reading
            
        Returns:
            Updated sensor status
        """
        sensor_id = reading.sensor_id
        
        # Initialize if new sensor
        if sensor_id not in self.sensor_history:
            self.sensor_history[sensor_id] = []
            self.sensor_status[sensor_id] = SensorStatus.HEALTHY
        
        # Add to history
        self.sensor_history[sensor_id].append(reading)
        if len(self.sensor_history[sensor_id]) > self.window_size:
            self.sensor_history[sensor_id].pop(0)
        
        # Update last update time
        self.last_update[sensor_id] = reading.timestamp
        
        # Evaluate health
        status = self._evaluate_health(sensor_id)
        self.sensor_status[sensor_id] = status
        
        return status
    
    def _evaluate_health(self, sensor_id: str) -> SensorStatus:
        """Evaluate sensor health based on history"""
        history = self.sensor_history[sensor_id]
        
        if not history:
            return SensorStatus.FAILED
        
        # Check data quality
        quality_scores = {
            DataQuality.HIGH: 1.0,
            DataQuality.MEDIUM: 0.7,
            DataQuality.LOW: 0.3,
            DataQuality.INVALID: 0.0
        }
        
        avg_quality = np.mean([
            quality_scores[r.quality] for r in history
        ])
        
        # Check confidence
        avg_confidence = np.mean([r.confidence for r in history])
        
        # Check update rate
        if len(history) > 1:
            time_diffs = [
                (history[i].timestamp - history[i-1].timestamp).total_seconds()
                for i in range(1, len(history))
            ]
            avg_interval = np.mean(time_diffs)
            update_rate_ok = avg_interval < 2.0  # Max 2 seconds between updates
        else:
            update_rate_ok = True
        
        # Determine status
        health_score = avg_quality * avg_confidence
        
        if health_score > 0.8 and update_rate_ok:
            return SensorStatus.HEALTHY
        elif health_score > 0.5:
            return SensorStatus.DEGRADED
        elif health_score > 0.2:
            return SensorStatus.RECOVERING
        else:
            return SensorStatus.FAILED
    
    def get_sensor_health(self, sensor_id: str) -> Dict[str, Any]:
        """Get detailed health metrics for a sensor"""
        if sensor_id not in self.sensor_history:
            return {'status': SensorStatus.FAILED, 'metrics': {}}
        
        history = self.sensor_history[sensor_id]
        
        metrics = {
            'status': self.sensor_status.get(sensor_id, SensorStatus.FAILED),
            'last_update': self.last_update.get(sensor_id),
            'sample_count': len(history),
            'avg_confidence': np.mean([r.confidence for r in history]) if history else 0,
            'quality_distribution': self._get_quality_distribution(history)
        }
        
        return metrics
    
    def _get_quality_distribution(self, history: List[SensorReading]) -> Dict[str, float]:
        """Get distribution of quality levels"""
        if not history:
            return {}
        
        counts = {q: 0 for q in DataQuality}
        for reading in history:
            counts[reading.quality] += 1
        
        total = len(history)
        return {q.value: count/total for q, count in counts.items()}


class SensorFailoverManager:
    """Manage sensor failover and data fusion"""
    
    def __init__(self):
        """Initialize failover manager"""
        self.sensors: Dict[str, SensorConfig] = {}
        self.health_monitor = SensorHealthMonitor()
        self.redundancy_groups: Dict[str, List[str]] = {}
        self.fusion_strategies: Dict[str, Callable] = {}
        self.failover_history = []
        
        self._setup_default_strategies()
        
    def _setup_default_strategies(self):
        """Setup default fusion strategies"""
        self.fusion_strategies['weighted_average'] = self._weighted_average_fusion
        self.fusion_strategies['voting'] = self._voting_fusion
        self.fusion_strategies['kalman'] = self._kalman_fusion
        
    def register_sensor(self, config: SensorConfig):
        """Register a sensor with the manager"""
        self.sensors[config.sensor_id] = config
        
        # Update redundancy groups
        if config.redundancy_group:
            if config.redundancy_group not in self.redundancy_groups:
                self.redundancy_groups[config.redundancy_group] = []
            self.redundancy_groups[config.redundancy_group].append(config.sensor_id)
        
        logger.info(f"Registered sensor {config.sensor_id} (type: {config.sensor_type})")
    
    def process_reading(self, reading: SensorReading) -> Optional[SensorReading]:
        """
        Process sensor reading with failover logic.
        
        Args:
            reading: Incoming sensor reading
            
        Returns:
            Processed reading (possibly fused from multiple sensors)
        """
        # Update health
        status = self.health_monitor.update(reading)
        
        # Check if failover needed
        if status in [SensorStatus.FAILED, SensorStatus.DEGRADED]:
            return self._handle_failover(reading)
        
        return reading
    
    def _handle_failover(self, failed_reading: SensorReading) -> Optional[SensorReading]:
        """Handle sensor failure with redundancy"""
        sensor_config = self.sensors.get(failed_reading.sensor_id)
        
        if not sensor_config or not sensor_config.redundancy_group:
            logger.warning(f"No redundancy for failed sensor {failed_reading.sensor_id}")
            return failed_reading  # Return degraded reading
        
        # Find healthy sensors in same group
        group = sensor_config.redundancy_group
        healthy_sensors = []
        
        for sensor_id in self.redundancy_groups[group]:
            if sensor_id != failed_reading.sensor_id:
                status = self.health_monitor.sensor_status.get(
                    sensor_id, SensorStatus.FAILED
                )
                if status == SensorStatus.HEALTHY:
                    healthy_sensors.append(sensor_id)
        
        if not healthy_sensors:
            logger.error(f"No healthy sensors available in group {group}")
            return None
        
        # Use primary healthy sensor
        primary = healthy_sensors[0]
        history = self.health_monitor.sensor_history.get(primary, [])
        
        if history:
            # Log failover
            self.failover_history.append({
                'timestamp': datetime.now(),
                'failed_sensor': failed_reading.sensor_id,
                'failover_to': primary,
                'group': group
            })
            
            logger.info(f"Failover: {failed_reading.sensor_id} -> {primary}")
            return history[-1]  # Return latest reading from healthy sensor
        
        return None
    
    def fuse_readings(self,
                     readings: List[SensorReading],
                     strategy: str = 'weighted_average') -> Optional[SensorReading]:
        """
        Fuse multiple sensor readings.
        
        Args:
            readings: List of readings to fuse
            strategy: Fusion strategy to use
            
        Returns:
            Fused reading
        """
        if not readings:
            return None
        
        if len(readings) == 1:
            return readings[0]
        
        fusion_func = self.fusion_strategies.get(strategy, self._weighted_average_fusion)
        return fusion_func(readings)
    
    def _weighted_average_fusion(self, readings: List[SensorReading]) -> SensorReading:
        """Weighted average fusion based on confidence"""
        # Filter valid readings
        valid_readings = [
            r for r in readings 
            if r.quality != DataQuality.INVALID and r.confidence > 0
        ]
        
        if not valid_readings:
            return readings[0]  # Return first reading as fallback
        
        # Calculate weights
        weights = np.array([r.confidence for r in valid_readings])
        weights = weights / weights.sum()
        
        # Fuse values (assuming numeric)
        try:
            values = np.array([float(r.value) for r in valid_readings])
            fused_value = np.sum(values * weights)
            
            # Calculate fused confidence
            fused_confidence = np.mean([r.confidence for r in valid_readings])
            
            # Determine quality
            if fused_confidence > 0.8:
                fused_quality = DataQuality.HIGH
            elif fused_confidence > 0.5:
                fused_quality = DataQuality.MEDIUM
            else:
                fused_quality = DataQuality.LOW
            
            return SensorReading(
                sensor_id='fused',
                value=fused_value,
                timestamp=datetime.now(),
                quality=fused_quality,
                confidence=fused_confidence,
                metadata={'fusion_strategy': 'weighted_average', 'source_count': len(valid_readings)}
            )
        except (ValueError, TypeError):
            # Non-numeric values - return highest confidence reading
            return max(valid_readings, key=lambda r: r.confidence)
    
    def _voting_fusion(self, readings: List[SensorReading]) -> SensorReading:
        """Voting-based fusion for discrete values"""
        # Count votes
        votes = {}
        for reading in readings:
            if reading.quality != DataQuality.INVALID:
                value = str(reading.value)
                if value not in votes:
                    votes[value] = 0
                votes[value] += reading.confidence
        
        if not votes:
            return readings[0]
        
        # Select winning value
        winning_value = max(votes, key=votes.get)
        
        # Find original reading with winning value
        for reading in readings:
            if str(reading.value) == winning_value:
                return SensorReading(
                    sensor_id='fused',
                    value=reading.value,
                    timestamp=datetime.now(),
                    quality=reading.quality,
                    confidence=votes[winning_value] / len(readings),
                    metadata={'fusion_strategy': 'voting', 'votes': votes}
                )
        
        return readings[0]
    
    def _kalman_fusion(self, readings: List[SensorReading]) -> SensorReading:
        """Simplified Kalman filter fusion"""
        # This is a placeholder for a proper Kalman filter
        # In production, use a proper implementation
        return self._weighted_average_fusion(readings)
    
    def get_degradation_status(self) -> Dict[str, Any]:
        """Get current degradation status"""
        total_sensors = len(self.sensors)
        
        status_counts = {
            SensorStatus.HEALTHY: 0,
            SensorStatus.DEGRADED: 0,
            SensorStatus.FAILED: 0,
            SensorStatus.RECOVERING: 0
        }
        
        for sensor_id in self.sensors:
            status = self.health_monitor.sensor_status.get(
                sensor_id, SensorStatus.FAILED
            )
            status_counts[status] += 1
        
        degradation_level = 'NORMAL'
        if status_counts[SensorStatus.FAILED] > total_sensors * 0.5:
            degradation_level = 'CRITICAL'
        elif status_counts[SensorStatus.FAILED] > 0 or status_counts[SensorStatus.DEGRADED] > total_sensors * 0.3:
            degradation_level = 'DEGRADED'
        
        return {
            'level': degradation_level,
            'sensor_status': {s.value: c for s, c in status_counts.items()},
            'total_sensors': total_sensors,
            'failover_count': len(self.failover_history),
            'timestamp': datetime.now()
        }


class DegradedModeController:
    """Controller for degraded operation modes"""
    
    def __init__(self):
        """Initialize degraded mode controller"""
        self.current_mode = 'NORMAL'
        self.mode_stack = ['NORMAL']
        self.capabilities = self._define_capabilities()
        
    def _define_capabilities(self) -> Dict[str, Dict[str, bool]]:
        """Define capabilities for each mode"""
        return {
            'NORMAL': {
                'auto_navigation': True,
                'collision_avoidance': True,
                'weather_routing': True,
                'optimization': True,
                'high_speed': True
            },
            'DEGRADED': {
                'auto_navigation': True,
                'collision_avoidance': True,
                'weather_routing': False,
                'optimization': False,
                'high_speed': False
            },
            'CONSERVATIVE': {
                'auto_navigation': False,
                'collision_avoidance': True,
                'weather_routing': False,
                'optimization': False,
                'high_speed': False
            },
            'MANUAL': {
                'auto_navigation': False,
                'collision_avoidance': False,
                'weather_routing': False,
                'optimization': False,
                'high_speed': False
            }
        }
    
    def transition_to_mode(self, new_mode: str) -> bool:
        """
        Transition to new operational mode.
        
        Args:
            new_mode: Target mode
            
        Returns:
            Success status
        """
        if new_mode not in self.capabilities:
            logger.error(f"Invalid mode: {new_mode}")
            return False
        
        old_mode = self.current_mode
        self.current_mode = new_mode
        self.mode_stack.append(new_mode)
        
        logger.warning(f"Mode transition: {old_mode} -> {new_mode}")
        
        # Notify subsystems of capability changes
        self._notify_capability_change(old_mode, new_mode)
        
        return True
    
    def _notify_capability_change(self, old_mode: str, new_mode: str):
        """Notify subsystems of capability changes"""
        old_caps = self.capabilities[old_mode]
        new_caps = self.capabilities[new_mode]
        
        for capability, enabled in new_caps.items():
            if enabled != old_caps.get(capability, True):
                status = "enabled" if enabled else "disabled"
                logger.info(f"Capability {capability} {status} in {new_mode} mode")
    
    def get_current_capabilities(self) -> Dict[str, bool]:
        """Get current mode capabilities"""
        return self.capabilities.get(self.current_mode, {})
    
    def recommend_mode(self, degradation_status: Dict[str, Any]) -> str:
        """Recommend operational mode based on degradation"""
        level = degradation_status.get('level', 'NORMAL')
        
        if level == 'CRITICAL':
            return 'MANUAL'
        elif level == 'DEGRADED':
            # Check specific sensor failures
            sensor_status = degradation_status.get('sensor_status', {})
            if sensor_status.get('failed', 0) > 0:
                return 'CONSERVATIVE'
            else:
                return 'DEGRADED'
        else:
            return 'NORMAL'