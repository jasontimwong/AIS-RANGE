"""
Tests for Safety Shield with Control Barrier Functions
"""

import pytest
import numpy as np
from datetime import datetime
import sys
import os

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from lib.safety.safety_shield import (
    SafetyConstraint,
    ControlAction,
    SafetyShield,
    AdaptiveSafetyShield
)


class TestSafetyConstraint:
    """Test SafetyConstraint class"""
    
    def test_collision_constraint(self):
        """Test collision constraint evaluation"""
        constraint = SafetyConstraint(
            name="collision_avoidance",
            type="collision",
            threshold=1.0,  # 1 nm minimum distance
            margin=0.2,
            priority=10
        )
        
        # Safe state
        state = {'min_distance_to_obstacle': 2.0}
        assert constraint.evaluate(state) > 0
        
        # Dangerous state
        state = {'min_distance_to_obstacle': 0.5}
        assert constraint.evaluate(state) < 0
    
    def test_grounding_constraint(self):
        """Test grounding constraint evaluation"""
        constraint = SafetyConstraint(
            name="grounding_prevention",
            type="grounding",
            threshold=2.0,  # 2m minimum UKC
            margin=0.5,
            priority=10
        )
        
        # Safe UKC
        state = {'ukc': 5.0}
        assert constraint.evaluate(state) > 0
        
        # Dangerous UKC
        state = {'ukc': 1.0}
        assert constraint.evaluate(state) < 0
    
    def test_speed_constraint(self):
        """Test speed constraint evaluation"""
        constraint = SafetyConstraint(
            name="speed_limit",
            type="speed",
            threshold=20.0,  # 20 knots max
            margin=2.0,
            priority=5
        )
        
        # Within limit
        state = {'speed': 15.0, 'max_safe_speed': 20.0}
        assert constraint.evaluate(state) > 0
        
        # Exceeding limit
        state = {'speed': 22.0, 'max_safe_speed': 20.0}
        assert constraint.evaluate(state) < 0


class TestControlAction:
    """Test ControlAction class"""
    
    def test_action_creation(self):
        """Test creating control action"""
        action = ControlAction(
            rudder_angle=10.0,
            engine_command=0.7,
            timestamp=datetime.now(),
            source='nominal',
            confidence=0.95
        )
        
        assert action.rudder_angle == 10.0
        assert action.engine_command == 0.7
        assert action.source == 'nominal'
        assert action.confidence == 0.95


class TestSafetyShield:
    """Test SafetyShield class"""
    
    def test_initialization(self):
        """Test safety shield initialization"""
        shield = SafetyShield(max_response_time_ms=50)
        
        assert shield.max_response_time_ms == 50
        assert shield.min_safety_margin == 0.1
        assert len(shield.constraints) == 0
    
    def test_add_constraint(self):
        """Test adding constraints"""
        shield = SafetyShield()
        
        constraint1 = SafetyConstraint("c1", "collision", 1.0, 0.2, 10)
        constraint2 = SafetyConstraint("c2", "speed", 20.0, 2.0, 5)
        
        shield.add_constraint(constraint1)
        shield.add_constraint(constraint2)
        
        assert len(shield.constraints) == 2
        # Higher priority should be first
        assert shield.constraints[0].priority == 10
    
    def test_filter_safe_control(self):
        """Test filtering when control is safe"""
        shield = SafetyShield()
        
        # Add constraint
        constraint = SafetyConstraint(
            name="collision",
            type="collision",
            threshold=1.0,
            margin=0.2,
            priority=10
        )
        shield.add_constraint(constraint)
        
        # Safe state
        state = {'min_distance_to_obstacle': 5.0}
        
        # Nominal action
        nominal = ControlAction(
            rudder_angle=5.0,
            engine_command=0.8,
            timestamp=datetime.now(),
            source='nominal',
            confidence=0.9
        )
        
        # Should return nominal action unchanged
        filtered = shield.filter_control(nominal, state)
        assert filtered.rudder_angle == nominal.rudder_angle
        assert filtered.engine_command == nominal.engine_command
        assert filtered.source == 'nominal'
    
    def test_filter_unsafe_control(self):
        """Test filtering when control is unsafe"""
        shield = SafetyShield()
        
        # Add collision constraint
        constraint = SafetyConstraint(
            name="collision",
            type="collision",
            threshold=1.0,
            margin=0.2,
            priority=10
        )
        shield.add_constraint(constraint)
        
        # Dangerous state - obstacle very close
        state = {
            'min_distance_to_obstacle': 0.5,
            'obstacle_bearing': 10,  # Slightly to starboard
            'current_engine': 0.8
        }
        
        # Nominal action (would continue toward obstacle)
        nominal = ControlAction(
            rudder_angle=0.0,
            engine_command=0.8,
            timestamp=datetime.now(),
            source='nominal',
            confidence=0.9
        )
        
        # Should modify action to avoid
        filtered = shield.filter_control(nominal, state)
        assert filtered.source == 'cbf'
        # Should turn away - either port or starboard based on obstacle bearing
        # Since obstacle is at +10 degrees (starboard), should turn to port (negative) or hard starboard
        assert abs(filtered.rudder_angle) > 0  # Should turn, direction depends on algorithm
        # Should reduce speed
        assert filtered.engine_command <= nominal.engine_command
    
    def test_emergency_stop(self):
        """Test emergency stop generation"""
        shield = SafetyShield()
        
        state = {'emergency': True}
        action = shield.emergency_stop(state)
        
        assert action.rudder_angle == 0.0
        assert action.engine_command == -1.0  # Full astern
        assert action.source == 'emergency'
        assert len(shield.emergency_actions) == 1
    
    def test_evaluate_safety_level(self):
        """Test safety level evaluation"""
        shield = SafetyShield()
        
        # Add multiple constraints
        shield.add_constraint(SafetyConstraint("c1", "collision", 1.0, 0.2, 10))
        shield.add_constraint(SafetyConstraint("c2", "grounding", 2.0, 0.5, 9))
        
        # Safe state
        state = {
            'min_distance_to_obstacle': 5.0,
            'ukc': 10.0
        }
        
        assessment = shield.evaluate_safety_level(state)
        assert assessment['level'] == 'SAFE'
        assert assessment['min_margin'] > 0
        
        # Critical state
        state = {
            'min_distance_to_obstacle': 0.5,
            'ukc': 1.0
        }
        
        assessment = shield.evaluate_safety_level(state)
        assert assessment['level'] == 'CRITICAL'
        assert assessment['min_margin'] < 0
    
    def test_statistics(self):
        """Test statistics tracking"""
        shield = SafetyShield()
        
        stats = shield.get_statistics()
        assert stats['interventions'] == 0
        assert stats['emergency_stops'] == 0
        assert stats['active_constraints'] == 0


class TestAdaptiveSafetyShield:
    """Test AdaptiveSafetyShield class"""
    
    def test_adaptation(self):
        """Test constraint adaptation"""
        shield = AdaptiveSafetyShield()
        
        # Add constraint with small margin
        constraint = SafetyConstraint(
            name="collision",
            type="collision",
            threshold=1.0,
            margin=0.1,
            priority=10
        )
        shield.add_constraint(constraint)
        
        # Simulate multiple interventions
        for _ in range(15):
            state = {
                'min_distance_to_obstacle': 0.05,  # Very close
                'obstacle_bearing': 0,
                'current_engine': 0.5
            }
            
            nominal = ControlAction(
                rudder_angle=0.0,
                engine_command=0.8,
                timestamp=datetime.now(),
                source='nominal',
                confidence=0.9
            )
            
            shield.filter_control(nominal, state)
        
        # Check that margin was adapted
        assert len(shield.intervention_history) == 15
        # Margin should have increased
        assert shield.constraints[0].margin > 0.1
    
    def test_reset_adaptation(self):
        """Test resetting adaptation history"""
        shield = AdaptiveSafetyShield()
        
        # Add some history
        shield.intervention_history = [{'test': 1}, {'test': 2}]
        
        shield.reset_adaptation()
        assert len(shield.intervention_history) == 0