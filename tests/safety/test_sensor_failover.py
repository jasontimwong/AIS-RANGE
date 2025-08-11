"""
Tests for Sensor Failover and Degradation
"""

import pytest
import numpy as np
from datetime import datetime, timedelta
import sys
import os

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from lib.safety.sensor_failover import (
    SensorStatus,
    DataQuality,
    SensorReading,
    SensorConfig,
    SensorHealthMonitor,
    SensorFailoverManager,
    DegradedModeController
)


class TestSensorReading:
    """Test SensorReading class"""
    
    def test_reading_creation(self):
        """Test creating sensor reading"""
        reading = SensorReading(
            sensor_id="gps_1",
            value=(10.0, 20.0),
            timestamp=datetime.now(),
            quality=DataQuality.HIGH,
            confidence=0.95
        )
        
        assert reading.sensor_id == "gps_1"
        assert reading.value == (10.0, 20.0)
        assert reading.quality == DataQuality.HIGH
        assert reading.confidence == 0.95


class TestSensorHealthMonitor:
    """Test SensorHealthMonitor class"""
    
    def test_initialization(self):
        """Test health monitor initialization"""
        monitor = SensorHealthMonitor(window_size=50)
        
        assert monitor.window_size == 50
        assert len(monitor.sensor_history) == 0
    
    def test_update_healthy_sensor(self):
        """Test updating healthy sensor"""
        monitor = SensorHealthMonitor()
        
        # Add healthy readings
        for i in range(10):
            reading = SensorReading(
                sensor_id="gps_1",
                value=(10.0 + i, 20.0),
                timestamp=datetime.now() + timedelta(seconds=i),
                quality=DataQuality.HIGH,
                confidence=0.95
            )
            status = monitor.update(reading)
        
        assert status == SensorStatus.HEALTHY
        assert len(monitor.sensor_history["gps_1"]) == 10
    
    def test_degraded_sensor_detection(self):
        """Test detecting degraded sensor"""
        monitor = SensorHealthMonitor()
        
        # Add mixed quality readings
        for i in range(10):
            quality = DataQuality.HIGH if i < 3 else DataQuality.LOW
            reading = SensorReading(
                sensor_id="radar_1",
                value=100.0 + i,
                timestamp=datetime.now() + timedelta(seconds=i),
                quality=quality,
                confidence=0.4
            )
            status = monitor.update(reading)
        
        # Should be degraded due to low quality
        assert status in [SensorStatus.DEGRADED, SensorStatus.RECOVERING]
    
    def test_failed_sensor_detection(self):
        """Test detecting failed sensor"""
        monitor = SensorHealthMonitor()
        
        # Add invalid readings
        for i in range(5):
            reading = SensorReading(
                sensor_id="depth_1",
                value=None,
                timestamp=datetime.now() + timedelta(seconds=i),
                quality=DataQuality.INVALID,
                confidence=0.0
            )
            status = monitor.update(reading)
        
        assert status == SensorStatus.FAILED
    
    def test_sensor_health_metrics(self):
        """Test getting sensor health metrics"""
        monitor = SensorHealthMonitor()
        
        # Add some readings
        for i in range(5):
            reading = SensorReading(
                sensor_id="ais_1",
                value={"mmsi": 123456},
                timestamp=datetime.now() + timedelta(seconds=i),
                quality=DataQuality.MEDIUM,
                confidence=0.7
            )
            monitor.update(reading)
        
        metrics = monitor.get_sensor_health("ais_1")
        
        assert metrics['status'] in [SensorStatus.HEALTHY, SensorStatus.DEGRADED, SensorStatus.RECOVERING]
        assert metrics['sample_count'] == 5
        assert 'avg_confidence' in metrics
        assert 'quality_distribution' in metrics


class TestSensorFailoverManager:
    """Test SensorFailoverManager class"""
    
    def test_initialization(self):
        """Test failover manager initialization"""
        manager = SensorFailoverManager()
        
        assert len(manager.sensors) == 0
        assert len(manager.redundancy_groups) == 0
    
    def test_register_sensor(self):
        """Test sensor registration"""
        manager = SensorFailoverManager()
        
        config = SensorConfig(
            sensor_id="gps_primary",
            sensor_type="gps",
            priority=10,
            redundancy_group="navigation"
        )
        
        manager.register_sensor(config)
        
        assert "gps_primary" in manager.sensors
        assert "navigation" in manager.redundancy_groups
        assert "gps_primary" in manager.redundancy_groups["navigation"]
    
    def test_process_healthy_reading(self):
        """Test processing healthy sensor reading"""
        manager = SensorFailoverManager()
        
        # Register sensor
        config = SensorConfig(
            sensor_id="gps_1",
            sensor_type="gps",
            priority=10
        )
        manager.register_sensor(config)
        
        # Process healthy reading
        reading = SensorReading(
            sensor_id="gps_1",
            value=(10.0, 20.0),
            timestamp=datetime.now(),
            quality=DataQuality.HIGH,
            confidence=0.95
        )
        
        result = manager.process_reading(reading)
        assert result == reading  # Should return unchanged
    
    def test_failover_to_backup(self):
        """Test failover to backup sensor"""
        manager = SensorFailoverManager()
        
        # Register primary and backup sensors
        primary = SensorConfig(
            sensor_id="gps_primary",
            sensor_type="gps",
            priority=10,
            redundancy_group="navigation"
        )
        backup = SensorConfig(
            sensor_id="gps_backup",
            sensor_type="gps",
            priority=5,
            redundancy_group="navigation"
        )
        
        manager.register_sensor(primary)
        manager.register_sensor(backup)
        
        # Add healthy reading for backup
        backup_reading = SensorReading(
            sensor_id="gps_backup",
            value=(15.0, 25.0),
            timestamp=datetime.now(),
            quality=DataQuality.HIGH,
            confidence=0.9
        )
        manager.health_monitor.update(backup_reading)
        manager.health_monitor.sensor_status["gps_backup"] = SensorStatus.HEALTHY
        
        # Process failed primary reading
        failed_reading = SensorReading(
            sensor_id="gps_primary",
            value=None,
            timestamp=datetime.now(),
            quality=DataQuality.INVALID,
            confidence=0.0
        )
        
        # Mark primary as failed
        manager.health_monitor.sensor_status["gps_primary"] = SensorStatus.FAILED
        
        result = manager.process_reading(failed_reading)
        
        # Should get backup reading
        if result:
            assert result.sensor_id == "gps_backup"
            assert len(manager.failover_history) > 0
    
    def test_weighted_average_fusion(self):
        """Test weighted average fusion"""
        manager = SensorFailoverManager()
        
        readings = [
            SensorReading("s1", 10.0, datetime.now(), DataQuality.HIGH, 0.9),
            SensorReading("s2", 12.0, datetime.now(), DataQuality.MEDIUM, 0.7),
            SensorReading("s3", 11.0, datetime.now(), DataQuality.HIGH, 0.8)
        ]
        
        fused = manager.fuse_readings(readings, strategy='weighted_average')
        
        assert fused is not None
        assert fused.sensor_id == 'fused'
        assert 10.0 <= fused.value <= 12.0  # Should be weighted average
    
    def test_voting_fusion(self):
        """Test voting fusion"""
        manager = SensorFailoverManager()
        
        readings = [
            SensorReading("s1", "SAFE", datetime.now(), DataQuality.HIGH, 0.9),
            SensorReading("s2", "SAFE", datetime.now(), DataQuality.MEDIUM, 0.7),
            SensorReading("s3", "DANGER", datetime.now(), DataQuality.LOW, 0.5)
        ]
        
        fused = manager.fuse_readings(readings, strategy='voting')
        
        assert fused is not None
        assert fused.value == "SAFE"  # Majority vote
    
    def test_degradation_status(self):
        """Test getting degradation status"""
        manager = SensorFailoverManager()
        
        # Register sensors
        for i in range(4):
            config = SensorConfig(
                sensor_id=f"sensor_{i}",
                sensor_type="generic",
                priority=5
            )
            manager.register_sensor(config)
        
        # Set different statuses
        manager.health_monitor.sensor_status["sensor_0"] = SensorStatus.HEALTHY
        manager.health_monitor.sensor_status["sensor_1"] = SensorStatus.HEALTHY
        manager.health_monitor.sensor_status["sensor_2"] = SensorStatus.DEGRADED
        manager.health_monitor.sensor_status["sensor_3"] = SensorStatus.FAILED
        
        status = manager.get_degradation_status()
        
        assert status['level'] == 'DEGRADED'
        assert status['total_sensors'] == 4
        assert status['sensor_status']['healthy'] == 2
        assert status['sensor_status']['failed'] == 1


class TestDegradedModeController:
    """Test DegradedModeController class"""
    
    def test_initialization(self):
        """Test controller initialization"""
        controller = DegradedModeController()
        
        assert controller.current_mode == 'NORMAL'
        assert 'NORMAL' in controller.capabilities
    
    def test_mode_transition(self):
        """Test transitioning between modes"""
        controller = DegradedModeController()
        
        # Transition to degraded mode
        success = controller.transition_to_mode('DEGRADED')
        assert success
        assert controller.current_mode == 'DEGRADED'
        
        # Check capabilities changed
        caps = controller.get_current_capabilities()
        assert caps['collision_avoidance'] == True
        assert caps['optimization'] == False
    
    def test_invalid_mode_transition(self):
        """Test invalid mode transition"""
        controller = DegradedModeController()
        
        success = controller.transition_to_mode('INVALID_MODE')
        assert not success
        assert controller.current_mode == 'NORMAL'
    
    def test_mode_recommendation(self):
        """Test mode recommendation based on degradation"""
        controller = DegradedModeController()
        
        # Normal status
        status = {'level': 'NORMAL', 'sensor_status': {}}
        recommended = controller.recommend_mode(status)
        assert recommended == 'NORMAL'
        
        # Degraded status
        status = {'level': 'DEGRADED', 'sensor_status': {'degraded': 2}}
        recommended = controller.recommend_mode(status)
        assert recommended == 'DEGRADED'
        
        # Critical status
        status = {'level': 'CRITICAL', 'sensor_status': {'failed': 3}}
        recommended = controller.recommend_mode(status)
        assert recommended == 'MANUAL'
    
    def test_capability_checking(self):
        """Test checking capabilities in different modes"""
        controller = DegradedModeController()
        
        # Normal mode - all capabilities
        caps = controller.get_current_capabilities()
        assert caps['auto_navigation'] == True
        assert caps['high_speed'] == True
        
        # Conservative mode - limited capabilities
        controller.transition_to_mode('CONSERVATIVE')
        caps = controller.get_current_capabilities()
        assert caps['auto_navigation'] == False
        assert caps['high_speed'] == False