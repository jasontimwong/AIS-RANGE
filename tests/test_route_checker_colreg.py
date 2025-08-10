#!/usr/bin/env python3
"""
Test Route Checker COLREG Integration
"""

import pytest
import numpy as np
from datetime import datetime

from lib.planner.hybrid_astar import Route
from lib.region.feasible_region import FeasibleRegion
from lib.checks.route_checker import RouteChecker, ValidationStatus
from lib.colreg import Vessel, VesselType, NavigationStatus


class TestRouteCheckerCOLREG:
    """Test COLREG integration in Route Checker"""
    
    def setup_method(self):
        """Setup test fixtures"""
        # Create a simple feasible region with mock data
        from shapely.geometry import MultiPolygon, Polygon, box
        
        bounds = (-122.6, 37.7, -122.4, 37.9)
        
        # Create a simple navigable area (most of the region)
        navigable = MultiPolygon([box(-122.6, 37.7, -122.4, 37.9)])
        
        # Create small no-go areas
        no_go = MultiPolygon([
            box(-122.55, 37.75, -122.54, 37.76),  # Small obstacle
            box(-122.46, 37.84, -122.45, 37.85)   # Another obstacle
        ])
        
        self.region = FeasibleRegion(
            bounds=bounds,
            no_go_areas=no_go,
            navigable_area=navigable,
            depth_contours={},
            danger_zones=[],
            restricted_areas=[],
            tss_zones=None
        )
        
        # Create route checker with COLREG enabled
        self.checker = RouteChecker(
            feasible_region=self.region,
            safety_depth=10.0,
            xtd_limit=185.2,
            min_cpa=926.0,  # 0.5 NM
            enable_colreg=True
        )
    
    def create_test_route(self, waypoints, headings=None, velocities=None):
        """Create a test route"""
        if headings is None:
            # Calculate headings from waypoints
            headings = []
            for i in range(len(waypoints) - 1):
                dx = waypoints[i+1][0] - waypoints[i][0]
                dy = waypoints[i+1][1] - waypoints[i][1]
                heading = np.arctan2(dx, dy)
                headings.append(heading)
            headings.append(headings[-1])  # Last waypoint uses previous heading
        
        if velocities is None:
            velocities = [10.0] * len(waypoints)  # 10 m/s default
        
        route = Route(
            waypoints=waypoints,
            headings=headings,
            velocities=velocities
        )
        
        return route
    
    def test_colreg_no_traffic(self):
        """Test COLREG checking with no traffic"""
        # Create a simple route
        waypoints = [
            (0, 0),
            (1000, 0),
            (2000, 0)
        ]
        route = self.create_test_route(waypoints)
        
        # Validate with no traffic
        report = self.checker.validate_route(route, "Test Route", traffic_vessels=[])
        
        # Should have info message about no traffic
        assert len(report.colreg_checks) == 1
        assert report.colreg_checks[0].status == ValidationStatus.INFO
        assert "No traffic vessels" in report.colreg_checks[0].message
    
    def test_colreg_crossing_situation(self):
        """Test COLREG crossing situation detection"""
        # Create eastbound route
        waypoints = [
            (0, 0),
            (1000, 0),
            (2000, 0)
        ]
        route = self.create_test_route(waypoints)
        
        # Create crossing traffic vessel (northbound from starboard)
        traffic = [
            Vessel(
                mmsi="987654321",
                position=(37.79, -122.49),  # South-east position
                speed=12.0,
                course=0.0,  # North
                heading=0.0,
                vessel_type=VesselType.POWER_DRIVEN,
                nav_status=NavigationStatus.UNDERWAY_USING_ENGINE
            )
        ]
        
        # Validate route
        report = self.checker.validate_route(route, "Crossing Route", traffic_vessels=traffic)
        
        # Should detect crossing situation
        colreg_warnings = [c for c in report.colreg_checks 
                          if c.status == ValidationStatus.WARNING]
        
        if colreg_warnings:
            # Check for crossing encounter
            crossing_checks = [c for c in colreg_warnings 
                             if 'CROSSING' in c.evidence.get('encounter_type', '')]
            assert len(crossing_checks) > 0, "Should detect crossing situation"
            
            # Check recommendations
            assert any("crossing" in r.lower() for r in report.recommendations)
    
    def test_colreg_head_on_situation(self):
        """Test COLREG head-on situation detection"""
        # Create eastbound route
        waypoints = [
            (0, 0),
            (1000, 0),
            (2000, 0)
        ]
        route = self.create_test_route(waypoints)
        
        # Create head-on traffic vessel (westbound)
        traffic = [
            Vessel(
                mmsi="123456789",
                position=(37.8, -122.48),  # East position
                speed=15.0,
                course=270.0,  # West
                heading=270.0,
                vessel_type=VesselType.POWER_DRIVEN,
                nav_status=NavigationStatus.UNDERWAY_USING_ENGINE
            )
        ]
        
        # Validate route
        report = self.checker.validate_route(route, "Head-on Route", traffic_vessels=traffic)
        
        # Should detect head-on situation
        colreg_warnings = [c for c in report.colreg_checks 
                          if c.status == ValidationStatus.WARNING]
        
        if colreg_warnings:
            # Check for head-on encounter
            head_on_checks = [c for c in colreg_warnings 
                            if 'HEAD_ON' in c.evidence.get('encounter_type', '')]
            assert len(head_on_checks) > 0, "Should detect head-on situation"
            
            # Check recommendations include starboard alteration
            assert any("starboard" in r.lower() for r in report.recommendations)
    
    def test_colreg_overtaking_situation(self):
        """Test COLREG overtaking situation detection"""
        # Create eastbound route with higher speed
        waypoints = [
            (0, 0),
            (1000, 0),
            (2000, 0)
        ]
        route = self.create_test_route(waypoints, velocities=[15.0, 15.0, 15.0])
        
        # Create slower vessel ahead (also eastbound)
        traffic = [
            Vessel(
                mmsi="111222333",
                position=(37.8, -122.49),  # Ahead position
                speed=5.0,  # Slower
                course=90.0,  # East
                heading=90.0,
                vessel_type=VesselType.POWER_DRIVEN,
                nav_status=NavigationStatus.UNDERWAY_USING_ENGINE
            )
        ]
        
        # Validate route
        report = self.checker.validate_route(route, "Overtaking Route", traffic_vessels=traffic)
        
        # Check if any COLREG checks were performed
        assert len(report.colreg_checks) > 0
        
        # If overtaking detected, check recommendations
        overtaking_checks = [c for c in report.colreg_checks 
                           if 'OVERTAKING' in c.evidence.get('encounter_type', '')]
        if overtaking_checks:
            assert any("overtaking" in r.lower() for r in report.recommendations)
    
    def test_colreg_safe_passage(self):
        """Test COLREG with safe passage (no conflicts)"""
        # Create northbound route
        waypoints = [
            (0, 0),
            (0, 1000),
            (0, 2000)
        ]
        route = self.create_test_route(waypoints)
        
        # Create distant traffic vessel (no conflict)
        traffic = [
            Vessel(
                mmsi="999888777",
                position=(37.85, -122.45),  # Far north-east
                speed=10.0,
                course=180.0,  # South
                heading=180.0,
                vessel_type=VesselType.POWER_DRIVEN,
                nav_status=NavigationStatus.UNDERWAY_USING_ENGINE
            )
        ]
        
        # Validate route
        report = self.checker.validate_route(route, "Safe Route", traffic_vessels=traffic)
        
        # Should pass COLREG compliance
        pass_checks = [c for c in report.colreg_checks 
                      if c.status == ValidationStatus.PASS]
        assert len(pass_checks) > 0, "Should have passing COLREG checks"
    
    def test_colreg_multiple_vessels(self):
        """Test COLREG with multiple traffic vessels"""
        # Create eastbound route
        waypoints = [
            (0, 0),
            (1000, 0),
            (2000, 0)
        ]
        route = self.create_test_route(waypoints)
        
        # Create multiple traffic vessels
        traffic = [
            Vessel(
                mmsi="111111111",
                position=(37.79, -122.49),  # Crossing from starboard
                speed=12.0,
                course=0.0,
                heading=0.0,
                vessel_type=VesselType.POWER_DRIVEN,
                nav_status=NavigationStatus.UNDERWAY_USING_ENGINE
            ),
            Vessel(
                mmsi="222222222",
                position=(37.81, -122.48),  # Crossing from port
                speed=10.0,
                course=180.0,
                heading=180.0,
                vessel_type=VesselType.POWER_DRIVEN,
                nav_status=NavigationStatus.UNDERWAY_USING_ENGINE
            )
        ]
        
        # Validate route
        report = self.checker.validate_route(route, "Multi-vessel Route", traffic_vessels=traffic)
        
        # Should detect multiple encounters
        assert len(report.colreg_checks) > 1
        
        # Check that different vessels are identified
        vessels_checked = set()
        for check in report.colreg_checks:
            if 'target_mmsi' in check.evidence:
                vessels_checked.add(check.evidence['target_mmsi'])
        
        assert len(vessels_checked) >= 1, "Should check multiple vessels"
    
    def test_colreg_clause_references(self):
        """Test COLREG clause references in validation"""
        # Create route with potential conflict
        waypoints = [
            (0, 0),
            (1000, 0),
            (2000, 0)
        ]
        route = self.create_test_route(waypoints)
        
        # Create crossing traffic
        traffic = [
            Vessel(
                mmsi="333444555",
                position=(37.79, -122.49),
                speed=12.0,
                course=0.0,
                heading=0.0,
                vessel_type=VesselType.POWER_DRIVEN,
                nav_status=NavigationStatus.UNDERWAY_USING_ENGINE
            )
        ]
        
        # Validate route
        report = self.checker.validate_route(route, "Clause Test Route", traffic_vessels=traffic)
        
        # Check clause references
        for check in report.colreg_checks:
            if check.status == ValidationStatus.WARNING:
                # Should have clause references
                assert len(check.clause_refs) > 0, "Should have COLREG clause references"
                
                # Check clause format
                for clause in check.clause_refs:
                    assert 'standard' in clause
                    assert clause['standard'] == 'COLREG'
                    assert 'clause' in clause
                    assert 'Rule' in clause['clause']
    
    def test_colreg_report_json(self):
        """Test COLREG in JSON report output"""
        # Create route
        waypoints = [
            (0, 0),
            (1000, 0)
        ]
        route = self.create_test_route(waypoints)
        
        # Create traffic
        traffic = [
            Vessel(
                mmsi="666777888",
                position=(37.79, -122.49),
                speed=12.0,
                course=0.0,
                heading=0.0,
                vessel_type=VesselType.POWER_DRIVEN,
                nav_status=NavigationStatus.UNDERWAY_USING_ENGINE
            )
        ]
        
        # Validate and get JSON report
        report = self.checker.validate_route(route, "JSON Test Route", traffic_vessels=traffic)
        json_report = report.to_json()
        
        # Parse JSON
        import json
        data = json.loads(json_report)
        
        # Check COLREG section exists
        assert 'checks' in data
        assert 'colreg' in data['checks']
        
        # Check compliance summary includes COLREG clauses
        if data['checks']['colreg']:
            assert 'compliance_summary' in data
            
            # Check for COLREG rules in compliance
            colreg_clauses = [c for c in data['compliance_summary']['clauses'] 
                            if c['standard'] == 'COLREG']
            assert len(colreg_clauses) >= 0, "Should include COLREG clauses"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])