"""
Safety Shield with Control Barrier Functions (CBF)
Provides real-time safety guarantees through control constraints
"""

import numpy as np
from dataclasses import dataclass
from typing import List, Tuple, Optional, Dict, Any
from datetime import datetime
import logging
import time

logger = logging.getLogger(__name__)


@dataclass
class SafetyConstraint:
    """Safety constraint definition"""
    name: str
    type: str  # 'collision', 'grounding', 'speed', 'acceleration'
    threshold: float
    margin: float
    priority: int  # Higher number = higher priority
    
    def evaluate(self, state: Dict[str, Any]) -> float:
        """Evaluate constraint satisfaction (positive = safe)"""
        if self.type == 'collision':
            return self._evaluate_collision(state)
        elif self.type == 'grounding':
            return self._evaluate_grounding(state)
        elif self.type == 'speed':
            return self._evaluate_speed(state)
        elif self.type == 'acceleration':
            return self._evaluate_acceleration(state)
        else:
            return float('inf')
    
    def _evaluate_collision(self, state: Dict[str, Any]) -> float:
        """Evaluate collision constraint"""
        min_distance = state.get('min_distance_to_obstacle', float('inf'))
        return min_distance - self.threshold
    
    def _evaluate_grounding(self, state: Dict[str, Any]) -> float:
        """Evaluate grounding constraint"""
        ukc = state.get('ukc', float('inf'))
        return ukc - self.threshold
    
    def _evaluate_speed(self, state: Dict[str, Any]) -> float:
        """Evaluate speed constraint"""
        speed = state.get('speed', 0.0)
        max_speed = state.get('max_safe_speed', self.threshold)
        return max_speed - speed
    
    def _evaluate_acceleration(self, state: Dict[str, Any]) -> float:
        """Evaluate acceleration constraint"""
        accel = state.get('acceleration', 0.0)
        return self.threshold - abs(accel)


@dataclass
class ControlAction:
    """Control action to be applied"""
    rudder_angle: float  # degrees
    engine_command: float  # -1 to 1 (astern to ahead)
    timestamp: datetime
    source: str  # 'nominal', 'cbf', 'emergency'
    confidence: float


class SafetyShield:
    """Control Barrier Function based safety shield"""
    
    def __init__(self,
                 max_response_time_ms: float = 100,
                 min_safety_margin: float = 0.1):
        """
        Initialize safety shield.
        
        Args:
            max_response_time_ms: Maximum response time in milliseconds
            min_safety_margin: Minimum safety margin for all constraints
        """
        self.max_response_time_ms = max_response_time_ms
        self.min_safety_margin = min_safety_margin
        self.constraints: List[SafetyConstraint] = []
        self.emergency_actions: List[ControlAction] = []
        self.performance_stats = {
            'interventions': 0,
            'avg_response_ms': 0,
            'constraint_violations': 0
        }
        
        logger.info(f"Safety shield initialized with {max_response_time_ms}ms response time")
    
    def add_constraint(self, constraint: SafetyConstraint):
        """Add safety constraint"""
        self.constraints.append(constraint)
        self.constraints.sort(key=lambda c: c.priority, reverse=True)
        logger.info(f"Added constraint: {constraint.name} (priority {constraint.priority})")
    
    def filter_control(self,
                      nominal_action: ControlAction,
                      vessel_state: Dict[str, Any]) -> ControlAction:
        """
        Filter control action through safety constraints.
        
        Args:
            nominal_action: Proposed control action
            vessel_state: Current vessel state
            
        Returns:
            Safe control action (possibly modified)
        """
        start_time = time.time()
        
        # Check all constraints
        violations = []
        for constraint in self.constraints:
            h = constraint.evaluate(vessel_state)
            if h < constraint.margin:
                violations.append((constraint, h))
        
        # If no violations, return nominal action
        if not violations:
            self._update_stats(start_time, False)
            return nominal_action
        
        # Compute safe control action using CBF
        safe_action = self._compute_safe_control(
            nominal_action, vessel_state, violations
        )
        
        # Log intervention
        logger.warning(f"Safety intervention: {len(violations)} constraints violated")
        self.performance_stats['interventions'] += 1
        self.performance_stats['constraint_violations'] += len(violations)
        
        self._update_stats(start_time, True)
        return safe_action
    
    def _compute_safe_control(self,
                             nominal: ControlAction,
                             state: Dict[str, Any],
                             violations: List[Tuple[SafetyConstraint, float]]) -> ControlAction:
        """
        Compute safe control using Control Barrier Functions.
        
        This is a simplified QP solver for demonstration.
        In production, use cvxpy or similar.
        """
        # Start with nominal action
        safe_rudder = nominal.rudder_angle
        safe_engine = nominal.engine_command
        
        # Apply corrections for each violation
        for constraint, h_value in violations:
            if constraint.type == 'collision':
                # Turn away from obstacle
                bearing_to_obstacle = state.get('obstacle_bearing', 0)
                if abs(bearing_to_obstacle) < 90:
                    # Obstacle ahead - turn away
                    safe_rudder = 35.0 if bearing_to_obstacle > 0 else -35.0
                    safe_engine = min(safe_engine, 0.5)  # Reduce speed
                    
            elif constraint.type == 'grounding':
                # Emergency stop or reverse
                if h_value < 0:  # Already grounding
                    safe_engine = -1.0  # Full astern
                else:
                    safe_engine = min(safe_engine, 0.0)  # Stop engines
                    
            elif constraint.type == 'speed':
                # Reduce engine command
                speed_ratio = state.get('speed', 0) / constraint.threshold
                if speed_ratio > 1.0:
                    safe_engine = safe_engine / speed_ratio
                    
            elif constraint.type == 'acceleration':
                # Limit rate of change
                safe_engine = np.clip(
                    safe_engine,
                    state.get('current_engine', 0) - 0.1,
                    state.get('current_engine', 0) + 0.1
                )
        
        return ControlAction(
            rudder_angle=np.clip(safe_rudder, -35.0, 35.0),
            engine_command=np.clip(safe_engine, -1.0, 1.0),
            timestamp=datetime.now(),
            source='cbf',
            confidence=0.9
        )
    
    def emergency_stop(self, state: Dict[str, Any]) -> ControlAction:
        """Generate emergency stop action"""
        action = ControlAction(
            rudder_angle=0.0,
            engine_command=-1.0,  # Full astern
            timestamp=datetime.now(),
            source='emergency',
            confidence=1.0
        )
        
        self.emergency_actions.append(action)
        logger.critical("EMERGENCY STOP initiated")
        return action
    
    def evaluate_safety_level(self, state: Dict[str, Any]) -> Dict[str, Any]:
        """
        Evaluate overall safety level.
        
        Returns:
            Safety assessment with constraint margins
        """
        margins = {}
        min_margin = float('inf')
        critical_constraint = None
        
        for constraint in self.constraints:
            h = constraint.evaluate(state)
            margins[constraint.name] = h
            
            if h < min_margin:
                min_margin = h
                critical_constraint = constraint.name
        
        # Determine safety level
        if min_margin < 0:
            safety_level = 'CRITICAL'
        elif min_margin < self.min_safety_margin:
            safety_level = 'WARNING'
        elif min_margin < self.min_safety_margin * 2:
            safety_level = 'CAUTION'
        else:
            safety_level = 'SAFE'
        
        return {
            'level': safety_level,
            'min_margin': min_margin,
            'critical_constraint': critical_constraint,
            'margins': margins,
            'timestamp': datetime.now()
        }
    
    def _update_stats(self, start_time: float, intervention: bool):
        """Update performance statistics"""
        response_ms = (time.time() - start_time) * 1000
        
        # Update rolling average
        alpha = 0.1  # Exponential smoothing factor
        self.performance_stats['avg_response_ms'] = (
            alpha * response_ms + 
            (1 - alpha) * self.performance_stats['avg_response_ms']
        )
        
        if response_ms > self.max_response_time_ms:
            logger.warning(f"Response time {response_ms:.1f}ms exceeds limit")
    
    def get_statistics(self) -> Dict[str, Any]:
        """Get safety shield statistics"""
        return {
            'interventions': self.performance_stats['interventions'],
            'avg_response_ms': self.performance_stats['avg_response_ms'],
            'constraint_violations': self.performance_stats['constraint_violations'],
            'emergency_stops': len(self.emergency_actions),
            'active_constraints': len(self.constraints)
        }


class AdaptiveSafetyShield(SafetyShield):
    """Adaptive safety shield that learns from interventions"""
    
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.intervention_history = []
        self.adaptation_enabled = True
        self.learning_rate = 0.01
    
    def filter_control(self,
                      nominal_action: ControlAction,
                      vessel_state: Dict[str, Any]) -> ControlAction:
        """Filter with adaptation"""
        # Get base safe action
        safe_action = super().filter_control(nominal_action, vessel_state)
        
        # Record if intervention occurred
        if safe_action.source == 'cbf':
            self.intervention_history.append({
                'state': vessel_state.copy(),
                'nominal': nominal_action,
                'safe': safe_action,
                'timestamp': datetime.now()
            })
            
            # Adapt constraints if enabled
            if self.adaptation_enabled:
                self._adapt_constraints(vessel_state)
        
        return safe_action
    
    def _adapt_constraints(self, state: Dict[str, Any]):
        """Adapt constraint parameters based on history"""
        if len(self.intervention_history) < 10:
            return  # Need more data
        
        # Analyze recent interventions
        recent = self.intervention_history[-10:]
        
        # Find frequently violated constraints
        violation_counts = {}
        for record in recent:
            for constraint in self.constraints:
                h = constraint.evaluate(record['state'])
                if h < constraint.margin:
                    violation_counts[constraint.name] = violation_counts.get(constraint.name, 0) + 1
        
        # Adapt margins for frequently violated constraints
        for constraint in self.constraints:
            if constraint.name in violation_counts:
                violation_rate = violation_counts[constraint.name] / len(recent)
                if violation_rate > 0.3:  # More than 30% violations
                    # Increase safety margin
                    constraint.margin *= (1 + self.learning_rate)
                    logger.info(f"Adapted {constraint.name} margin to {constraint.margin:.3f}")
    
    def reset_adaptation(self):
        """Reset adaptation history"""
        self.intervention_history.clear()
        logger.info("Adaptation history reset")