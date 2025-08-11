"""
ETA Window Optimizer
Optimizes speed profiles to meet arrival time windows
"""

import numpy as np
from dataclasses import dataclass
from typing import List, Tuple, Optional, Dict, Any
from datetime import datetime, timedelta
import logging

logger = logging.getLogger(__name__)


@dataclass
class SpeedSegment:
    """Speed profile segment"""
    start_pos: float  # Nautical miles from start
    end_pos: float
    speed: float  # Knots
    duration: float  # Hours
    
    @property
    def distance(self) -> float:
        """Distance covered in this segment"""
        return self.end_pos - self.start_pos


@dataclass
class ETAConstraint:
    """Arrival time constraint"""
    earliest: datetime
    latest: datetime
    penalty_early: float = 10.0  # Cost per hour early
    penalty_late: float = 50.0   # Cost per hour late
    
    def evaluate(self, arrival_time: datetime) -> float:
        """Calculate penalty for given arrival time"""
        if arrival_time < self.earliest:
            hours_early = (self.earliest - arrival_time).total_seconds() / 3600
            return hours_early * self.penalty_early
        elif arrival_time > self.latest:
            hours_late = (arrival_time - self.latest).total_seconds() / 3600
            return hours_late * self.penalty_late
        else:
            return 0.0  # Within window


class ETAOptimizer:
    """Optimizes vessel speed to meet ETA constraints"""
    
    def __init__(self,
                 min_speed: float = 5.0,   # knots
                 max_speed: float = 20.0,   # knots
                 eco_speed: float = 12.0):  # knots
        """
        Initialize ETA optimizer.
        
        Args:
            min_speed: Minimum vessel speed
            max_speed: Maximum vessel speed
            eco_speed: Economic/preferred speed
        """
        self.min_speed = min_speed
        self.max_speed = max_speed
        self.eco_speed = eco_speed
        
        logger.info(f"ETA Optimizer initialized: speeds {min_speed}-{max_speed} kts, eco {eco_speed} kts")
    
    def optimize_constant_speed(self,
                               distance: float,  # nautical miles
                               departure_time: datetime,
                               constraint: ETAConstraint) -> Dict[str, Any]:
        """
        Find optimal constant speed to meet ETA window.
        
        Args:
            distance: Total distance to cover
            departure_time: Departure time
            constraint: Arrival time constraint
            
        Returns:
            Optimization result
        """
        # Calculate required speeds for earliest and latest arrival
        earliest_duration = (constraint.earliest - departure_time).total_seconds() / 3600
        latest_duration = (constraint.latest - departure_time).total_seconds() / 3600
        
        if earliest_duration <= 0:
            return {
                'status': 'infeasible',
                'reason': 'Earliest arrival is before departure'
            }
        
        speed_for_earliest = distance / earliest_duration if earliest_duration > 0 else float('inf')
        speed_for_latest = distance / latest_duration if latest_duration > 0 else float('inf')
        
        # Check feasibility
        if speed_for_latest > self.max_speed:
            return {
                'status': 'infeasible',
                'reason': f'Required speed {speed_for_latest:.1f} exceeds maximum {self.max_speed}'
            }
        
        if speed_for_earliest < self.min_speed:
            return {
                'status': 'infeasible',
                'reason': f'Required speed {speed_for_earliest:.1f} below minimum {self.min_speed}'
            }
        
        # Find optimal speed (prefer eco speed if within window)
        if speed_for_latest <= self.eco_speed <= speed_for_earliest:
            optimal_speed = self.eco_speed
        else:
            # Use speed closest to eco that meets constraint
            if self.eco_speed < speed_for_latest:
                optimal_speed = speed_for_latest
            elif self.eco_speed > speed_for_earliest:
                optimal_speed = speed_for_earliest
            else:
                optimal_speed = self.eco_speed
        
        # Ensure within limits
        optimal_speed = max(self.min_speed, min(self.max_speed, optimal_speed))
        
        # Calculate arrival
        duration = distance / optimal_speed
        arrival_time = departure_time + timedelta(hours=duration)
        
        return {
            'status': 'success',
            'optimal_speed': optimal_speed,
            'duration_hours': duration,
            'arrival_time': arrival_time,
            'penalty': constraint.evaluate(arrival_time),
            'fuel_factor': self._fuel_consumption_factor(optimal_speed)
        }
    
    def optimize_variable_speed(self,
                              waypoints: List[Tuple[float, float]],  # [(distance, min_depth), ...]
                              departure_time: datetime,
                              constraint: ETAConstraint,
                              tide_windows: Optional[List[Tuple[int, float, float]]] = None) -> Dict[str, Any]:
        """
        Optimize variable speed profile along route.
        
        Args:
            waypoints: List of (distance_nm, min_depth_m) tuples
            departure_time: Departure time
            constraint: Arrival time constraint
            tide_windows: Optional list of (waypoint_idx, start_hours, end_hours) for tide constraints
            
        Returns:
            Optimization result with speed profile
        """
        n_segments = len(waypoints) - 1
        if n_segments <= 0:
            return {'status': 'error', 'reason': 'Need at least 2 waypoints'}
        
        # Initialize with eco speed
        speeds = [self.eco_speed] * n_segments
        segments = []
        
        # First pass: adjust for tide windows if provided
        if tide_windows:
            speeds = self._adjust_for_tide_windows(waypoints, speeds, tide_windows, departure_time)
        
        # Second pass: adjust to meet ETA constraint
        total_distance = waypoints[-1][0]
        
        # Calculate current ETA
        current_time = departure_time
        for i in range(n_segments):
            dist = waypoints[i+1][0] - waypoints[i][0]
            duration = dist / speeds[i]
            current_time += timedelta(hours=duration)
        
        # Adjust speeds to meet constraint
        if current_time < constraint.earliest:
            # Too early - slow down
            scale_factor = (current_time - departure_time).total_seconds() / (constraint.earliest - departure_time).total_seconds()
            speeds = [max(self.min_speed, s * scale_factor) for s in speeds]
        elif current_time > constraint.latest:
            # Too late - speed up
            scale_factor = (current_time - departure_time).total_seconds() / (constraint.latest - departure_time).total_seconds()
            speeds = [min(self.max_speed, s * scale_factor) for s in speeds]
        
        # Build segments
        current_pos = 0.0
        current_time = departure_time
        
        for i in range(n_segments):
            dist = waypoints[i+1][0] - waypoints[i][0]
            duration = dist / speeds[i]
            
            segment = SpeedSegment(
                start_pos=waypoints[i][0],
                end_pos=waypoints[i+1][0],
                speed=speeds[i],
                duration=duration
            )
            segments.append(segment)
            
            current_time += timedelta(hours=duration)
        
        return {
            'status': 'success',
            'segments': segments,
            'speeds': speeds,
            'arrival_time': current_time,
            'penalty': constraint.evaluate(current_time),
            'total_fuel_factor': np.mean([self._fuel_consumption_factor(s) for s in speeds])
        }
    
    def _adjust_for_tide_windows(self,
                                waypoints: List[Tuple[float, float]],
                                speeds: List[float],
                                tide_windows: List[Tuple[int, float, float]],
                                departure_time: datetime) -> List[float]:
        """Adjust speeds to hit tide windows"""
        adjusted_speeds = speeds.copy()
        
        for wp_idx, start_hours, end_hours in tide_windows:
            if wp_idx >= len(waypoints):
                continue
            
            # Calculate when we would arrive at this waypoint
            arrival_hours = 0.0
            for i in range(wp_idx):
                if i < len(waypoints) - 1:
                    dist = waypoints[i+1][0] - waypoints[i][0]
                    arrival_hours += dist / adjusted_speeds[i]
            
            # Check if we're within window
            if arrival_hours < start_hours:
                # Too early - slow down previous segment
                if wp_idx > 0:
                    factor = start_hours / arrival_hours if arrival_hours > 0 else 1.0
                    for i in range(wp_idx):
                        adjusted_speeds[i] = max(self.min_speed, adjusted_speeds[i] / factor)
            elif arrival_hours > end_hours:
                # Too late - speed up previous segments
                if wp_idx > 0:
                    factor = end_hours / arrival_hours if arrival_hours > 0 else 1.0
                    for i in range(wp_idx):
                        adjusted_speeds[i] = min(self.max_speed, adjusted_speeds[i] / factor)
        
        return adjusted_speeds
    
    def _fuel_consumption_factor(self, speed: float) -> float:
        """
        Estimate fuel consumption factor (simplified cubic law).
        
        Args:
            speed: Speed in knots
            
        Returns:
            Relative fuel consumption (1.0 at eco speed)
        """
        # Simplified: fuel consumption proportional to speed^3
        return (speed / self.eco_speed) ** 3
    
    def calculate_speed_limits(self,
                             depth: float,
                             draft: float,
                             min_ukc: float = 2.0) -> Tuple[float, float]:
        """
        Calculate speed limits based on water depth (squat effect).
        
        Args:
            depth: Water depth (m)
            draft: Vessel draft (m)
            min_ukc: Minimum UKC required (m)
            
        Returns:
            (min_safe_speed, max_safe_speed) in knots
        """
        ukc = depth - draft
        
        if ukc < min_ukc:
            # Too shallow - no safe speed
            return 0.0, 0.0
        
        # Simplified squat calculation
        # Squat increases with speed^2
        max_squat = ukc - min_ukc
        
        if max_squat <= 0:
            return self.min_speed, self.min_speed
        
        # Max speed where squat = max_squat
        # squat ≈ C * V^2 where C is a coefficient (~0.01 for cargo ships)
        squat_coeff = 0.01
        max_safe_speed = np.sqrt(max_squat / squat_coeff) * 1.944  # m/s to knots
        
        return self.min_speed, min(self.max_speed, max_safe_speed)
    
    def generate_speed_profile_report(self,
                                     segments: List[SpeedSegment],
                                     departure_time: datetime) -> Dict[str, Any]:
        """
        Generate detailed speed profile report.
        
        Args:
            segments: Speed profile segments
            departure_time: Departure time
            
        Returns:
            Detailed report
        """
        report = {
            'departure_time': departure_time,
            'segments': [],
            'total_distance': 0.0,
            'total_duration': 0.0,
            'average_speed': 0.0,
            'fuel_consumption': 0.0
        }
        
        current_time = departure_time
        
        for i, seg in enumerate(segments):
            seg_report = {
                'segment': i + 1,
                'start_pos': seg.start_pos,
                'end_pos': seg.end_pos,
                'distance': seg.distance,
                'speed': seg.speed,
                'duration': seg.duration,
                'start_time': current_time,
                'end_time': current_time + timedelta(hours=seg.duration),
                'fuel_factor': self._fuel_consumption_factor(seg.speed)
            }
            
            report['segments'].append(seg_report)
            report['total_distance'] += seg.distance
            report['total_duration'] += seg.duration
            report['fuel_consumption'] += seg.duration * self._fuel_consumption_factor(seg.speed)
            
            current_time += timedelta(hours=seg.duration)
        
        report['arrival_time'] = current_time
        report['average_speed'] = report['total_distance'] / report['total_duration'] if report['total_duration'] > 0 else 0
        
        return report