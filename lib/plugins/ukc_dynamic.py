"""
Dynamic UKC (Under Keel Clearance) Calculator
Combines static depth with time-varying water levels and vessel motion
"""

import numpy as np
import pandas as pd
from dataclasses import dataclass
from typing import List, Tuple, Optional, Dict, Any
from datetime import datetime, timedelta
import logging

logger = logging.getLogger(__name__)


@dataclass
class DynamicUKCResult:
    """Result of dynamic UKC evaluation"""
    min_ukc_m: float
    min_ukc_time: datetime
    min_ukc_position: Tuple[float, float]
    violations: int
    violation_segments: List[Dict[str, Any]]
    ukc_timeline: pd.DataFrame
    recommendations: List[str]
    
    def is_safe(self) -> bool:
        """Check if route meets UKC requirements"""
        return self.violations == 0


class UKCDynamic:
    """Dynamic UKC calculator with tide and motion effects"""
    
    def __init__(self,
                 s104_adapter: Optional[Any] = None,
                 s102_adapter: Optional[Any] = None):
        """
        Initialize dynamic UKC calculator.
        
        Args:
            s104_adapter: Water level/tide adapter
            s102_adapter: High-resolution bathymetry adapter
        """
        self.s104_adapter = s104_adapter
        self.s102_adapter = s102_adapter
        
        # Vessel motion parameters
        self.squat_coefficient = 0.01  # Simplified squat model
        self.heel_coefficient = 0.05   # Roll/heel effect
        
        logger.info("Dynamic UKC calculator initialized")
    
    def calculate_dynamic_ukc(self,
                             position: Tuple[float, float],
                             time: datetime,
                             static_depth: float,
                             draft: float,
                             speed: float = 10.0,  # knots
                             wave_height: float = 0.5) -> float:
        """
        Calculate UKC at specific position and time.
        
        Args:
            position: (lon, lat)
            time: Time of calculation
            static_depth: Static water depth (m)
            draft: Vessel draft (m)
            speed: Vessel speed (knots)
            wave_height: Significant wave height (m)
            
        Returns:
            UKC in meters
        """
        # Get water level from tide
        water_level = 0.0
        if self.s104_adapter:
            water_level = self.s104_adapter.get_water_level_at_point(
                position[0], position[1], time
            )
        
        # Calculate squat (increases with speed^2)
        speed_ms = speed * 0.514444  # knots to m/s
        squat = self.squat_coefficient * speed_ms ** 2
        
        # Wave-induced vertical motion
        wave_allowance = 0.5 * wave_height  # Simplified
        
        # Total UKC
        ukc = static_depth + water_level - draft - squat - wave_allowance
        
        return ukc
    
    def evaluate_route_ukc(self,
                          route: List[Tuple[float, float, datetime]],  # [(lon, lat, time), ...]
                          depth_grid: Optional[np.ndarray] = None,
                          lon_grid: Optional[np.ndarray] = None,
                          lat_grid: Optional[np.ndarray] = None,
                          draft: float = 10.0,
                          min_ukc: float = 2.0,
                          speeds: Optional[List[float]] = None,
                          wave_heights: Optional[List[float]] = None) -> DynamicUKCResult:
        """
        Evaluate dynamic UKC along a time-stamped route.
        
        Args:
            route: List of (lon, lat, time) waypoints
            depth_grid: Static depth grid
            lon_grid: Longitude grid
            lat_grid: Latitude grid
            draft: Vessel draft (m)
            min_ukc: Minimum required UKC (m)
            speeds: Speed at each segment (knots)
            wave_heights: Wave height at each position (m)
            
        Returns:
            Dynamic UKC evaluation result
        """
        violations = 0
        violation_segments = []
        ukc_values = []
        min_ukc_value = float('inf')
        min_ukc_time = None
        min_ukc_position = None
        
        # Default speeds and waves if not provided
        if speeds is None:
            speeds = [10.0] * (len(route) - 1)
        if wave_heights is None:
            wave_heights = [0.5] * len(route)
        
        # Evaluate at each waypoint
        for i, (lon, lat, time) in enumerate(route):
            # Get static depth
            static_depth = self._get_static_depth(lon, lat, depth_grid, lon_grid, lat_grid)
            
            # Get speed for this segment
            speed = speeds[min(i, len(speeds) - 1)]
            wave_height = wave_heights[min(i, len(wave_heights) - 1)]
            
            # Calculate dynamic UKC
            ukc = self.calculate_dynamic_ukc(
                position=(lon, lat),
                time=time,
                static_depth=static_depth,
                draft=draft,
                speed=speed,
                wave_height=wave_height
            )
            
            ukc_values.append({
                'time': time,
                'lon': lon,
                'lat': lat,
                'static_depth': static_depth,
                'water_level': self._get_water_level(lon, lat, time),
                'squat': self._calculate_squat(speed),
                'wave_allowance': 0.5 * wave_height,
                'ukc': ukc,
                'speed': speed
            })
            
            # Track minimum
            if ukc < min_ukc_value:
                min_ukc_value = ukc
                min_ukc_time = time
                min_ukc_position = (lon, lat)
            
            # Check for violation
            if ukc < min_ukc:
                violations += 1
                if i > 0:
                    violation_segments.append({
                        'segment': i,
                        'start': route[i-1],
                        'end': (lon, lat, time),
                        'ukc': ukc,
                        'deficit': min_ukc - ukc
                    })
        
        # Create timeline DataFrame
        ukc_timeline = pd.DataFrame(ukc_values)
        
        # Generate recommendations
        recommendations = self._generate_recommendations(
            violations, violation_segments, ukc_timeline, min_ukc
        )
        
        return DynamicUKCResult(
            min_ukc_m=min_ukc_value,
            min_ukc_time=min_ukc_time,
            min_ukc_position=min_ukc_position,
            violations=violations,
            violation_segments=violation_segments,
            ukc_timeline=ukc_timeline,
            recommendations=recommendations
        )
    
    def find_safe_departure_window(self,
                                  route: List[Tuple[float, float]],  # Spatial route
                                  start_time: datetime,
                                  search_hours: float = 24.0,
                                  travel_hours: float = 12.0,
                                  draft: float = 10.0,
                                  min_ukc: float = 2.0) -> List[Tuple[datetime, datetime]]:
        """
        Find departure windows that maintain safe UKC throughout voyage.
        
        Args:
            route: Spatial route [(lon, lat), ...]
            start_time: Start of search period
            search_hours: Hours to search
            travel_hours: Expected voyage duration
            draft: Vessel draft
            min_ukc: Minimum UKC
            
        Returns:
            List of safe departure windows
        """
        safe_windows = []
        
        # Sample departure times
        sample_interval = timedelta(minutes=30)
        n_samples = int(search_hours * 2)  # Every 30 minutes
        
        for i in range(n_samples):
            departure = start_time + i * sample_interval
            
            # Create time-stamped route
            time_stamped_route = self._create_time_stamped_route(
                route, departure, travel_hours
            )
            
            # Evaluate UKC
            result = self.evaluate_route_ukc(
                time_stamped_route,
                draft=draft,
                min_ukc=min_ukc
            )
            
            if result.is_safe():
                # Check if this extends previous window
                if safe_windows and (departure - safe_windows[-1][1]) <= sample_interval:
                    # Extend previous window
                    safe_windows[-1] = (safe_windows[-1][0], departure)
                else:
                    # Start new window
                    safe_windows.append((departure, departure))
        
        return safe_windows
    
    def optimize_speed_for_ukc(self,
                              route: List[Tuple[float, float]],
                              departure_time: datetime,
                              min_speed: float = 5.0,
                              max_speed: float = 20.0,
                              draft: float = 10.0,
                              min_ukc: float = 2.0) -> Dict[str, Any]:
        """
        Optimize speed profile to maintain UKC.
        
        Args:
            route: Spatial route
            departure_time: Departure time
            min_speed: Minimum speed (knots)
            max_speed: Maximum speed (knots)
            draft: Vessel draft
            min_ukc: Minimum UKC
            
        Returns:
            Optimized speed profile
        """
        n_segments = len(route) - 1
        speeds = [10.0] * n_segments  # Start with moderate speed
        
        # Iteratively adjust speeds
        for iteration in range(10):
            # Create time-stamped route with current speeds
            time_stamped_route = []
            current_time = departure_time
            
            for i in range(len(route)):
                time_stamped_route.append((route[i][0], route[i][1], current_time))
                
                if i < n_segments:
                    # Calculate segment transit time
                    distance = self._calculate_distance(route[i], route[i+1])
                    transit_time = distance / speeds[i]
                    current_time += timedelta(hours=transit_time)
            
            # Evaluate UKC
            result = self.evaluate_route_ukc(
                time_stamped_route,
                draft=draft,
                min_ukc=min_ukc,
                speeds=speeds
            )
            
            if result.is_safe():
                break
            
            # Adjust speeds at violation segments
            for violation in result.violation_segments:
                seg_idx = violation['segment'] - 1
                if seg_idx >= 0 and seg_idx < len(speeds):
                    # Reduce speed to reduce squat
                    speeds[seg_idx] = max(min_speed, speeds[seg_idx] * 0.8)
        
        return {
            'speeds': speeds,
            'violations': result.violations,
            'min_ukc': result.min_ukc_m,
            'is_feasible': result.is_safe()
        }
    
    def _get_static_depth(self, lon: float, lat: float,
                         depth_grid: Optional[np.ndarray],
                         lon_grid: Optional[np.ndarray],
                         lat_grid: Optional[np.ndarray]) -> float:
        """Get static depth at position"""
        if depth_grid is None:
            return 20.0  # Default depth
        
        # Simple nearest neighbor interpolation
        if lon_grid is not None and lat_grid is not None:
            # Find nearest grid point
            if lon_grid.ndim == 1 and lat_grid.ndim == 1:
                lon_idx = np.argmin(np.abs(lon_grid - lon))
                lat_idx = np.argmin(np.abs(lat_grid - lat))
                
                if lon_idx < depth_grid.shape[0] and lat_idx < depth_grid.shape[1]:
                    return float(depth_grid[lon_idx, lat_idx])
        
        return 20.0  # Default
    
    def _get_water_level(self, lon: float, lat: float, time: datetime) -> float:
        """Get water level from tide"""
        if self.s104_adapter:
            return self.s104_adapter.get_water_level_at_point(lon, lat, time)
        return 0.0
    
    def _calculate_squat(self, speed: float) -> float:
        """Calculate squat effect"""
        speed_ms = speed * 0.514444
        return self.squat_coefficient * speed_ms ** 2
    
    def _calculate_distance(self, pos1: Tuple[float, float], 
                           pos2: Tuple[float, float]) -> float:
        """Calculate distance between positions in nm"""
        # Simplified distance calculation
        dx = (pos2[0] - pos1[0]) * 60 * np.cos(np.radians((pos1[1] + pos2[1]) / 2))
        dy = (pos2[1] - pos1[1]) * 60
        return np.sqrt(dx**2 + dy**2)
    
    def _create_time_stamped_route(self,
                                  route: List[Tuple[float, float]],
                                  departure: datetime,
                                  total_hours: float) -> List[Tuple[float, float, datetime]]:
        """Create time-stamped route with uniform speed"""
        time_stamped = []
        n_segments = len(route) - 1
        
        if n_segments <= 0:
            return [(route[0][0], route[0][1], departure)]
        
        segment_hours = total_hours / n_segments
        current_time = departure
        
        for lon, lat in route:
            time_stamped.append((lon, lat, current_time))
            current_time += timedelta(hours=segment_hours)
        
        return time_stamped
    
    def _generate_recommendations(self,
                                 violations: int,
                                 violation_segments: List[Dict],
                                 ukc_timeline: pd.DataFrame,
                                 min_ukc: float) -> List[str]:
        """Generate recommendations based on UKC analysis"""
        recommendations = []
        
        if violations == 0:
            recommendations.append("Route maintains safe UKC throughout voyage")
            
            # Check margin
            if ukc_timeline['ukc'].min() < min_ukc * 1.5:
                recommendations.append(f"Warning: UKC margin is less than 50% above minimum")
        else:
            recommendations.append(f"Route has {violations} UKC violations")
            
            # Analyze violations
            max_deficit = max(v['deficit'] for v in violation_segments) if violation_segments else 0
            
            if max_deficit > 2.0:
                recommendations.append("Consider alternative route - significant UKC deficit")
            elif max_deficit > 1.0:
                recommendations.append("Adjust departure time to utilize higher tide")
            else:
                recommendations.append("Reduce speed in shallow areas to minimize squat")
            
            # Check if violations are clustered
            if len(violation_segments) > 1:
                segments = [v['segment'] for v in violation_segments]
                if max(segments) - min(segments) <= 2:
                    recommendations.append("Violations concentrated in single area - consider local rerouting")
        
        # Speed recommendations
        if 'speed' in ukc_timeline.columns:
            avg_speed = ukc_timeline['speed'].mean()
            if avg_speed > 15:
                recommendations.append("Consider reducing speed to improve UKC margins")
        
        return recommendations