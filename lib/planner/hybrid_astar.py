"""
Hybrid A* Path Planner Module
Implements kinematically-feasible path planning with continuous state space.
Combines A* graph search with continuous motion primitives.
"""

from typing import List, Tuple, Optional, Dict, Set
from dataclasses import dataclass, field
from heapq import heappush, heappop
import numpy as np
from shapely.geometry import LineString, Point
import logging
import time

from lib.region.feasible_region import FeasibleRegion
from lib.costs.cost_field import CostField

logger = logging.getLogger(__name__)


@dataclass
class Node:
    """Represents a node in the Hybrid A* search tree."""
    x: float  # X position (meters)
    y: float  # Y position (meters)
    theta: float  # Heading (radians)
    g_cost: float = 0.0  # Cost from start
    h_cost: float = 0.0  # Heuristic cost to goal
    parent: Optional['Node'] = None
    steer: float = 0.0  # Steering angle used to reach this node
    velocity: float = 10.0  # Velocity (m/s)
    
    @property
    def f_cost(self) -> float:
        """Total cost (g + h)."""
        return self.g_cost + self.h_cost
    
    def __lt__(self, other: 'Node') -> bool:
        """For priority queue ordering."""
        return self.f_cost < other.f_cost
    
    def get_grid_index(self, resolution: float, angle_resolution: float) -> Tuple[int, int, int]:
        """Get discretized grid index for collision checking."""
        xi = int(self.x / resolution)
        yi = int(self.y / resolution)
        ti = int(self.theta / angle_resolution) % int(2 * np.pi / angle_resolution)
        return (xi, yi, ti)


@dataclass
class PlannerConfig:
    """Configuration for Hybrid A* planner."""
    grid_resolution: float = 10.0  # Spatial discretization (meters)
    angle_resolution: float = np.pi / 8  # Angular discretization (radians)
    min_turn_radius: float = 100.0  # Minimum turning radius (meters)
    max_steer_angle: float = np.pi / 4  # Maximum steering angle (radians)
    num_steer_angles: int = 5  # Number of steering angles to try
    motion_step: float = 20.0  # Motion primitive step size (meters)
    max_iterations: int = 10000  # Maximum search iterations
    goal_tolerance_xy: float = 20.0  # Goal position tolerance (meters)
    goal_tolerance_theta: float = np.pi / 8  # Goal heading tolerance (radians)
    vessel_length: float = 50.0  # Vessel length for collision checking (meters)
    vessel_width: float = 10.0  # Vessel width for collision checking (meters)


@dataclass
class Route:
    """Represents a planned route."""
    waypoints: List[Tuple[float, float]]  # (x, y) waypoints
    headings: List[float]  # Heading at each waypoint (radians)
    velocities: List[float]  # Velocity at each waypoint (m/s)
    total_cost: float = 0.0
    planning_time: float = 0.0  # Planning time in seconds
    
    def to_linestring(self) -> LineString:
        """Convert route to Shapely LineString."""
        return LineString(self.waypoints)
    
    def get_length(self) -> float:
        """Get total route length in meters."""
        if len(self.waypoints) < 2:
            return 0.0
        return self.to_linestring().length


class HybridAStar:
    """
    Hybrid A* path planner implementation.
    Combines discrete grid search with continuous motion primitives.
    """
    
    def __init__(self, config: PlannerConfig, feasible_region: FeasibleRegion):
        """
        Initialize planner.
        
        Args:
            config: Planner configuration
            feasible_region: Feasible navigation region
        """
        self.config = config
        self.region = feasible_region
        self.cost_field: Optional[CostField] = None
        
        # Generate motion primitives
        self.motion_primitives = self._generate_motion_primitives()
        
        # Initialize visited set for duplicate detection
        self.visited: Set[Tuple[int, int, int]] = set()
    
    def set_cost_field(self, cost_field: CostField) -> None:
        """Set the cost field for planning."""
        self.cost_field = cost_field
    
    def plan(self, 
             start: Tuple[float, float, float],
             goal: Tuple[float, float, float],
             initial_velocity: float = 10.0) -> Optional[Route]:
        """
        Plan a route from start to goal.
        
        Args:
            start: Start pose (x, y, theta) in meters and radians
            goal: Goal pose (x, y, theta) in meters and radians
            initial_velocity: Initial velocity in m/s
            
        Returns:
            Route object if successful, None if no path found
        """
        start_time = time.time()
        logger.info(f"Planning from {start} to {goal}")
        
        # Reset visited set
        self.visited.clear()
        
        # Initialize start node
        start_node = Node(
            x=start[0], y=start[1], theta=start[2],
            g_cost=0.0,
            h_cost=self._heuristic(start[0], start[1], goal[0], goal[1]),
            velocity=initial_velocity
        )
        
        # Priority queue for open set
        open_set = []
        heappush(open_set, start_node)
        
        # Track best node found (for partial solutions)
        best_node = start_node
        best_distance = float('inf')
        
        iterations = 0
        
        while open_set and iterations < self.config.max_iterations:
            iterations += 1
            
            # Get node with lowest f-cost
            current = heappop(open_set)
            
            # Check if goal reached
            if self._is_goal_reached(current, goal):
                logger.info(f"Goal reached after {iterations} iterations")
                route = self._reconstruct_path(current)
                route.planning_time = time.time() - start_time
                return route
            
            # Track best node (closest to goal)
            dist_to_goal = np.hypot(current.x - goal[0], current.y - goal[1])
            if dist_to_goal < best_distance:
                best_distance = dist_to_goal
                best_node = current
            
            # Mark as visited
            grid_index = current.get_grid_index(
                self.config.grid_resolution,
                self.config.angle_resolution
            )
            if grid_index in self.visited:
                continue
            self.visited.add(grid_index)
            
            # Expand neighbors using motion primitives
            neighbors = self._expand_node(current, goal)
            
            for neighbor in neighbors:
                # Check if already visited
                neighbor_index = neighbor.get_grid_index(
                    self.config.grid_resolution,
                    self.config.angle_resolution
                )
                if neighbor_index not in self.visited:
                    heappush(open_set, neighbor)
        
        logger.warning(f"No complete path found after {iterations} iterations")
        logger.info(f"Best node distance to goal: {best_distance:.1f}m")
        
        # Return partial solution if available
        if best_node != start_node:
            route = self._reconstruct_path(best_node)
            route.planning_time = time.time() - start_time
            return route
        
        return None
    
    def _generate_motion_primitives(self) -> List[Tuple[float, float]]:
        """Generate discrete steering angles and distances for motion primitives."""
        primitives = []
        
        # Generate steering angles
        if self.config.num_steer_angles == 1:
            steer_angles = [0.0]
        else:
            steer_angles = np.linspace(
                -self.config.max_steer_angle,
                self.config.max_steer_angle,
                self.config.num_steer_angles
            )
        
        # Each primitive is (steering_angle, distance)
        for steer in steer_angles:
            primitives.append((steer, self.config.motion_step))
        
        return primitives
    
    def _expand_node(self, node: Node, goal: Tuple[float, float, float]) -> List[Node]:
        """Expand a node using motion primitives."""
        neighbors = []
        
        for steer_angle, distance in self.motion_primitives:
            # Apply motion model
            new_node = self._apply_motion_primitive(node, steer_angle, distance)
            
            if new_node is None:
                continue
            
            # Check collision
            if not self._is_collision_free(node, new_node):
                continue
            
            # Calculate costs
            motion_cost = self._calculate_motion_cost(node, new_node)
            new_node.g_cost = node.g_cost + motion_cost
            new_node.h_cost = self._heuristic(new_node.x, new_node.y, goal[0], goal[1])
            new_node.parent = node
            new_node.steer = steer_angle
            
            neighbors.append(new_node)
        
        return neighbors
    
    def _apply_motion_primitive(self, node: Node, steer_angle: float, distance: float) -> Optional[Node]:
        """
        Apply motion primitive using bicycle model.
        
        Args:
            node: Current node
            steer_angle: Steering angle in radians
            distance: Distance to travel in meters
            
        Returns:
            New node after applying motion
        """
        # Simple bicycle model
        if abs(steer_angle) < 1e-6:
            # Straight motion
            new_x = node.x + distance * np.cos(node.theta)
            new_y = node.y + distance * np.sin(node.theta)
            new_theta = node.theta
        else:
            # Curved motion
            radius = self.config.min_turn_radius / np.tan(abs(steer_angle))
            
            # Arc length
            dtheta = distance / radius
            
            # New position and heading
            new_theta = node.theta + dtheta * np.sign(steer_angle)
            
            # Calculate new position using arc geometry
            if steer_angle > 0:  # Left turn
                cx = node.x - radius * np.sin(node.theta)
                cy = node.y + radius * np.cos(node.theta)
                new_x = cx + radius * np.sin(new_theta)
                new_y = cy - radius * np.cos(new_theta)
            else:  # Right turn
                cx = node.x + radius * np.sin(node.theta)
                cy = node.y - radius * np.cos(node.theta)
                new_x = cx - radius * np.sin(new_theta)
                new_y = cy + radius * np.cos(new_theta)
        
        # Normalize theta to [-pi, pi]
        new_theta = np.arctan2(np.sin(new_theta), np.cos(new_theta))
        
        return Node(x=new_x, y=new_y, theta=new_theta, velocity=node.velocity)
    
    def _is_collision_free(self, from_node: Node, to_node: Node) -> bool:
        """Check if motion from one node to another is collision-free."""
        # Create path segment
        path = LineString([(from_node.x, from_node.y), (to_node.x, to_node.y)])
        
        # Check against no-go areas
        if path.intersects(self.region.no_go_areas):
            return False
        
        # Check if endpoints are in navigable area
        if not self.region.is_point_safe(to_node.x, to_node.y):
            return False
        
        # TODO: Add vessel shape collision checking
        # For now, use point collision checking
        
        return True
    
    def _calculate_motion_cost(self, from_node: Node, to_node: Node) -> float:
        """Calculate cost of motion between nodes."""
        # Base cost: distance
        distance = np.hypot(to_node.x - from_node.x, to_node.y - from_node.y)
        cost = distance
        
        # Add steering cost (penalize turning)
        steer_cost = abs(to_node.steer) * 10.0
        cost += steer_cost
        
        # Add cost field contribution if available
        if self.cost_field:
            field_cost = self.cost_field.get_cost(to_node.x, to_node.y)
            cost += field_cost * distance
        
        # Add safety margin cost (distance to hazards)
        clearance = self.region.get_clearance(to_node.x, to_node.y)
        if clearance < 100.0:  # Within 100m of hazard
            safety_cost = (100.0 - clearance) * 0.5
            cost += safety_cost
        
        return cost
    
    def _heuristic(self, x1: float, y1: float, x2: float, y2: float) -> float:
        """Heuristic function for A* (Euclidean distance)."""
        return np.hypot(x2 - x1, y2 - y1)
    
    def _is_goal_reached(self, node: Node, goal: Tuple[float, float, float]) -> bool:
        """Check if node has reached the goal."""
        pos_error = np.hypot(node.x - goal[0], node.y - goal[1])
        
        # Check position tolerance
        if pos_error > self.config.goal_tolerance_xy:
            return False
        
        # Check heading tolerance (optional)
        if goal[2] is not None:
            heading_error = abs(node.theta - goal[2])
            if heading_error > np.pi:
                heading_error = 2 * np.pi - heading_error
            
            if heading_error > self.config.goal_tolerance_theta:
                return False
        
        return True
    
    def _reconstruct_path(self, goal_node: Node) -> Route:
        """Reconstruct path from start to goal node."""
        path = []
        headings = []
        velocities = []
        
        current = goal_node
        while current is not None:
            path.append((current.x, current.y))
            headings.append(current.theta)
            velocities.append(current.velocity)
            current = current.parent
        
        # Reverse to get start->goal order
        path.reverse()
        headings.reverse()
        velocities.reverse()
        
        return Route(
            waypoints=path,
            headings=headings,
            velocities=velocities,
            total_cost=goal_node.g_cost
        )