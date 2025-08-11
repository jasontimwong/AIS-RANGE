"""
Tests for ETA Window Optimizer
"""

import pytest
import numpy as np
from datetime import datetime, timedelta
import sys
import os

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from lib.eta.optimizer import (
    SpeedSegment,
    ETAConstraint,
    ETAOptimizer
)


class TestSpeedSegment:
    """Test SpeedSegment class"""
    
    def test_segment_creation(self):
        """Test creating speed segment"""
        segment = SpeedSegment(
            start_pos=0.0,
            end_pos=100.0,
            speed=15.0,
            duration=6.67
        )
        
        assert segment.distance == 100.0
        assert segment.speed == 15.0
        assert segment.duration == 6.67


class TestETAConstraint:
    """Test ETAConstraint class"""
    
    def test_constraint_evaluation(self):
        """Test ETA constraint penalty calculation"""
        earliest = datetime(2025, 1, 1, 12, 0)
        latest = datetime(2025, 1, 1, 18, 0)
        
        constraint = ETAConstraint(
            earliest=earliest,
            latest=latest,
            penalty_early=10.0,
            penalty_late=50.0
        )
        
        # Within window - no penalty
        arrival = datetime(2025, 1, 1, 15, 0)
        assert constraint.evaluate(arrival) == 0.0
        
        # 2 hours early
        arrival = datetime(2025, 1, 1, 10, 0)
        assert constraint.evaluate(arrival) == 20.0  # 2 * 10
        
        # 1 hour late
        arrival = datetime(2025, 1, 1, 19, 0)
        assert constraint.evaluate(arrival) == 50.0  # 1 * 50


class TestETAOptimizer:
    """Test ETA Optimizer"""
    
    def test_optimizer_initialization(self):
        """Test optimizer initialization"""
        optimizer = ETAOptimizer(
            min_speed=5.0,
            max_speed=20.0,
            eco_speed=12.0
        )
        
        assert optimizer.min_speed == 5.0
        assert optimizer.max_speed == 20.0
        assert optimizer.eco_speed == 12.0
    
    def test_optimize_constant_speed_feasible(self):
        """Test constant speed optimization - feasible case"""
        optimizer = ETAOptimizer()
        
        departure = datetime(2025, 1, 1, 0, 0)
        constraint = ETAConstraint(
            earliest=datetime(2025, 1, 1, 10, 0),  # 10 hours later
            latest=datetime(2025, 1, 1, 15, 0)     # 15 hours later
        )
        
        result = optimizer.optimize_constant_speed(
            distance=120.0,  # 120 nm
            departure_time=departure,
            constraint=constraint
        )
        
        assert result['status'] == 'success'
        assert 8.0 <= result['optimal_speed'] <= 12.0  # 120nm/15h to 120nm/10h
        assert result['penalty'] == 0.0  # Should be within window
    
    def test_optimize_constant_speed_infeasible_too_fast(self):
        """Test constant speed optimization - requires too high speed"""
        optimizer = ETAOptimizer(max_speed=15.0)
        
        departure = datetime(2025, 1, 1, 0, 0)
        constraint = ETAConstraint(
            earliest=datetime(2025, 1, 1, 5, 0),   # 5 hours
            latest=datetime(2025, 1, 1, 6, 0)      # 6 hours
        )
        
        result = optimizer.optimize_constant_speed(
            distance=120.0,  # Would need 20-24 knots
            departure_time=departure,
            constraint=constraint
        )
        
        assert result['status'] == 'infeasible'
        assert 'exceeds maximum' in result['reason']
    
    def test_optimize_constant_speed_eco_preferred(self):
        """Test that eco speed is preferred when feasible"""
        optimizer = ETAOptimizer(eco_speed=12.0)
        
        departure = datetime(2025, 1, 1, 0, 0)
        constraint = ETAConstraint(
            earliest=datetime(2025, 1, 1, 8, 0),   # 8 hours
            latest=datetime(2025, 1, 1, 15, 0)     # 15 hours
        )
        
        result = optimizer.optimize_constant_speed(
            distance=120.0,  # 12 knots would take 10 hours - within window
            departure_time=departure,
            constraint=constraint
        )
        
        assert result['status'] == 'success'
        assert abs(result['optimal_speed'] - 12.0) < 0.1  # Should choose eco speed
    
    def test_optimize_variable_speed(self):
        """Test variable speed optimization"""
        optimizer = ETAOptimizer()
        
        waypoints = [
            (0.0, 20.0),    # Start
            (50.0, 15.0),   # Waypoint 1
            (100.0, 18.0),  # Waypoint 2
            (150.0, 20.0)   # End
        ]
        
        departure = datetime(2025, 1, 1, 0, 0)
        constraint = ETAConstraint(
            earliest=datetime(2025, 1, 1, 10, 0),
            latest=datetime(2025, 1, 1, 15, 0)
        )
        
        result = optimizer.optimize_variable_speed(
            waypoints=waypoints,
            departure_time=departure,
            constraint=constraint
        )
        
        assert result['status'] == 'success'
        assert len(result['segments']) == 3  # 3 segments for 4 waypoints
        assert len(result['speeds']) == 3
        
        # Check arrival is within window
        arrival = result['arrival_time']
        assert constraint.earliest <= arrival <= constraint.latest
    
    def test_optimize_with_tide_windows(self):
        """Test optimization with tide window constraints"""
        optimizer = ETAOptimizer()
        
        waypoints = [
            (0.0, 20.0),
            (50.0, 10.0),   # Shallow area
            (100.0, 20.0)
        ]
        
        # Need to arrive at waypoint 1 during high tide (hours 4-6)
        tide_windows = [(1, 4.0, 6.0)]
        
        departure = datetime(2025, 1, 1, 0, 0)
        constraint = ETAConstraint(
            earliest=datetime(2025, 1, 1, 8, 0),
            latest=datetime(2025, 1, 1, 12, 0)
        )
        
        result = optimizer.optimize_variable_speed(
            waypoints=waypoints,
            departure_time=departure,
            constraint=constraint,
            tide_windows=tide_windows
        )
        
        assert result['status'] == 'success'
        
        # Calculate arrival at waypoint 1
        if result['segments']:
            arrival_at_wp1 = result['segments'][0].duration
            # Should be within tide window (approximately)
            assert 3.0 <= arrival_at_wp1 <= 7.0
    
    def test_fuel_consumption_factor(self):
        """Test fuel consumption calculation"""
        optimizer = ETAOptimizer(eco_speed=12.0)
        
        # At eco speed, factor should be 1.0
        assert optimizer._fuel_consumption_factor(12.0) == 1.0
        
        # At double eco speed, factor should be 8.0 (2^3)
        assert optimizer._fuel_consumption_factor(24.0) == 8.0
        
        # At half eco speed, factor should be 0.125 (0.5^3)
        assert optimizer._fuel_consumption_factor(6.0) == 0.125
    
    def test_calculate_speed_limits(self):
        """Test speed limit calculation based on depth"""
        optimizer = ETAOptimizer()
        
        # Deep water - full speed range
        min_speed, max_speed = optimizer.calculate_speed_limits(
            depth=50.0,
            draft=10.0,
            min_ukc=2.0
        )
        assert min_speed == optimizer.min_speed
        assert max_speed == optimizer.max_speed
        
        # Shallow water - restricted speed
        min_speed, max_speed = optimizer.calculate_speed_limits(
            depth=12.5,
            draft=10.0,
            min_ukc=2.0
        )
        assert min_speed == optimizer.min_speed
        assert max_speed < optimizer.max_speed
        
        # Too shallow - no safe speed
        min_speed, max_speed = optimizer.calculate_speed_limits(
            depth=11.0,
            draft=10.0,
            min_ukc=2.0
        )
        assert min_speed == 0.0
        assert max_speed == 0.0
    
    def test_generate_speed_profile_report(self):
        """Test speed profile report generation"""
        optimizer = ETAOptimizer()
        
        segments = [
            SpeedSegment(0.0, 50.0, 10.0, 5.0),
            SpeedSegment(50.0, 100.0, 15.0, 3.33),
            SpeedSegment(100.0, 150.0, 12.0, 4.17)
        ]
        
        departure = datetime(2025, 1, 1, 0, 0)
        report = optimizer.generate_speed_profile_report(segments, departure)
        
        assert report['departure_time'] == departure
        assert len(report['segments']) == 3
        assert report['total_distance'] == 150.0
        assert abs(report['total_duration'] - 12.5) < 0.1
        assert abs(report['average_speed'] - 12.0) < 0.1