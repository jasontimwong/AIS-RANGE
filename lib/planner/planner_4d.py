"""
4D Time-Domain Planner
Extends spatial planning to include time dimension for tide/current optimization
"""

import numpy as np
import heapq
from dataclasses import dataclass
from typing import List, Tuple, Optional, Dict, Any, Set
from datetime import datetime, timedelta
import logging

logger = logging.getLogger(__name__)


@dataclass
class Node4D:
    """4D search node with position and time"""
    x: int
    y: int
    t: int  # Time index
    g: float = 0.0  # Cost so far
    h: float = 0.0  # Heuristic
    parent: Optional['Node4D'] = None
    
    @property
    def f(self) -> float:
        """Total cost estimate"""
        return self.g + self.h
    
    def __lt__(self, other: 'Node4D') -> bool:
        """For priority queue"""
        return self.f < other.f
    
    def __hash__(self) -> int:
        """For set membership"""
        return hash((self.x, self.y, self.t))
    
    def __eq__(self, other: object) -> bool:
        """For equality checks"""
        if not isinstance(other, Node4D):
            return False
        return self.x == other.x and self.y == other.y and self.t == other.t


class Planner4D:
    """4D planner with time-varying costs"""
    
    def __init__(self,
                 grid_size: Tuple[int, int],
                 time_steps: int,
                 time_resolution: float = 600.0,  # seconds per time step
                 s104_adapter: Optional[Any] = None,
                 s111_adapter: Optional[Any] = None):
        """
        Initialize 4D planner.
        
        Args:
            grid_size: (width, height) of spatial grid
            time_steps: Number of time discretization steps
            time_resolution: Seconds per time step
            s104_adapter: Water level adapter
            s111_adapter: Current adapter
        """
        self.width, self.height = grid_size
        self.time_steps = time_steps
        self.time_resolution = time_resolution
        self.s104_adapter = s104_adapter
        self.s111_adapter = s111_adapter
        
        # Cost grids (3D: x, y, t)
        self.static_cost = np.ones((self.width, self.height))
        self.dynamic_cost = np.ones((self.width, self.height, time_steps))
        
        # Feasibility mask
        self.feasible = np.ones((self.width, self.height), dtype=bool)
        
        logger.info(f"Initialized 4D planner: {self.width}x{self.height}x{time_steps}")
    
    def set_static_costs(self, cost_grid: np.ndarray):
        """Set static (time-independent) costs"""
        assert cost_grid.shape == (self.width, self.height)
        self.static_cost = cost_grid
    
    def set_feasible_mask(self, mask: np.ndarray):
        """Set feasible region mask"""
        assert mask.shape == (self.width, self.height)
        self.feasible = mask
    
    def update_dynamic_costs(self, 
                            start_time: datetime,
                            lon_grid: np.ndarray,
                            lat_grid: np.ndarray,
                            depth_grid: np.ndarray,
                            draft: float = 10.0,
                            min_ukc: float = 2.0):
        """
        Update time-varying costs based on tide and currents.
        
        Args:
            start_time: Planning start time
            lon_grid: Longitude grid
            lat_grid: Latitude grid
            depth_grid: Static depth grid
            draft: Ship draft
            min_ukc: Minimum UKC required
        """
        for t in range(self.time_steps):
            current_time = start_time + timedelta(seconds=t * self.time_resolution)
            
            for x in range(self.width):
                for y in range(self.height):
                    if not self.feasible[x, y]:
                        self.dynamic_cost[x, y, t] = np.inf
                        continue
                    
                    cost = self.static_cost[x, y]
                    
                    # Add tide-based cost
                    if self.s104_adapter and x < lon_grid.shape[0] and y < lat_grid.shape[0]:
                        lon = lon_grid[x, y] if lon_grid.ndim > 1 else lon_grid[x]
                        lat = lat_grid[x, y] if lat_grid.ndim > 1 else lat_grid[y]
                        
                        water_level = self.s104_adapter.get_water_level_at_point(
                            lon, lat, current_time
                        )
                        
                        # Calculate dynamic UKC
                        depth = depth_grid[x, y] if x < depth_grid.shape[0] and y < depth_grid.shape[1] else 10.0
                        ukc = depth - draft + water_level
                        
                        if ukc < min_ukc:
                            # Penalize low UKC
                            cost += 10.0 * (min_ukc - ukc) ** 2
                        
                        # Prefer high tide for better clearance
                        cost += 1.0 / (1.0 + water_level)
                    
                    # Add current-based cost
                    if self.s111_adapter:
                        # Simplified current cost (would integrate with S-111)
                        # Favorable current reduces cost
                        current_factor = 1.0  # Placeholder
                        cost *= current_factor
                    
                    self.dynamic_cost[x, y, t] = cost
    
    def plan(self,
             start: Tuple[int, int, int],  # (x, y, t)
             goal: Tuple[int, int],  # (x, y) - time is flexible
             time_window: Optional[Tuple[int, int]] = None) -> Optional[List[Node4D]]:
        """
        Find optimal 4D path.
        
        Args:
            start: Start position and time (x, y, t)
            goal: Goal position (x, y)
            time_window: Optional (earliest, latest) arrival time indices
            
        Returns:
            Path as list of 4D nodes, or None if no path exists
        """
        start_node = Node4D(start[0], start[1], start[2])
        goal_x, goal_y = goal
        
        # Time window constraints
        earliest_arrival = time_window[0] if time_window else 0
        latest_arrival = time_window[1] if time_window else self.time_steps - 1
        
        # Priority queue and visited set
        open_set = [start_node]
        closed_set: Set[Node4D] = set()
        
        # Best cost to each state
        g_score: Dict[Tuple[int, int, int], float] = {
            (start_node.x, start_node.y, start_node.t): 0.0
        }
        
        while open_set:
            current = heapq.heappop(open_set)
            
            # Check goal with time window
            if (current.x == goal_x and current.y == goal_y and
                earliest_arrival <= current.t <= latest_arrival):
                # Reconstruct path
                path = []
                node = current
                while node:
                    path.append(node)
                    node = node.parent
                return list(reversed(path))
            
            if current in closed_set:
                continue
            
            closed_set.add(current)
            
            # Explore neighbors in 4D
            for neighbor in self._get_neighbors_4d(current):
                if neighbor in closed_set:
                    continue
                
                # Check time bounds
                if neighbor.t >= self.time_steps:
                    continue
                
                # Check feasibility
                if not self.feasible[neighbor.x, neighbor.y]:
                    continue
                
                # Calculate cost
                move_cost = self._calculate_move_cost(current, neighbor)
                tentative_g = current.g + move_cost
                
                # Check if better path
                state = (neighbor.x, neighbor.y, neighbor.t)
                if state not in g_score or tentative_g < g_score[state]:
                    g_score[state] = tentative_g
                    neighbor.g = tentative_g
                    neighbor.h = self._heuristic_4d(neighbor, goal_x, goal_y, earliest_arrival)
                    neighbor.parent = current
                    heapq.heappush(open_set, neighbor)
        
        return None  # No path found
    
    def _get_neighbors_4d(self, node: Node4D) -> List[Node4D]:
        """Get 4D neighbors (8-connected in space + time progression)"""
        neighbors = []
        
        # Spatial moves (8-connected)
        for dx in [-1, 0, 1]:
            for dy in [-1, 0, 1]:
                if dx == 0 and dy == 0:
                    # Option to wait in place
                    neighbors.append(Node4D(node.x, node.y, node.t + 1))
                else:
                    nx, ny = node.x + dx, node.y + dy
                    if 0 <= nx < self.width and 0 <= ny < self.height:
                        # Time advances with movement
                        neighbors.append(Node4D(nx, ny, node.t + 1))
        
        return neighbors
    
    def _calculate_move_cost(self, from_node: Node4D, to_node: Node4D) -> float:
        """Calculate cost of moving between 4D nodes"""
        # Spatial distance
        dx = to_node.x - from_node.x
        dy = to_node.y - from_node.y
        spatial_dist = np.sqrt(dx**2 + dy**2) if dx != 0 or dy != 0 else 0.1
        
        # Dynamic cost at destination
        if to_node.t < self.time_steps:
            dynamic = self.dynamic_cost[to_node.x, to_node.y, to_node.t]
        else:
            dynamic = np.inf
        
        # Combine spatial and dynamic costs
        return spatial_dist * dynamic
    
    def _heuristic_4d(self, node: Node4D, goal_x: int, goal_y: int, 
                      earliest_arrival: int) -> float:
        """4D heuristic estimate"""
        # Spatial distance
        spatial_h = np.sqrt((goal_x - node.x)**2 + (goal_y - node.y)**2)
        
        # Time penalty for being too early
        time_h = 0.0
        if node.t < earliest_arrival:
            min_time_to_goal = spatial_h  # Assuming unit speed
            arrival_time = node.t + min_time_to_goal
            if arrival_time < earliest_arrival:
                time_h = (earliest_arrival - arrival_time) * 0.1
        
        return spatial_h + time_h
    
    def extract_trajectory(self, path: List[Node4D], 
                          start_time: datetime,
                          grid_to_world: Optional[Any] = None) -> Dict[str, Any]:
        """
        Extract trajectory with times and positions.
        
        Args:
            path: 4D path nodes
            start_time: Real-world start time
            grid_to_world: Optional transform to world coordinates
            
        Returns:
            Trajectory dictionary
        """
        trajectory = {
            'waypoints': [],
            'times': [],
            'costs': [],
            'total_cost': 0.0,
            'duration': 0.0
        }
        
        for node in path:
            # Time
            time = start_time + timedelta(seconds=node.t * self.time_resolution)
            trajectory['times'].append(time)
            
            # Position
            if grid_to_world:
                world_pos = grid_to_world(node.x, node.y)
            else:
                world_pos = (node.x, node.y)
            
            trajectory['waypoints'].append(world_pos)
            
            # Cost
            if node.t < self.time_steps:
                cost = self.dynamic_cost[node.x, node.y, node.t]
                trajectory['costs'].append(float(cost))
        
        if path:
            trajectory['total_cost'] = path[-1].g
            trajectory['duration'] = (path[-1].t - path[0].t) * self.time_resolution
        
        return trajectory
    
    def find_optimal_departure(self,
                              start: Tuple[int, int],
                              goal: Tuple[int, int],
                              time_range: Tuple[datetime, datetime],
                              time_window: Optional[Tuple[datetime, datetime]] = None) -> Dict[str, Any]:
        """
        Find optimal departure time within range.
        
        Args:
            start: Start position (x, y)
            goal: Goal position (x, y)
            time_range: (earliest, latest) departure times
            time_window: Optional (earliest, latest) arrival times
            
        Returns:
            Optimal departure analysis
        """
        results = []
        
        # Convert times to indices
        base_time = time_range[0]
        departure_indices = range(0, min(10, self.time_steps))  # Sample departures
        
        for dep_idx in departure_indices:
            # Try planning from this departure time
            path = self.plan(
                (start[0], start[1], dep_idx),
                goal,
                time_window=self._time_window_to_indices(time_window, base_time) if time_window else None
            )
            
            if path:
                departure_time = base_time + timedelta(seconds=dep_idx * self.time_resolution)
                arrival_time = base_time + timedelta(seconds=path[-1].t * self.time_resolution)
                
                results.append({
                    'departure_time': departure_time,
                    'arrival_time': arrival_time,
                    'cost': path[-1].g,
                    'duration': (path[-1].t - dep_idx) * self.time_resolution,
                    'path': path
                })
        
        if not results:
            return {'status': 'no_feasible_departure'}
        
        # Find optimal
        optimal = min(results, key=lambda r: r['cost'])
        
        return {
            'status': 'success',
            'optimal': optimal,
            'alternatives': results
        }
    
    def _time_window_to_indices(self, 
                               window: Tuple[datetime, datetime],
                               base_time: datetime) -> Tuple[int, int]:
        """Convert datetime window to time indices"""
        earliest = int((window[0] - base_time).total_seconds() / self.time_resolution)
        latest = int((window[1] - base_time).total_seconds() / self.time_resolution)
        
        earliest = max(0, min(earliest, self.time_steps - 1))
        latest = max(0, min(latest, self.time_steps - 1))
        
        return earliest, latest