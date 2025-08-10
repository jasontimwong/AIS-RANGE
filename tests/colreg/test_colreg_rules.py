#!/usr/bin/env python3
"""
Tests for COLREG Rules Implementation
"""

import pytest
import numpy as np
from datetime import datetime

from lib.colreg import (
    COLREGRules,
    COLREGValidator,
    Vessel,
    VesselType,
    NavigationStatus,
    EncounterType,
    ActionType,
    Visibility,
    format_colreg_report
)


class TestCOLREGRules:
    """Test COLREG rules implementation"""
    
    def setup_method(self):
        """Setup test fixtures"""
        self.rules = COLREGRules(safety_distance_nm=1.0, safety_time_min=10.0)
        
        # Create test vessels
        self.own_vessel = Vessel(
            mmsi="123456789",
            position=(37.8, -122.5),
            speed=10.0,
            course=90.0,
            heading=90.0,
            vessel_type=VesselType.POWER_DRIVEN,
            nav_status=NavigationStatus.UNDERWAY_USING_ENGINE,
            length=200.0,
            beam=32.0,
            draft=10.0
        )
    
    def test_cpa_calculation_head_on(self):
        """Test CPA calculation for head-on situation"""
        target = Vessel(
            mmsi="987654321",
            position=(37.8, -122.4),  # East of own vessel
            speed=10.0,
            course=270.0,  # Reciprocal course
            heading=270.0
        )
        
        cpa_data = self.rules._calculate_cpa(self.own_vessel, target)
        
        assert cpa_data.distance < 0.5  # Should be very close CPA
        assert cpa_data.time > 0  # Should have positive TCPA
        assert cpa_data.crossing_situation == "ahead"
    
    def test_cpa_calculation_crossing_starboard(self):
        """Test CPA calculation for crossing situation with target on starboard"""
        # Own vessel heading East (90°)
        # To have target on starboard, it should be South-East of our position
        target = Vessel(
            mmsi="987654321",
            position=(37.75, -122.45),  # Southeast of own vessel
            speed=12.0,
            course=315.0,  # Northwest course (will cross ahead)
            heading=315.0
        )
        
        cpa_data = self.rules._calculate_cpa(self.own_vessel, target)
        
        assert cpa_data.crossing_situation == "starboard"
        assert cpa_data.time > 0
    
    def test_cpa_calculation_overtaking(self):
        """Test CPA calculation for overtaking situation"""
        # Own vessel behind and faster
        self.own_vessel.position = (37.8, -122.52)  # West (behind when going East)
        self.own_vessel.speed = 15.0  # Faster
        
        target = Vessel(
            mmsi="987654321",
            position=(37.8, -122.5),  # Ahead of own vessel
            speed=8.0,
            course=90.0,  # Same course but slower
            heading=90.0
        )
        
        cpa_data = self.rules._calculate_cpa(self.own_vessel, target)
        
        # Target should be ahead of us since we're overtaking
        assert cpa_data.crossing_situation == "ahead"
        assert cpa_data.time > 0
    
    def test_risk_assessment_no_risk(self):
        """Test risk assessment when no collision risk exists"""
        target = Vessel(
            mmsi="987654321",
            position=(37.9, -122.4),  # Well clear
            speed=10.0,
            course=0.0,  # North course
            heading=0.0
        )
        
        assessment = self.rules.assess_situation(self.own_vessel, target)
        
        assert assessment.encounter_type == EncounterType.NO_RISK
        assert assessment.risk_level == "none"
        assert 7 in assessment.applicable_rules  # Rule 7 always applies
    
    def test_head_on_situation(self):
        """Test Rule 14: Head-on situation"""
        target = Vessel(
            mmsi="987654321",
            position=(37.8, -122.4),
            speed=10.0,
            course=270.0,  # Reciprocal course
            heading=270.0
        )
        
        assessment = self.rules.assess_situation(self.own_vessel, target)
        
        assert assessment.encounter_type == EncounterType.HEAD_ON
        assert 14 in assessment.applicable_rules
        assert assessment.recommended_action == ActionType.ALTER_COURSE_STARBOARD
        assert "starboard" in assessment.own_vessel_obligations[0].lower()
        assert assessment.risk_level == "high"
    
    def test_crossing_give_way(self):
        """Test Rule 15: Crossing situation where own vessel must give way"""
        # Create a crossing situation where vessels will have close CPA
        # Own vessel at (37.8, -122.5) heading East (90°) at 10 knots
        # Target vessel positioned to cross ahead from starboard
        target = Vessel(
            mmsi="987654321",
            position=(37.79, -122.49),  # Slightly south and east - on starboard
            speed=10.0,
            course=20.0,  # North-northeast course - will cross ahead
            heading=20.0
        )
        
        assessment = self.rules.assess_situation(self.own_vessel, target)
        
        assert assessment.encounter_type == EncounterType.CROSSING
        assert 15 in assessment.applicable_rules
        assert 16 in assessment.applicable_rules  # Give way vessel rules
        assert assessment.recommended_action == ActionType.ALTER_COURSE_STARBOARD
        assert "Give way" in assessment.own_vessel_obligations[0]
    
    def test_crossing_stand_on(self):
        """Test Rule 15/17: Crossing situation where own vessel is stand-on"""
        # Create crossing where target on port must give way to us
        # Own vessel at (37.8, -122.5) heading East (90°) at 10 knots
        # Target positioned to cross from port side
        target = Vessel(
            mmsi="987654321",
            position=(37.81, -122.49),  # Slightly north and east - on port
            speed=10.0,
            course=160.0,  # South-southeast course - will cross ahead
            heading=160.0
        )
        
        assessment = self.rules.assess_situation(self.own_vessel, target)
        
        assert assessment.encounter_type == EncounterType.CROSSING
        assert 15 in assessment.applicable_rules
        assert 17 in assessment.applicable_rules  # Stand-on vessel rules
        assert assessment.recommended_action == ActionType.MAINTAIN_COURSE
        assert "Stand-on" in assessment.own_vessel_obligations[0]
    
    def test_overtaking_situation(self):
        """Test Rule 13: Overtaking situation"""
        # Make own vessel faster and behind target
        self.own_vessel.speed = 15.0
        self.own_vessel.position = (37.8, -122.55)  # West of target
        
        target = Vessel(
            mmsi="987654321",
            position=(37.8, -122.5),
            speed=8.0,
            course=90.0,  # Same course but slower
            heading=90.0
        )
        
        assessment = self.rules.assess_situation(self.own_vessel, target)
        
        assert assessment.encounter_type == EncounterType.OVERTAKING
        assert 13 in assessment.applicable_rules
        assert assessment.recommended_action in [ActionType.ALTER_COURSE_PORT, 
                                                 ActionType.ALTER_COURSE_STARBOARD]
        assert "overtaken" in assessment.own_vessel_obligations[0].lower()
    
    def test_restricted_visibility(self):
        """Test Rule 19: Restricted visibility"""
        target = Vessel(
            mmsi="987654321",
            position=(37.81, -122.49),
            speed=10.0,
            course=180.0,
            heading=180.0
        )
        
        # Test with fog conditions
        assessment = self.rules.assess_situation(
            self.own_vessel, 
            target,
            visibility=Visibility.FOG
        )
        
        # In restricted visibility, Rule 19 overrides normal rules
        assessment_fog = self.rules._apply_rule_19(
            self.own_vessel,
            target,
            Visibility.FOG
        )
        
        assert assessment_fog is not None
        assert 19 in assessment_fog.applicable_rules
        assert assessment_fog.recommended_action == ActionType.REDUCE_SPEED
        assert "fog signals" in assessment_fog.own_vessel_obligations[1].lower()
    
    def test_action_validation_compliant(self):
        """Test validation of COLREG-compliant actions"""
        # Create give-way situation (target on starboard)
        target = Vessel(
            mmsi="987654321",
            position=(37.79, -122.49),  # On starboard, will cross
            speed=10.0,
            course=20.0,
            heading=20.0
        )
        
        assessment = self.rules.assess_situation(self.own_vessel, target)
        
        # Propose compliant action for give-way vessel
        proposed_action = {
            "course_change": 30,  # Starboard turn as recommended
            "speed_change": 0
        }
        
        is_valid, explanation = self.rules.validate_action(assessment, proposed_action)
        assert is_valid
        assert "complies" in explanation.lower()
    
    def test_action_validation_non_compliant(self):
        """Test validation of non-compliant actions"""
        # Create give-way situation (target on starboard)
        target = Vessel(
            mmsi="987654321",
            position=(37.79, -122.49),  # On starboard
            speed=10.0,
            course=20.0,
            heading=20.0
        )
        
        assessment = self.rules.assess_situation(self.own_vessel, target)
        
        # Propose non-compliant action (port turn when should turn starboard)
        proposed_action = {
            "course_change": -30,  # Port turn - wrong direction!
            "speed_change": 0
        }
        
        is_valid, explanation = self.rules.validate_action(assessment, proposed_action)
        assert not is_valid
        assert "starboard" in explanation.lower()
    
    def test_insufficient_action(self):
        """Test Rule 8: Action must be substantial"""
        # Create give-way situation
        target = Vessel(
            mmsi="987654321",
            position=(37.79, -122.49),  # On starboard
            speed=10.0,
            course=20.0,
            heading=20.0
        )
        
        assessment = self.rules.assess_situation(self.own_vessel, target)
        
        # Propose insufficient action (too small for give-way vessel)
        proposed_action = {
            "course_change": 5,  # Too small for give-way vessel
            "speed_change": 0
        }
        
        is_valid, explanation = self.rules.validate_action(assessment, proposed_action)
        assert not is_valid
        assert "substantial" in explanation.lower()


class TestCOLREGValidator:
    """Test COLREG route validation"""
    
    def setup_method(self):
        """Setup test fixtures"""
        self.validator = COLREGValidator()
        
        self.own_vessel = Vessel(
            mmsi="123456789",
            position=(37.8, -122.5),
            speed=10.0,
            course=90.0,
            heading=90.0,
            length=200.0
        )
        
        self.traffic_vessels = [
            Vessel(
                mmsi="111000001",
                position=(37.82, -122.45),
                speed=12.0,
                course=180.0,
                heading=180.0
            ),
            Vessel(
                mmsi="111000002",
                position=(37.78, -122.42),
                speed=8.0,
                course=270.0,
                heading=270.0
            )
        ]
    
    def test_route_validation_clean(self):
        """Test validation of route with no COLREG violations"""
        # Route that avoids all traffic
        planned_route = [
            (37.8, -122.5),
            (37.8, -122.48),
            (37.8, -122.46),
            (37.8, -122.44),
            (37.8, -122.42),
            (37.8, -122.40)
        ]
        
        violations = self.validator.validate_route(
            planned_route,
            self.own_vessel,
            []  # No traffic for clean test
        )
        
        assert len(violations) == 0
    
    def test_route_validation_with_violations(self):
        """Test validation of route with COLREG violations"""
        # Route that conflicts with traffic
        planned_route = [
            (37.8, -122.5),
            (37.81, -122.48),
            (37.82, -122.46),  # Will conflict with first traffic vessel
            (37.82, -122.44),
            (37.81, -122.42),
            (37.8, -122.40)
        ]
        
        violations = self.validator.validate_route(
            planned_route,
            self.own_vessel,
            self.traffic_vessels
        )
        
        # Should detect violations
        assert len(violations) > 0
        
        # Check violation details
        violation = violations[0]
        assert "waypoint_index" in violation
        assert "target_mmsi" in violation
        assert "encounter_type" in violation
        assert "violated_rules" in violation
        assert "required_action" in violation
    
    def test_report_formatting(self):
        """Test formatting of COLREG assessment report"""
        target = Vessel(
            mmsi="987654321",
            position=(37.8, -122.4),
            speed=10.0,
            course=270.0,
            heading=270.0
        )
        
        assessment = self.validator.rules.assess_situation(self.own_vessel, target)
        report = format_colreg_report(assessment)
        
        assert "COLREG ASSESSMENT REPORT" in report
        assert "Encounter Type:" in report
        assert "Risk Level:" in report
        assert "Applicable Rules:" in report
        assert "Own Vessel Obligations:" in report
        assert "Recommended Action:" in report


class TestSpecificScenarios:
    """Test specific COLREG scenarios from requirements"""
    
    def setup_method(self):
        """Setup test fixtures"""
        self.rules = COLREGRules()
    
    def test_sf_bay_crossing_scenario(self):
        """Test San Francisco Bay crossing scenario"""
        own_vessel = Vessel(
            mmsi="123456789",
            position=(37.8, -122.5),
            speed=12.0,
            course=45.0,  # Northeast
            heading=45.0,
            length=200.0
        )
        
        # Position target for crossing, not head-on
        # Target crosses from our starboard side
        target = Vessel(
            mmsi="111000001",
            position=(37.79, -122.49),  # Southeast of us
            speed=10.0,
            course=315.0,  # Northwest - crossing course
            heading=315.0
        )
        
        assessment = self.rules.assess_situation(own_vessel, target)
        
        # Should be a crossing situation
        assert assessment.encounter_type == EncounterType.CROSSING
        assert assessment.risk_level in ["high", "medium"]
    
    def test_narrow_channel_scenario(self):
        """Test narrow channel scenario (Rule 9 related)"""
        own_vessel = Vessel(
            mmsi="123456789",
            position=(37.8, -122.5),
            speed=8.0,
            course=90.0,
            heading=90.0,
            length=300.0  # Large vessel
        )
        
        target = Vessel(
            mmsi="111000001",
            position=(37.8, -122.48),
            speed=6.0,
            course=270.0,
            heading=270.0,
            length=50.0  # Small vessel
        )
        
        assessment = self.rules.assess_situation(own_vessel, target)
        
        # Should detect head-on in narrow waters
        assert assessment.encounter_type == EncounterType.HEAD_ON
        assert assessment.recommended_action == ActionType.ALTER_COURSE_STARBOARD
    
    def test_tss_compliance(self):
        """Test Traffic Separation Scheme compliance (Rule 10)"""
        tss_requirements = self.rules._apply_rule_10(None, None, is_tss=True)
        
        assert "tss_obligations" in tss_requirements
        assert len(tss_requirements["tss_obligations"]) > 0
        assert "traffic lane" in tss_requirements["tss_obligations"][0]


if __name__ == "__main__":
    pytest.main([__file__, "-v"])