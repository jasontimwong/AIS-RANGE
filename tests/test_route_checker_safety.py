"""
Test suite for route safety validation
"""

import pytest
import numpy as np
from datetime import datetime
from shapely.geometry import Point, LineString, Polygon, MultiPolygon, box

from lib.checks.route_checker import (
    RouteChecker, RouteValidationReport, ValidationCheck, ValidationStatus
)
from lib.planner.hybrid_astar import Route
from lib.region.feasible_region import FeasibleRegion


class TestRouteChecker:
    """Test route validation functionality."""
    
    @pytest.fixture
    def test_region(self):
        """Create test navigation region."""
        bounds = (0, 0, 1000, 1000)
        
        # Create some no-go areas
        obstacles = [
            box(200, 200, 300, 300),  # Small obstacle
            box(700, 700, 800, 800),  # Another obstacle
        ]
        no_go_areas = MultiPolygon(obstacles)
        
        # Navigable area
        full_area = box(*bounds)
        navigable_area = MultiPolygon([full_area.difference(no_go_areas)])
        
        return FeasibleRegion(
            bounds=bounds,
            no_go_areas=no_go_areas,
            navigable_area=navigable_area,
            depth_contours={10: [], 20: []},
            danger_zones=obstacles,
            restricted_areas=[]
        )
    
    @pytest.fixture
    def safe_route(self):
        """Create a safe test route."""
        waypoints = [
            (100, 100),
            (100, 500),
            (500, 500),
            (500, 900),
            (900, 900)
        ]
        headings = [np.pi/2, np.pi/2, 0, np.pi/2, 0]
        velocities = [10.0] * 5
        
        return Route(
            waypoints=waypoints,
            headings=headings,
            velocities=velocities,
            total_cost=1000.0
        )
    
    @pytest.fixture
    def unsafe_route(self):
        """Create route that goes through obstacle."""
        waypoints = [
            (100, 100),
            (250, 250),  # Inside first obstacle
            (500, 500),
            (750, 750),  # Inside second obstacle
            (900, 900)
        ]
        headings = [np.pi/4] * 5
        velocities = [10.0] * 5
        
        return Route(
            waypoints=waypoints,
            headings=headings,
            velocities=velocities,
            total_cost=1000.0
        )
    
    def test_checker_initialization(self, test_region):
        """Test route checker initialization."""
        checker = RouteChecker(
            feasible_region=test_region,
            safety_depth=10.0,
            xtd_limit=50.0,
            min_cpa=100.0
        )
        
        assert checker.region == test_region
        assert checker.safety_depth == 10.0
        assert checker.xtd_limit == 50.0
        assert checker.min_cpa == 100.0
    
    def test_safe_route_validation(self, test_region, safe_route):
        """Test validation of safe route."""
        checker = RouteChecker(test_region)
        report = checker.validate_route(safe_route, "Safe Route")
        
        assert report.route_name == "Safe Route"
        assert report.is_valid == True
        assert report.failed_checks == 0
        assert len(report.critical_issues) == 0
    
    def test_unsafe_route_validation(self, test_region, unsafe_route):
        """Test validation of unsafe route."""
        checker = RouteChecker(test_region)
        report = checker.validate_route(unsafe_route, "Unsafe Route")
        
        assert report.route_name == "Unsafe Route"
        assert report.is_valid == False
        assert report.failed_checks > 0
        assert len(report.critical_issues) > 0
        
        # Check specific safety failures
        safety_fails = [c for c in report.safety_checks 
                       if c.status == ValidationStatus.FAIL]
        assert len(safety_fails) > 0
    
    def test_no_go_area_check(self, test_region, unsafe_route):
        """Test no-go area detection."""
        checker = RouteChecker(test_region)
        checks = checker._check_no_go_areas(unsafe_route)
        
        # Should detect route enters no-go area
        no_go_check = next((c for c in checks 
                          if c.name == "No-Go Area Avoidance"), None)
        assert no_go_check is not None
        assert no_go_check.status == ValidationStatus.FAIL
        assert no_go_check.severity == "critical"
    
    def test_waypoint_safety_check(self, test_region):
        """Test individual waypoint safety checking."""
        checker = RouteChecker(test_region)
        
        # Create route with waypoint in obstacle
        bad_route = Route(
            waypoints=[(100, 100), (250, 250), (500, 500)],
            headings=[0, 0, 0],
            velocities=[10, 10, 10]
        )
        
        checks = checker._check_no_go_areas(bad_route)
        
        # Should detect waypoint 2 is unsafe
        wp_checks = [c for c in checks if "Waypoint" in c.name]
        assert len(wp_checks) > 0
        assert any(c.waypoint_index == 1 for c in wp_checks)
    
    def test_xtd_corridor_check(self, test_region, safe_route):
        """Test XTD corridor validation."""
        checker = RouteChecker(test_region, xtd_limit=10.0)
        checks = checker._check_xtd_corridor(safe_route)
        
        assert len(checks) > 0
        xtd_check = checks[0]
        assert xtd_check.name == "XTD Corridor Clearance"
        
        # Very narrow corridor might intersect obstacles
        checker_narrow = RouteChecker(test_region, xtd_limit=200.0)
        checks_narrow = checker_narrow._check_xtd_corridor(safe_route)
        # Wider corridor more likely to hit obstacles
    
    def test_turn_radius_check(self, test_region):
        """Test turn radius validation."""
        checker = RouteChecker(test_region)
        
        # Create route with sharp turn
        sharp_route = Route(
            waypoints=[(0, 0), (100, 0), (100, 100)],  # 90-degree turn
            headings=[0, 0, np.pi/2],
            velocities=[10, 10, 10]
        )
        
        checks = checker._check_turn_radius(sharp_route)
        
        # Should detect sharp turn
        turn_warnings = [c for c in checks 
                        if c.status == ValidationStatus.WARNING]
        assert len(turn_warnings) > 0
    
    def test_route_continuity_check(self, test_region):
        """Test route continuity validation."""
        checker = RouteChecker(test_region)
        
        # Create route with very long leg
        long_leg_route = Route(
            waypoints=[(0, 0), (60000, 0)],  # 60km leg
            headings=[0, 0],
            velocities=[10, 10]
        )
        
        checks = checker._check_route_continuity(long_leg_route)
        
        # Should warn about long leg
        warnings = [c for c in checks 
                   if c.status == ValidationStatus.WARNING]
        assert len(warnings) > 0
    
    def test_speed_limit_check(self, test_region, safe_route):
        """Test speed limit validation."""
        checker = RouteChecker(test_region)
        
        # Create route with excessive speed
        fast_route = Route(
            waypoints=safe_route.waypoints,
            headings=safe_route.headings,
            velocities=[25.0] * len(safe_route.waypoints)  # 25 m/s
        )
        
        checks = checker._check_speed_limits(fast_route)
        
        # Should warn about speed
        speed_warnings = [c for c in checks 
                         if c.category == "speed" and 
                         c.status == ValidationStatus.WARNING]
        assert len(speed_warnings) > 0
    
    def test_validation_report_generation(self, test_region, safe_route):
        """Test complete validation report generation."""
        checker = RouteChecker(test_region)
        report = checker.validate_route(safe_route, "Test Route")
        
        assert isinstance(report, RouteValidationReport)
        assert report.route_name == "Test Route"
        assert isinstance(report.validation_time, datetime)
        assert report.total_checks > 0
        assert report.passed_checks >= 0
        assert report.failed_checks >= 0
        assert report.warnings >= 0
        
        # Check report sections
        assert isinstance(report.safety_checks, list)
        assert isinstance(report.geometry_checks, list)
        assert isinstance(report.speed_checks, list)
        
        # Check metrics
        assert "route_length_m" in report.metrics
        assert "waypoint_count" in report.metrics
        assert report.metrics["waypoint_count"] == len(safe_route.waypoints)
    
    def test_report_json_export(self, test_region, safe_route):
        """Test JSON export of validation report."""
        checker = RouteChecker(test_region)
        report = checker.validate_route(safe_route, "JSON Test")
        
        json_str = report.to_json()
        assert json_str is not None
        
        # Parse JSON to check structure
        import json
        data = json.loads(json_str)
        
        assert data["route_name"] == "JSON Test"
        assert "summary" in data
        assert "checks" in data
        assert "metrics" in data
        
        # Check summary fields
        assert data["summary"]["total_checks"] == report.total_checks
        assert data["summary"]["is_valid"] == report.is_valid
    
    def test_min_clearance_calculation(self, test_region, safe_route):
        """Test minimum clearance calculation."""
        checker = RouteChecker(test_region)
        min_clearance = checker._calculate_min_clearance(safe_route)
        
        assert min_clearance >= 0
        assert min_clearance < float('inf')
    
    def test_max_turn_rate_calculation(self, test_region):
        """Test maximum turn rate calculation."""
        checker = RouteChecker(test_region)
        
        # Route with turns
        turning_route = Route(
            waypoints=[(0, 0), (100, 0), (100, 100), (0, 100)],
            headings=[0, 0, np.pi/2, np.pi],
            velocities=[10, 10, 10, 10]
        )
        
        max_turn_rate = checker._calculate_max_turn_rate(turning_route)
        assert max_turn_rate > 0
    
    def test_recommendations_generation(self, test_region, unsafe_route):
        """Test recommendation generation based on issues."""
        checker = RouteChecker(test_region)
        report = checker.validate_route(unsafe_route, "Problem Route")
        
        assert len(report.recommendations) > 0
        assert any("no-go" in r.lower() for r in report.recommendations)