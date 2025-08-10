"""
Test suite for Hybrid A* planner
"""

import pytest
import numpy as np
from shapely.geometry import Point, LineString, Polygon, MultiPolygon, box

from lib.planner.hybrid_astar import (
    HybridAStar, PlannerConfig, Route, Node
)
from lib.region.feasible_region import FeasibleRegion

# Avoid importing S57Reader in tests - use mock data directly


class TestHybridAStar:
    """Test Hybrid A* planner functionality."""
    
    @pytest.fixture
    def simple_region(self):
        """Create a simple test region with one obstacle."""
        # Create 1km x 1km navigable area with obstacle in center
        bounds = (0, 0, 1000, 1000)
        
        # Central obstacle
        obstacle = box(400, 400, 600, 600)
        no_go_areas = MultiPolygon([obstacle])
        
        # Navigable area is everything except obstacle
        full_area = box(*bounds)
        navigable_area = MultiPolygon([full_area.difference(obstacle)])
        
        return FeasibleRegion(
            bounds=bounds,
            no_go_areas=no_go_areas,
            navigable_area=navigable_area,
            depth_contours={},
            danger_zones=[obstacle],
            restricted_areas=[]
        )
    
    @pytest.fixture
    def planner_config(self):
        """Create test planner configuration."""
        return PlannerConfig(
            grid_resolution=10.0,
            angle_resolution=np.pi / 8,
            min_turn_radius=50.0,
            max_steer_angle=np.pi / 6,
            num_steer_angles=3,
            motion_step=20.0,
            max_iterations=1000,
            goal_tolerance_xy=20.0,
            goal_tolerance_theta=np.pi / 4
        )
    
    def test_planner_initialization(self, planner_config, simple_region):
        """Test planner initialization."""
        planner = HybridAStar(planner_config, simple_region)
        
        assert planner.config == planner_config
        assert planner.region == simple_region
        assert len(planner.motion_primitives) == planner_config.num_steer_angles
    
    def test_straight_line_planning(self, planner_config, simple_region):
        """Test planning a straight line in open water."""
        planner = HybridAStar(planner_config, simple_region)
        
        # Plan from bottom-left to top-left (no obstacles)
        start = (100, 100, 0)  # facing east
        goal = (100, 900, None)  # no heading constraint
        
        route = planner.plan(start, goal)
        
        assert route is not None
        assert len(route.waypoints) >= 2
        assert route.waypoints[0] == (100, 100)
        # Goal should be reached within tolerance
        final_wp = route.waypoints[-1]
        assert abs(final_wp[0] - 100) <= planner_config.goal_tolerance_xy
        assert abs(final_wp[1] - 900) <= planner_config.goal_tolerance_xy
    
    def test_obstacle_avoidance(self, planner_config, simple_region):
        """Test planning around obstacle."""
        planner = HybridAStar(planner_config, simple_region)
        
        # Plan from left to right of obstacle (must go around)
        start = (200, 500, 0)  # Left of obstacle
        goal = (800, 500, None)  # Right of obstacle
        
        route = planner.plan(start, goal)
        
        assert route is not None
        assert len(route.waypoints) > 2  # Not a straight line
        
        # Check route doesn't intersect obstacle
        route_line = route.to_linestring()
        assert not route_line.intersects(simple_region.no_go_areas)
    
    def test_no_valid_path(self, planner_config):
        """Test behavior when no valid path exists."""
        # Create region where goal is inside obstacle
        bounds = (0, 0, 1000, 1000)
        obstacle = box(0, 0, 1000, 1000)  # Entire area is no-go
        no_go_areas = MultiPolygon([obstacle])
        navigable_area = MultiPolygon([])
        
        blocked_region = FeasibleRegion(
            bounds=bounds,
            no_go_areas=no_go_areas,
            navigable_area=navigable_area,
            depth_contours={},
            danger_zones=[],
            restricted_areas=[]
        )
        
        planner = HybridAStar(planner_config, blocked_region)
        
        start = (100, 100, 0)
        goal = (900, 900, None)
        
        route = planner.plan(start, goal)
        assert route is None  # No valid path
    
    def test_motion_primitives(self, planner_config, simple_region):
        """Test motion primitive generation."""
        planner = HybridAStar(planner_config, simple_region)
        
        # Check correct number of primitives
        assert len(planner.motion_primitives) == planner_config.num_steer_angles
        
        # Check primitive values
        for steer, dist in planner.motion_primitives:
            assert abs(steer) <= planner_config.max_steer_angle
            assert dist == planner_config.motion_step
    
    def test_node_expansion(self, planner_config, simple_region):
        """Test node expansion logic."""
        planner = HybridAStar(planner_config, simple_region)
        
        # Create a test node in safe area
        node = Node(x=100, y=100, theta=0, g_cost=0, h_cost=100)
        goal = (200, 100, None)
        
        # Expand node
        neighbors = planner._expand_node(node, goal)
        
        assert len(neighbors) > 0
        assert all(isinstance(n, Node) for n in neighbors)
        
        # Check neighbors have correct parent
        for neighbor in neighbors:
            assert neighbor.parent == node
            assert neighbor.g_cost > node.g_cost
    
    def test_collision_checking(self, planner_config, simple_region):
        """Test collision detection."""
        planner = HybridAStar(planner_config, simple_region)
        
        # Test collision-free path
        from_node = Node(x=100, y=100, theta=0)
        to_node = Node(x=200, y=100, theta=0)
        assert planner._is_collision_free(from_node, to_node) == True
        
        # Test path through obstacle
        from_node = Node(x=300, y=500, theta=0)
        to_node = Node(x=700, y=500, theta=0)  # Goes through central obstacle
        assert planner._is_collision_free(from_node, to_node) == False
    
    def test_heuristic_function(self, planner_config, simple_region):
        """Test heuristic calculation."""
        planner = HybridAStar(planner_config, simple_region)
        
        # Test Euclidean distance heuristic
        h = planner._heuristic(0, 0, 300, 400)
        expected = np.hypot(300, 400)  # 500
        assert abs(h - expected) < 1e-6
    
    def test_goal_reached(self, planner_config, simple_region):
        """Test goal reached detection."""
        planner = HybridAStar(planner_config, simple_region)
        
        goal = (500, 500, np.pi/2)
        
        # Node at goal
        node_at_goal = Node(x=500, y=500, theta=np.pi/2)
        assert planner._is_goal_reached(node_at_goal, goal) == True
        
        # Node within tolerance
        node_near = Node(x=510, y=510, theta=np.pi/2 + 0.1)
        assert planner._is_goal_reached(node_near, goal) == True
        
        # Node outside tolerance
        node_far = Node(x=550, y=550, theta=0)
        assert planner._is_goal_reached(node_far, goal) == False
    
    def test_path_reconstruction(self, planner_config, simple_region):
        """Test path reconstruction from goal node."""
        planner = HybridAStar(planner_config, simple_region)
        
        # Create a chain of nodes
        node1 = Node(x=100, y=100, theta=0, g_cost=0)
        node2 = Node(x=200, y=100, theta=0, g_cost=100, parent=node1)
        node3 = Node(x=300, y=100, theta=0, g_cost=200, parent=node2)
        
        # Reconstruct path
        route = planner._reconstruct_path(node3)
        
        assert len(route.waypoints) == 3
        assert route.waypoints[0] == (100, 100)
        assert route.waypoints[1] == (200, 100)
        assert route.waypoints[2] == (300, 100)
        assert route.total_cost == 200


@pytest.mark.parametrize("start,goal,expected_success", [
    ((100, 100, 0), (900, 900, None), True),  # Diagonal path
    ((100, 100, 0), (100, 900, None), True),  # Vertical path
    ((100, 100, 0), (900, 100, None), True),  # Horizontal path
])
def test_various_paths(start, goal, expected_success):
    """Test planning various paths."""
    # Create open water region
    bounds = (0, 0, 1000, 1000)
    region = FeasibleRegion(
        bounds=bounds,
        no_go_areas=MultiPolygon([]),
        navigable_area=MultiPolygon([box(*bounds)]),
        depth_contours={},
        danger_zones=[],
        restricted_areas=[]
    )
    
    config = PlannerConfig(max_iterations=500)
    planner = HybridAStar(config, region)
    
    route = planner.plan(start, goal)
    
    if expected_success:
        assert route is not None
        assert len(route.waypoints) >= 2
    else:
        assert route is None