"""
Cost Field Module
Generates comprehensive cost maps for path planning.
Combines multiple cost factors: distance, curvature, safety margins, traffic, and speed constraints.
"""

from typing import Dict, Optional, Tuple, Callable
from dataclasses import dataclass
import numpy as np
from scipy.interpolate import RegularGridInterpolator
import logging

logger = logging.getLogger(__name__)


@dataclass
class CostWeights:
    """Weights for different cost components."""
    w_distance: float = 1.0      # Distance/length cost
    w_curvature: float = 0.5     # Curvature/turning cost
    w_safety: float = 2.0        # Safety margin cost
    w_traffic: float = 1.5       # Traffic/CPA cost
    w_speed: float = 0.3         # Speed constraint cost
    w_depth: float = 1.0         # Depth/UKC cost
    
    def normalize(self) -> None:
        """Normalize weights to sum to 1."""
        total = (self.w_distance + self.w_curvature + self.w_safety + 
                self.w_traffic + self.w_speed + self.w_depth)
        if total > 0:
            self.w_distance /= total
            self.w_curvature /= total
            self.w_safety /= total
            self.w_traffic /= total
            self.w_speed /= total
            self.w_depth /= total


class CostField:
    """
    Comprehensive cost field for route planning.
    Combines multiple cost layers into a unified cost map.
    """
    
    def __init__(self, 
                 bounds: Tuple[float, float, float, float],
                 resolution: float = 10.0,
                 weights: Optional[CostWeights] = None):
        """
        Initialize cost field.
        
        Args:
            bounds: (minx, miny, maxx, maxy) in meters
            resolution: Grid resolution in meters
            weights: Cost component weights
        """
        self.bounds = bounds
        self.resolution = resolution
        self.weights = weights or CostWeights()
        
        # Calculate grid dimensions
        self.minx, self.miny, self.maxx, self.maxy = bounds
        self.width = int((self.maxx - self.minx) / resolution) + 1
        self.height = int((self.maxy - self.miny) / resolution) + 1
        
        # Initialize cost layers
        self.distance_cost = np.zeros((self.height, self.width))
        self.curvature_cost = np.zeros((self.height, self.width))
        self.safety_cost = np.zeros((self.height, self.width))
        self.traffic_cost = np.zeros((self.height, self.width))
        self.speed_cost = np.zeros((self.height, self.width))
        self.depth_cost = np.zeros((self.height, self.width))
        
        # Combined cost field
        self.total_cost = np.zeros((self.height, self.width))
        
        # Create interpolator for continuous queries
        self.interpolator = None
        self._update_interpolator()
    
    def set_distance_cost(self, goal_x: float, goal_y: float) -> None:
        """
        Set distance-based cost (Euclidean distance to goal).
        
        Args:
            goal_x: Goal X coordinate in meters
            goal_y: Goal Y coordinate in meters
        """
        for i in range(self.height):
            for j in range(self.width):
                x = self.minx + j * self.resolution
                y = self.miny + i * self.resolution
                self.distance_cost[i, j] = np.hypot(x - goal_x, y - goal_y)
        
        # Normalize
        if self.distance_cost.max() > 0:
            self.distance_cost /= self.distance_cost.max()
    
    def set_safety_cost_from_obstacles(self, 
                                      obstacle_distance_func: Callable[[float, float], float],
                                      safety_margin: float = 100.0) -> None:
        """
        Set safety cost based on distance to obstacles.
        
        Args:
            obstacle_distance_func: Function that returns distance to nearest obstacle
            safety_margin: Distance within which cost increases (meters)
        """
        for i in range(self.height):
            for j in range(self.width):
                x = self.minx + j * self.resolution
                y = self.miny + i * self.resolution
                
                dist = obstacle_distance_func(x, y)
                
                if dist < safety_margin:
                    # Exponential cost increase near obstacles
                    self.safety_cost[i, j] = np.exp(-dist / (safety_margin / 3))
                else:
                    self.safety_cost[i, j] = 0
    
    def set_curvature_cost_from_map(self, curvature_map: np.ndarray) -> None:
        """
        Set curvature cost from pre-computed curvature constraints.
        
        Args:
            curvature_map: 2D array of curvature costs (same dimensions as grid)
        """
        if curvature_map.shape == (self.height, self.width):
            self.curvature_cost = curvature_map.copy()
            
            # Normalize
            if self.curvature_cost.max() > 0:
                self.curvature_cost /= self.curvature_cost.max()
        else:
            logger.warning("Curvature map dimensions don't match cost field")
    
    def set_traffic_cost(self, 
                         traffic_density_func: Optional[Callable[[float, float, float], float]] = None,
                         time: float = 0.0) -> None:
        """
        Set traffic-based cost.
        
        Args:
            traffic_density_func: Function(x, y, t) -> density/risk value
            time: Current time for traffic prediction
        """
        if traffic_density_func:
            for i in range(self.height):
                for j in range(self.width):
                    x = self.minx + j * self.resolution
                    y = self.miny + i * self.resolution
                    self.traffic_cost[i, j] = traffic_density_func(x, y, time)
            
            # Normalize
            if self.traffic_cost.max() > 0:
                self.traffic_cost /= self.traffic_cost.max()
    
    def set_depth_cost(self, 
                      depth_func: Callable[[float, float], float],
                      min_depth: float = 10.0,
                      critical_depth: float = 5.0) -> None:
        """
        Set depth-based cost for UKC constraints.
        
        Args:
            depth_func: Function(x, y) -> water depth in meters
            min_depth: Preferred minimum depth
            critical_depth: Critical minimum depth (high cost below this)
        """
        for i in range(self.height):
            for j in range(self.width):
                x = self.minx + j * self.resolution
                y = self.miny + i * self.resolution
                
                depth = depth_func(x, y)
                
                if depth < critical_depth:
                    # Very high cost for critically shallow water
                    self.depth_cost[i, j] = 10.0
                elif depth < min_depth:
                    # Increasing cost as depth decreases
                    self.depth_cost[i, j] = (min_depth - depth) / (min_depth - critical_depth)
                else:
                    self.depth_cost[i, j] = 0
        
        # Normalize to [0, 1] range
        max_cost = self.depth_cost.max()
        if max_cost > 0 and max_cost != 10.0:
            mask = self.depth_cost < 10.0
            self.depth_cost[mask] /= max_cost
    
    def set_speed_cost(self, 
                       speed_limit_func: Optional[Callable[[float, float], float]] = None,
                       vessel_speed: float = 10.0) -> None:
        """
        Set speed constraint cost.
        
        Args:
            speed_limit_func: Function(x, y) -> speed limit in m/s
            vessel_speed: Planned vessel speed in m/s
        """
        if speed_limit_func:
            for i in range(self.height):
                for j in range(self.width):
                    x = self.minx + j * self.resolution
                    y = self.miny + i * self.resolution
                    
                    limit = speed_limit_func(x, y)
                    
                    if vessel_speed > limit:
                        # Cost for exceeding speed limit
                        self.speed_cost[i, j] = (vessel_speed - limit) / vessel_speed
                    else:
                        self.speed_cost[i, j] = 0
    
    def combine_costs(self) -> np.ndarray:
        """
        Combine all cost layers using weights.
        
        Returns:
            Combined cost field
        """
        self.total_cost = (
            self.weights.w_distance * self.distance_cost +
            self.weights.w_curvature * self.curvature_cost +
            self.weights.w_safety * self.safety_cost +
            self.weights.w_traffic * self.traffic_cost +
            self.weights.w_speed * self.speed_cost +
            self.weights.w_depth * self.depth_cost
        )
        
        self._update_interpolator()
        return self.total_cost
    
    def get_cost(self, x: float, y: float) -> float:
        """
        Get interpolated cost at continuous position.
        
        Args:
            x: X coordinate in meters
            y: Y coordinate in meters
            
        Returns:
            Interpolated cost value
        """
        if self.interpolator is None:
            self.combine_costs()
        
        # Clamp to bounds
        x = np.clip(x, self.minx, self.maxx)
        y = np.clip(y, self.miny, self.maxy)
        
        try:
            return float(self.interpolator([y, x]))
        except:
            # Fallback to nearest grid point
            j = int((x - self.minx) / self.resolution)
            i = int((y - self.miny) / self.resolution)
            i = np.clip(i, 0, self.height - 1)
            j = np.clip(j, 0, self.width - 1)
            return self.total_cost[i, j]
    
    def get_gradient(self, x: float, y: float) -> Tuple[float, float]:
        """
        Get cost gradient at position (for gradient-based planning).
        
        Args:
            x: X coordinate in meters
            y: Y coordinate in meters
            
        Returns:
            (grad_x, grad_y) gradient components
        """
        # Use finite differences
        h = self.resolution / 2
        
        cost_xp = self.get_cost(x + h, y)
        cost_xm = self.get_cost(x - h, y)
        cost_yp = self.get_cost(x, y + h)
        cost_ym = self.get_cost(x, y - h)
        
        grad_x = (cost_xp - cost_xm) / (2 * h)
        grad_y = (cost_yp - cost_ym) / (2 * h)
        
        return grad_x, grad_y
    
    def _update_interpolator(self) -> None:
        """Update the interpolator for continuous cost queries."""
        y_coords = np.linspace(self.miny, self.maxy, self.height)
        x_coords = np.linspace(self.minx, self.maxx, self.width)
        
        self.interpolator = RegularGridInterpolator(
            (y_coords, x_coords),
            self.total_cost,
            method='linear',
            bounds_error=False,
            fill_value=np.inf
        )
    
    def visualize_layer(self, layer_name: str = "total") -> np.ndarray:
        """
        Get a specific cost layer for visualization.
        
        Args:
            layer_name: Name of layer to retrieve
            
        Returns:
            2D numpy array of costs
        """
        layers = {
            "total": self.total_cost,
            "distance": self.distance_cost,
            "curvature": self.curvature_cost,
            "safety": self.safety_cost,
            "traffic": self.traffic_cost,
            "speed": self.speed_cost,
            "depth": self.depth_cost
        }
        
        return layers.get(layer_name, self.total_cost)