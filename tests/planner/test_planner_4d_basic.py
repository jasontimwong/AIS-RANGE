"""
Tests for 4D Time-Domain Planner
"""

import pytest
import numpy as np
from datetime import datetime, timedelta
import sys
import os

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from lib.planner.planner_4d import Node4D, Planner4D


class TestNode4D:
    """Test 4D node class"""
    
    def test_node_creation(self):
        """Test creating 4D node"""
        node = Node4D(x=10, y=20, t=5, g=1.0, h=2.0)
        
        assert node.x == 10
        assert node.y == 20
        assert node.t == 5
        assert node.g == 1.0
        assert node.h == 2.0
        assert node.f == 3.0
    
    def test_node_comparison(self):
        """Test node comparison for priority queue"""
        node1 = Node4D(0, 0, 0, g=1.0, h=2.0)  # f=3
        node2 = Node4D(1, 1, 1, g=2.0, h=1.0)  # f=3
        node3 = Node4D(2, 2, 2, g=0.5, h=1.0)  # f=1.5
        
        assert not (node1 < node2)  # Equal f values
        assert node3 < node1  # Lower f value
    
    def test_node_hashing(self):
        """Test node hashing for set membership"""
        node1 = Node4D(10, 20, 5)
        node2 = Node4D(10, 20, 5)
        node3 = Node4D(10, 20, 6)
        
        nodes = {node1}
        assert node2 in nodes  # Same coordinates
        assert node3 not in nodes  # Different time


class TestPlanner4D:
    """Test 4D planner"""
    
    def test_planner_initialization(self):
        """Test planner initialization"""
        planner = Planner4D(
            grid_size=(50, 40),
            time_steps=10,
            time_resolution=600.0
        )
        
        assert planner.width == 50
        assert planner.height == 40
        assert planner.time_steps == 10
        assert planner.time_resolution == 600.0
        assert planner.static_cost.shape == (50, 40)
        assert planner.dynamic_cost.shape == (50, 40, 10)
    
    def test_set_static_costs(self):
        """Test setting static costs"""
        planner = Planner4D((10, 10), 5)
        
        cost_grid = np.random.rand(10, 10) + 1.0
        planner.set_static_costs(cost_grid)
        
        assert np.array_equal(planner.static_cost, cost_grid)
    
    def test_set_feasible_mask(self):
        """Test setting feasible mask"""
        planner = Planner4D((10, 10), 5)
        
        mask = np.ones((10, 10), dtype=bool)
        mask[5, 5] = False  # One infeasible cell
        
        planner.set_feasible_mask(mask)
        
        assert planner.feasible[0, 0] == True
        assert planner.feasible[5, 5] == False
    
    def test_simple_4d_planning(self):
        """Test simple 4D path planning"""
        planner = Planner4D((10, 10), 10, time_resolution=1.0)
        
        # Set uniform costs
        planner.set_static_costs(np.ones((10, 10)))
        
        # Make dynamic costs vary with time (prefer later times)
        for t in range(10):
            planner.dynamic_cost[:, :, t] = 1.0 + 0.1 * t
        
        # Plan path
        path = planner.plan(
            start=(0, 0, 0),
            goal=(9, 9)
        )
        
        assert path is not None
        assert len(path) > 0
        assert path[0].x == 0 and path[0].y == 0
        assert path[-1].x == 9 and path[-1].y == 9
    
    def test_planning_with_obstacles(self):
        """Test planning with obstacles"""
        planner = Planner4D((10, 10), 10)
        
        # Create feasible mask with obstacle
        mask = np.ones((10, 10), dtype=bool)
        mask[4:7, 3:8] = False  # Block in the middle
        
        planner.set_feasible_mask(mask)
        
        # Plan around obstacle
        path = planner.plan(
            start=(0, 0, 0),
            goal=(9, 9)
        )
        
        if path:
            # Check no path point is in obstacle
            for node in path:
                assert planner.feasible[node.x, node.y]
    
    def test_time_window_constraint(self):
        """Test planning with arrival time window"""
        planner = Planner4D((5, 5), 20)
        
        # Plan with time window
        path = planner.plan(
            start=(0, 0, 0),
            goal=(4, 4),
            time_window=(10, 15)  # Must arrive between t=10 and t=15
        )
        
        if path:
            arrival_time = path[-1].t
            assert 10 <= arrival_time <= 15
    
    def test_extract_trajectory(self):
        """Test trajectory extraction"""
        planner = Planner4D((5, 5), 10)
        
        # Create simple path
        path = [
            Node4D(0, 0, 0, g=0.0),
            Node4D(1, 1, 1, g=1.0),
            Node4D(2, 2, 2, g=2.0)
        ]
        
        start_time = datetime(2025, 1, 1, 12, 0)
        trajectory = planner.extract_trajectory(path, start_time)
        
        assert len(trajectory['waypoints']) == 3
        assert len(trajectory['times']) == 3
        assert trajectory['times'][0] == start_time
        assert trajectory['times'][1] == start_time + timedelta(seconds=600)  # Default resolution
    
    def test_find_optimal_departure(self):
        """Test finding optimal departure time"""
        planner = Planner4D((5, 5), 20)
        
        # Set costs that vary with time
        for t in range(20):
            # Lower cost at certain times (simulating tide windows)
            if 5 <= t <= 10:
                planner.dynamic_cost[:, :, t] = 0.5
            else:
                planner.dynamic_cost[:, :, t] = 2.0
        
        # Find optimal departure
        result = planner.find_optimal_departure(
            start=(0, 0),
            goal=(4, 4),
            time_range=(datetime(2025, 1, 1, 0, 0), datetime(2025, 1, 1, 6, 0))
        )
        
        assert result['status'] in ['success', 'no_feasible_departure']
        
        if result['status'] == 'success':
            assert 'optimal' in result
            assert 'alternatives' in result
            assert len(result['alternatives']) > 0
    
    def test_4d_neighbors(self):
        """Test 4D neighbor generation"""
        planner = Planner4D((10, 10), 10)
        
        node = Node4D(5, 5, 3)
        neighbors = planner._get_neighbors_4d(node)
        
        # Should have 9 neighbors (8 spatial + 1 wait)
        assert len(neighbors) == 9
        
        # All neighbors should advance in time
        for neighbor in neighbors:
            assert neighbor.t == node.t + 1
        
        # Check wait-in-place option exists
        wait_nodes = [n for n in neighbors if n.x == 5 and n.y == 5]
        assert len(wait_nodes) == 1