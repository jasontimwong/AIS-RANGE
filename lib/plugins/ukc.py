"""
UKC (Under Keel Clearance) Plugin
Calculates and validates under keel clearance for routes
"""

from dataclasses import dataclass
from typing import List, Tuple, Optional, Dict, Any
import numpy as np
import logging

logger = logging.getLogger(__name__)


@dataclass
class UKCResult:
    """Result of UKC evaluation"""
    min_ukc_m: float
    violations: int
    violation_points: List[Tuple[float, float]]
    ukc_profile: List[float]  # UKC at each sample point
    
    def is_safe(self) -> bool:
        """Check if route meets UKC requirements"""
        return self.violations == 0


def evaluate_route_ukc(
    route_pts: List[Tuple[float, float]],
    lon_grid: np.ndarray,
    lat_grid: np.ndarray,
    depth_2d: np.ndarray,
    ship_draft_m: float,
    min_ukc_m: float,
    tide_elevation_m: float = 0.0,
    wave_heave_m: float = 0.0,
    sample_interval_m: float = 100.0
) -> UKCResult:
    """
    Evaluate Under Keel Clearance along a route.
    
    Args:
        route_pts: List of (lon, lat) waypoints
        lon_grid: Longitude grid from S-102
        lat_grid: Latitude grid from S-102
        depth_2d: Depth array from S-102
        ship_draft_m: Ship's draft in meters
        min_ukc_m: Minimum required UKC
        tide_elevation_m: Tidal elevation (positive = higher water)
        wave_heave_m: Wave-induced heave
        sample_interval_m: Distance between UKC samples
        
    Returns:
        UKCResult with minimum UKC and violations
    """
    violations = 0
    violation_points = []
    ukc_profile = []
    min_ukc = float('inf')
    
    # Sample points along route
    sample_points = _sample_route(route_pts, sample_interval_m)
    
    for lon, lat in sample_points:
        # Get depth at this point (nearest neighbor interpolation)
        depth = _interpolate_depth(lon, lat, lon_grid, lat_grid, depth_2d)
        
        # Calculate UKC
        # UKC = Water Depth - Draft + Tide - Wave Heave
        ukc = depth - ship_draft_m + tide_elevation_m - wave_heave_m
        
        ukc_profile.append(ukc)
        min_ukc = min(min_ukc, ukc)
        
        # Check for violation
        if ukc < min_ukc_m:
            violations += 1
            violation_points.append((lon, lat))
            logger.warning(f"UKC violation at ({lon:.4f}, {lat:.4f}): "
                         f"UKC={ukc:.2f}m < required={min_ukc_m}m")
    
    result = UKCResult(
        min_ukc_m=min_ukc,
        violations=violations,
        violation_points=violation_points,
        ukc_profile=ukc_profile
    )
    
    logger.info(f"UKC evaluation: min={min_ukc:.2f}m, violations={violations}, "
                f"samples={len(sample_points)}")
    
    return result


def _sample_route(route_pts: List[Tuple[float, float]], 
                  interval_m: float) -> List[Tuple[float, float]]:
    """
    Sample points along route at regular intervals.
    
    Args:
        route_pts: Waypoints as (lon, lat) tuples
        interval_m: Sampling interval in meters
        
    Returns:
        List of sampled (lon, lat) points
    """
    samples = []
    
    # Always include waypoints
    for i in range(len(route_pts)):
        if i == 0:
            samples.append(route_pts[i])
        else:
            # Interpolate between waypoints
            prev_lon, prev_lat = route_pts[i-1]
            curr_lon, curr_lat = route_pts[i]
            
            # Calculate distance (simplified for small distances)
            dx = (curr_lon - prev_lon) * 111000 * np.cos(np.radians(prev_lat))
            dy = (curr_lat - prev_lat) * 111000
            dist = np.sqrt(dx**2 + dy**2)
            
            # Number of samples in this segment
            n_samples = max(1, int(dist / interval_m))
            
            for j in range(1, n_samples + 1):
                t = j / n_samples
                lon = prev_lon + t * (curr_lon - prev_lon)
                lat = prev_lat + t * (curr_lat - prev_lat)
                samples.append((lon, lat))
    
    return samples


def _interpolate_depth(lon: float, lat: float,
                      lon_grid: np.ndarray, lat_grid: np.ndarray,
                      depth_2d: np.ndarray) -> float:
    """
    Interpolate depth at given position (nearest neighbor).
    
    Args:
        lon: Query longitude
        lat: Query latitude
        lon_grid: Grid of longitudes
        lat_grid: Grid of latitudes
        depth_2d: Depth values
        
    Returns:
        Interpolated depth
    """
    # Find nearest grid point
    lon_flat = lon_grid.flatten()
    lat_flat = lat_grid.flatten()
    
    distances = np.sqrt((lon_flat - lon)**2 + (lat_flat - lat)**2)
    nearest_idx = np.argmin(distances)
    
    # Convert flat index to 2D index
    i, j = np.unravel_index(nearest_idx, depth_2d.shape)
    
    return depth_2d[i, j]


def generate_ukc_heatmap(route_pts: List[Tuple[float, float]],
                        lon_grid: np.ndarray,
                        lat_grid: np.ndarray,
                        depth_2d: np.ndarray,
                        ship_draft_m: float,
                        tide_elevation_m: float = 0.0,
                        wave_heave_m: float = 0.0) -> np.ndarray:
    """
    Generate UKC heatmap for entire grid.
    
    Args:
        route_pts: Route waypoints (for context)
        lon_grid: Longitude grid
        lat_grid: Latitude grid
        depth_2d: Depth array
        ship_draft_m: Ship's draft
        tide_elevation_m: Tidal elevation
        wave_heave_m: Wave heave
        
    Returns:
        2D array of UKC values
    """
    # Calculate UKC at every grid point
    ukc_grid = depth_2d - ship_draft_m + tide_elevation_m - wave_heave_m
    
    logger.info(f"UKC heatmap: min={ukc_grid.min():.2f}m, "
                f"max={ukc_grid.max():.2f}m, "
                f"mean={ukc_grid.mean():.2f}m")
    
    return ukc_grid


def load_ukc_config(config_path: str = "config/plugins/ukc.yaml") -> Dict[str, float]:
    """
    Load UKC configuration from YAML file.
    
    Args:
        config_path: Path to configuration file
        
    Returns:
        Configuration dictionary
    """
    import yaml
    
    try:
        with open(config_path, 'r') as f:
            config = yaml.safe_load(f)
            logger.info(f"Loaded UKC config: {config}")
            return config
    except FileNotFoundError:
        logger.warning(f"UKC config not found at {config_path}, using defaults")
        return {
            'min_ukc_m': 1.0,
            'default_draft_m': 9.5,
            'tide_elevation_m': 0.5,
            'wave_heave_m': 0.3
        }