"""
CPA/TCPA (Closest Point of Approach) Module
Calculates collision risk metrics for vessel encounters.
"""

from typing import Tuple, Optional, List
from dataclasses import dataclass
import numpy as np
import logging

logger = logging.getLogger(__name__)


@dataclass
class VesselState:
    """Vessel kinematic state."""
    x: float  # Position X (meters)
    y: float  # Position Y (meters)  
    speed: float  # Speed (m/s)
    course: float  # Course over ground (radians)
    
    @property
    def velocity(self) -> Tuple[float, float]:
        """Get velocity components."""
        vx = self.speed * np.cos(self.course)
        vy = self.speed * np.sin(self.course)
        return vx, vy


@dataclass
class CPAResult:
    """CPA calculation result."""
    cpa: float  # Closest point of approach distance (meters)
    tcpa: float  # Time to CPA (seconds)
    cpa_position_own: Tuple[float, float]  # Own vessel position at CPA
    cpa_position_target: Tuple[float, float]  # Target vessel position at CPA
    is_collision_risk: bool  # Whether CPA is below threshold


class CPACalculator:
    """Calculates CPA/TCPA between vessels."""
    
    @staticmethod
    def calculate_cpa(own_vessel: VesselState, 
                      target_vessel: VesselState,
                      time_horizon: float = 3600.0) -> CPAResult:
        """
        Calculate CPA and TCPA between two vessels.
        
        Args:
            own_vessel: Own vessel state
            target_vessel: Target vessel state
            time_horizon: Maximum time to consider (seconds)
            
        Returns:
            CPAResult with CPA metrics
        """
        # Get relative position
        dx = target_vessel.x - own_vessel.x
        dy = target_vessel.y - own_vessel.y
        
        # Get relative velocity
        vx_own, vy_own = own_vessel.velocity
        vx_target, vy_target = target_vessel.velocity
        dvx = vx_target - vx_own
        dvy = vy_target - vy_own
        
        # Calculate TCPA using dot product
        dv_squared = dvx**2 + dvy**2
        
        if dv_squared < 1e-6:
            # Vessels have same velocity - constant separation
            cpa = np.hypot(dx, dy)
            tcpa = 0.0
            cpa_pos_own = (own_vessel.x, own_vessel.y)
            cpa_pos_target = (target_vessel.x, target_vessel.y)
        else:
            # Time to CPA
            tcpa = -(dx * dvx + dy * dvy) / dv_squared
            
            # Limit to time horizon
            tcpa = np.clip(tcpa, 0, time_horizon)
            
            # Positions at CPA
            cpa_pos_own = (
                own_vessel.x + vx_own * tcpa,
                own_vessel.y + vy_own * tcpa
            )
            cpa_pos_target = (
                target_vessel.x + vx_target * tcpa,
                target_vessel.y + vy_target * tcpa
            )
            
            # CPA distance
            cpa = np.hypot(
                cpa_pos_target[0] - cpa_pos_own[0],
                cpa_pos_target[1] - cpa_pos_own[1]
            )
        
        # Check collision risk (0.5 NM = 926m typical threshold)
        is_collision_risk = cpa < 926.0 and tcpa > 0
        
        return CPAResult(
            cpa=cpa,
            tcpa=tcpa,
            cpa_position_own=cpa_pos_own,
            cpa_position_target=cpa_pos_target,
            is_collision_risk=is_collision_risk
        )
    
    @staticmethod
    def calculate_multiple_cpa(own_vessel: VesselState,
                              targets: List[VesselState],
                              min_cpa_threshold: float = 926.0) -> List[CPAResult]:
        """
        Calculate CPA with multiple targets.
        
        Args:
            own_vessel: Own vessel state
            targets: List of target vessel states
            min_cpa_threshold: Minimum safe CPA (meters)
            
        Returns:
            List of CPA results
        """
        results = []
        
        for target in targets:
            result = CPACalculator.calculate_cpa(own_vessel, target)
            result.is_collision_risk = result.cpa < min_cpa_threshold
            results.append(result)
        
        return results
    
    @staticmethod
    def create_cpa_cost_field(own_vessel: VesselState,
                             targets: List[VesselState],
                             grid_bounds: Tuple[float, float, float, float],
                             resolution: float = 50.0,
                             time_step: float = 60.0) -> np.ndarray:
        """
        Create cost field based on CPA with traffic.
        
        Args:
            own_vessel: Own vessel state
            targets: Target vessels
            grid_bounds: (minx, miny, maxx, maxy)
            resolution: Grid resolution (meters)
            time_step: Time resolution (seconds)
            
        Returns:
            2D cost array
        """
        minx, miny, maxx, maxy = grid_bounds
        width = int((maxx - minx) / resolution) + 1
        height = int((maxy - miny) / resolution) + 1
        
        cost_field = np.zeros((height, width))
        
        # For each grid point, calculate minimum CPA if vessel were there
        for i in range(height):
            for j in range(width):
                x = minx + j * resolution
                y = miny + i * resolution
                
                # Create hypothetical vessel state at this position
                test_vessel = VesselState(
                    x=x, y=y,
                    speed=own_vessel.speed,
                    course=own_vessel.course
                )
                
                # Calculate CPA with all targets
                min_cpa = float('inf')
                for target in targets:
                    result = CPACalculator.calculate_cpa(test_vessel, target)
                    min_cpa = min(min_cpa, result.cpa)
                
                # Convert CPA to cost (inverse relationship)
                if min_cpa < 100:  # Very close
                    cost_field[i, j] = 10.0
                elif min_cpa < 500:  # Close
                    cost_field[i, j] = 5.0 * (500 - min_cpa) / 400
                elif min_cpa < 1000:  # Moderate
                    cost_field[i, j] = 1.0 * (1000 - min_cpa) / 500
                else:
                    cost_field[i, j] = 0.0
        
        return cost_field