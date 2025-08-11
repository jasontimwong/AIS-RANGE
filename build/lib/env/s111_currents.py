"""
S-111 Surface Currents Integration
Handles time-varying ocean current data for route planning
"""

import csv
import datetime as dt
import numpy as np
from typing import List, Tuple, Dict, Any
from dataclasses import dataclass
import logging

logger = logging.getLogger(__name__)


@dataclass
class CurrentSample:
    """Single current measurement"""
    time: dt.datetime
    lon: float
    lat: float
    u_ms: float  # East component (m/s)
    v_ms: float  # North component (m/s)


@dataclass
class CurrentField:
    """Collection of current samples"""
    samples: List[CurrentSample]
    
    def get_time_range(self) -> Tuple[dt.datetime, dt.datetime]:
        """Get temporal coverage of current data"""
        times = [s.time for s in self.samples]
        return min(times), max(times)
    
    def get_spatial_bounds(self) -> Tuple[float, float, float, float]:
        """Get spatial bounds (min_lon, min_lat, max_lon, max_lat)"""
        lons = [s.lon for s in self.samples]
        lats = [s.lat for s in self.samples]
        return min(lons), min(lats), max(lons), max(lats)


def load_s111_csv(path: str) -> CurrentField:
    """
    Load S-111 current data from CSV.
    
    Args:
        path: Path to CSV with columns: time_iso, lon, lat, u_ms, v_ms
        
    Returns:
        CurrentField object containing all samples
    """
    samples = []
    
    with open(path, 'r', encoding='utf-8') as f:
        reader = csv.reader(f)
        for line in reader:
            # Skip comments and empty lines
            if not line or line[0].startswith('#'):
                continue
            
            time_str, lon, lat, u, v = line
            
            # Parse ISO time
            time_obj = dt.datetime.fromisoformat(time_str.replace('Z', '+00:00'))
            
            sample = CurrentSample(
                time=time_obj,
                lon=float(lon),
                lat=float(lat),
                u_ms=float(u),
                v_ms=float(v)
            )
            samples.append(sample)
    
    field = CurrentField(samples=samples)
    
    logger.info(f"Loaded S-111 currents: {len(samples)} samples, "
                f"time=[{field.get_time_range()[0]}, {field.get_time_range()[1]}]")
    
    return field


def sample_current(cur: CurrentField, lon: float, lat: float, when: dt.datetime) -> Tuple[float, float]:
    """
    Sample current at specific location and time.
    
    Args:
        cur: Current field data
        lon: Longitude to sample
        lat: Latitude to sample
        when: Time to sample
        
    Returns:
        Tuple of (u_ms, v_ms) current components
    """
    # Simple nearest neighbor for now
    # In production, use spatial/temporal interpolation
    
    best_sample = None
    best_dist = float('inf')
    
    for sample in cur.samples:
        # Spatial distance (simplified)
        spatial_dist = np.sqrt((sample.lon - lon)**2 + (sample.lat - lat)**2)
        
        # Temporal distance in hours
        time_dist = abs((sample.time - when).total_seconds()) / 3600
        
        # Combined distance (weighted)
        combined_dist = spatial_dist + time_dist * 0.01  # Adjust weights as needed
        
        if combined_dist < best_dist:
            best_dist = combined_dist
            best_sample = sample
    
    if best_sample:
        return best_sample.u_ms, best_sample.v_ms
    else:
        return 0.0, 0.0  # No current if no data


def effective_speed_ms(base_speed_ms: float, u_ms: float, v_ms: float, heading_rad: float) -> float:
    """
    Calculate effective ground speed considering current.
    
    Args:
        base_speed_ms: Ship's speed through water (m/s)
        u_ms: Current east component (m/s)
        v_ms: Current north component (m/s)
        heading_rad: Ship's heading in radians (0 = north, π/2 = east)
        
    Returns:
        Effective ground speed (m/s)
    """
    # Ship velocity components
    ship_u = base_speed_ms * np.sin(heading_rad)  # East
    ship_v = base_speed_ms * np.cos(heading_rad)  # North
    
    # Ground velocity = ship velocity + current
    ground_u = ship_u + u_ms
    ground_v = ship_v + v_ms
    
    # Magnitude of ground velocity
    ground_speed = np.sqrt(ground_u**2 + ground_v**2)
    
    return ground_speed


def travel_time_s(dist_m: float, base_speed_ms: float, u_ms: float, v_ms: float, heading_rad: float) -> float:
    """
    Calculate travel time considering current.
    
    Args:
        dist_m: Distance to travel (m)
        base_speed_ms: Ship's speed through water (m/s)
        u_ms: Current east component (m/s)
        v_ms: Current north component (m/s)
        heading_rad: Ship's heading in radians
        
    Returns:
        Travel time in seconds
    """
    effective_speed = effective_speed_ms(base_speed_ms, u_ms, v_ms, heading_rad)
    
    if effective_speed <= 0:
        # Can't make progress against current
        return float('inf')
    
    return dist_m / effective_speed


def compute_current_cost_factor(base_speed_ms: float, u_ms: float, v_ms: float, heading_rad: float) -> float:
    """
    Compute cost multiplication factor based on current.
    
    Args:
        base_speed_ms: Ship's speed through water
        u_ms: Current east component
        v_ms: Current north component
        heading_rad: Ship's heading
        
    Returns:
        Cost factor (>1 for adverse current, <1 for favorable)
    """
    # Calculate how current affects speed
    effective = effective_speed_ms(base_speed_ms, u_ms, v_ms, heading_rad)
    
    if effective <= 0:
        return 10.0  # Very high cost for impossible progress
    
    # Cost inversely proportional to effective speed
    # Normalized by base speed
    cost_factor = base_speed_ms / effective
    
    # Clamp to reasonable range
    return np.clip(cost_factor, 0.5, 5.0)