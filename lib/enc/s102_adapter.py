"""
S-102 High Resolution Bathymetry Adapter
Converts S-102 depth data to internal depth grid format
"""

from typing import Tuple
import numpy as np
import csv
import logging

logger = logging.getLogger(__name__)


def load_s102_csv(path: str) -> Tuple[np.ndarray, np.ndarray, np.ndarray]:
    """
    Load S-102 depth data from CSV format.
    
    Args:
        path: Path to CSV file with columns: lon, lat, depth_m
        
    Returns:
        Tuple of (lon_grid, lat_grid, depth_2d) where depth_2d.shape = (H, W)
    """
    lons = []
    lats = []
    depths = []
    
    with open(path, 'r', encoding='utf-8') as f:
        reader = csv.reader(f)
        for line in reader:
            # Skip comments and empty lines
            if not line or line[0].startswith('#'):
                continue
            
            lon, lat, depth = map(float, line)
            lons.append(lon)
            lats.append(lat)
            depths.append(depth)
    
    # Convert to numpy arrays
    lons = np.array(lons)
    lats = np.array(lats)
    depths = np.array(depths)
    
    # Determine grid dimensions
    unique_lons = np.unique(lons)
    unique_lats = np.unique(lats)
    
    # Create grid
    lon_grid, lat_grid = np.meshgrid(unique_lons, unique_lats)
    
    # Fill depth grid
    depth_2d = np.zeros((len(unique_lats), len(unique_lons)))
    for i, (lon, lat, depth) in enumerate(zip(lons, lats, depths)):
        lat_idx = np.where(unique_lats == lat)[0][0]
        lon_idx = np.where(unique_lons == lon)[0][0]
        depth_2d[lat_idx, lon_idx] = depth
    
    logger.info(f"Loaded S-102 grid: shape={depth_2d.shape}, "
                f"lon=[{unique_lons.min():.3f}, {unique_lons.max():.3f}], "
                f"lat=[{unique_lats.min():.3f}, {unique_lats.max():.3f}]")
    
    return lon_grid, lat_grid, depth_2d


def to_no_go_mask(depth_2d: np.ndarray, safety_depth_m: float) -> np.ndarray:
    """
    Convert depth grid to no-go mask based on safety depth.
    
    Args:
        depth_2d: 2D array of depths in meters
        safety_depth_m: Minimum safe water depth
        
    Returns:
        Boolean array where True indicates no-go areas
    """
    # Areas shallower than safety depth are no-go
    no_go_mask = depth_2d < safety_depth_m
    
    logger.info(f"Generated no-go mask: safety_depth={safety_depth_m}m, "
                f"no-go_ratio={no_go_mask.sum() / no_go_mask.size:.2%}")
    
    return no_go_mask


def compute_area_difference(mask1: np.ndarray, mask2: np.ndarray) -> float:
    """
    Compute area difference between two masks.
    
    Args:
        mask1: First boolean mask
        mask2: Second boolean mask
        
    Returns:
        Percentage difference in area
    """
    area1 = mask1.sum()
    area2 = mask2.sum()
    
    if area1 == 0:
        return 100.0 if area2 > 0 else 0.0
    
    diff_ratio = abs(area1 - area2) / area1
    return diff_ratio * 100


def generate_difference_heatmap(depth_s102: np.ndarray, depth_s57: np.ndarray) -> np.ndarray:
    """
    Generate heatmap showing depth differences between S-102 and S-57.
    
    Args:
        depth_s102: S-102 depth grid
        depth_s57: S-57 depth grid (interpolated to same resolution)
        
    Returns:
        Difference heatmap (S-102 - S-57)
    """
    # Ensure same shape
    if depth_s102.shape != depth_s57.shape:
        raise ValueError(f"Shape mismatch: S-102={depth_s102.shape}, S-57={depth_s57.shape}")
    
    diff = depth_s102 - depth_s57
    
    logger.info(f"Depth difference stats: mean={diff.mean():.2f}m, "
                f"std={diff.std():.2f}m, "
                f"min={diff.min():.2f}m, max={diff.max():.2f}m")
    
    return diff