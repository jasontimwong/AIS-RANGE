#!/usr/bin/env python3
"""
COLREG Golden Sample Tests
Standardized test cases for COLREG compliance validation.
These tests serve as reference implementation for approval testing.
"""

import pytest
import json
import numpy as np
from pathlib import Path
from datetime import datetime
from typing import List, Dict, Any

from lib.colreg import (
    COLREGRules,
    COLREGValidator, 
    Vessel,
    VesselType,
    NavigationStatus,
    EncounterType,
    ActionType
)
from lib.colreg.scenario_runner import (
    COLREGScenario,
    COLREGScenarioRunner
)


class TestCOLREGGoldenSamples:
    """Golden sample tests for COLREG compliance"""
    
    @pytest.fixture
    def colreg_rules(self):
        """Create COLREG rules instance"""
        return COLREGRules(safety_distance_nm=1.0, safety_time_min=10.0)
    
    @pytest.fixture
    def validator(self, colreg_rules):
        """Create COLREG validator"""
        return COLREGValidator(colreg_rules)
    
    def test_golden_crossing_give_way(self, colreg_rules):
        """Golden test: Crossing situation where own vessel must give way"""
        # Own vessel heading East
        own_vessel = Vessel(
            mmsi="GOLDEN_OWN_1",
            position=(37.8, -122.5),
            speed=12.0,
            course=90.0,  # East
            heading=90.0,
            vessel_type=VesselType.POWER_DRIVEN,
            nav_status=NavigationStatus.UNDERWAY_USING_ENGINE
        )
        
        # Target vessel crossing from starboard
        target = Vessel(
            mmsi="GOLDEN_TGT_1",
            position=(37.79, -122.49),  # South-East of own vessel
            speed=10.0,
            course=0.0,  # North
            heading=0.0,
            vessel_type=VesselType.POWER_DRIVEN,
            nav_status=NavigationStatus.UNDERWAY_USING_ENGINE
        )
        
        # Assess situation
        assessment = colreg_rules.assess_situation(own_vessel, target)
        
        # Golden assertions
        assert assessment.encounter_type == EncounterType.CROSSING
        # Check if give-way in obligations
        is_give_way = any("Give-way" in obligation for obligation in assessment.own_vessel_obligations)
        assert is_give_way == True
        assert assessment.recommended_action in [
            ActionType.ALTER_COURSE_STARBOARD,
            ActionType.REDUCE_SPEED
        ]
        assert 15 in assessment.applicable_rules  # Rule 15: Crossing
        assert 16 in assessment.applicable_rules  # Rule 16: Give-way vessel
        assert assessment.risk_level in ['high', 'medium']
        
        # Store golden result
        self._store_golden_result("crossing_give_way", assessment)
    
    def test_golden_crossing_stand_on(self, colreg_rules):
        """Golden test: Crossing situation where own vessel is stand-on"""
        # Own vessel heading North
        own_vessel = Vessel(
            mmsi="GOLDEN_OWN_2",
            position=(37.8, -122.5),
            speed=12.0,
            course=0.0,  # North
            heading=0.0,
            vessel_type=VesselType.POWER_DRIVEN,
            nav_status=NavigationStatus.UNDERWAY_USING_ENGINE
        )
        
        # Target vessel crossing from port
        target = Vessel(
            mmsi="GOLDEN_TGT_2",
            position=(37.79, -122.51),  # South-West of own vessel
            speed=10.0,
            course=90.0,  # East
            heading=90.0,
            vessel_type=VesselType.POWER_DRIVEN,
            nav_status=NavigationStatus.UNDERWAY_USING_ENGINE
        )
        
        # Assess situation
        assessment = colreg_rules.assess_situation(own_vessel, target)
        
        # Golden assertions
        assert assessment.encounter_type == EncounterType.CROSSING
        assert assessment.own_is_give_way == False
        assert assessment.recommended_action == ActionType.MAINTAIN_COURSE
        assert 15 in assessment.applicable_rules  # Rule 15: Crossing
        assert 17 in assessment.applicable_rules  # Rule 17: Stand-on vessel
        
        # Store golden result
        self._store_golden_result("crossing_stand_on", assessment)
    
    def test_golden_head_on(self, colreg_rules):
        """Golden test: Head-on situation"""
        # Own vessel heading East
        own_vessel = Vessel(
            mmsi="GOLDEN_OWN_3",
            position=(37.8, -122.5),
            speed=15.0,
            course=90.0,  # East
            heading=90.0,
            vessel_type=VesselType.POWER_DRIVEN,
            nav_status=NavigationStatus.UNDERWAY_USING_ENGINE
        )
        
        # Target vessel heading West (reciprocal course)
        target = Vessel(
            mmsi="GOLDEN_TGT_3",
            position=(37.8, -122.48),  # East of own vessel
            speed=15.0,
            course=270.0,  # West
            heading=270.0,
            vessel_type=VesselType.POWER_DRIVEN,
            nav_status=NavigationStatus.UNDERWAY_USING_ENGINE
        )
        
        # Assess situation
        assessment = colreg_rules.assess_situation(own_vessel, target)
        
        # Golden assertions
        assert assessment.encounter_type == EncounterType.HEAD_ON
        assert assessment.own_is_give_way == True  # Both must give way
        assert assessment.recommended_action == ActionType.ALTER_COURSE_STARBOARD
        assert 14 in assessment.applicable_rules  # Rule 14: Head-on
        assert assessment.risk_level == 'high'
        
        # Store golden result
        self._store_golden_result("head_on", assessment)
    
    def test_golden_overtaking_own_overtakes(self, colreg_rules):
        """Golden test: Own vessel overtaking"""
        # Own vessel heading East (faster)
        own_vessel = Vessel(
            mmsi="GOLDEN_OWN_4",
            position=(37.8, -122.5),
            speed=20.0,  # Faster
            course=90.0,  # East
            heading=90.0,
            vessel_type=VesselType.POWER_DRIVEN,
            nav_status=NavigationStatus.UNDERWAY_USING_ENGINE
        )
        
        # Target vessel ahead, also heading East (slower)
        target = Vessel(
            mmsi="GOLDEN_TGT_4",
            position=(37.8, -122.49),  # Ahead (East)
            speed=8.0,  # Slower
            course=90.0,  # East
            heading=90.0,
            vessel_type=VesselType.POWER_DRIVEN,
            nav_status=NavigationStatus.UNDERWAY_USING_ENGINE
        )
        
        # Assess situation
        assessment = colreg_rules.assess_situation(own_vessel, target)
        
        # Golden assertions
        assert assessment.encounter_type == EncounterType.OVERTAKING
        assert assessment.own_is_give_way == True  # Overtaking vessel gives way
        assert assessment.recommended_action in [
            ActionType.ALTER_COURSE_PORT,
            ActionType.ALTER_COURSE_STARBOARD
        ]
        assert 13 in assessment.applicable_rules  # Rule 13: Overtaking
        
        # Store golden result
        self._store_golden_result("overtaking_own", assessment)
    
    def test_golden_overtaking_being_overtaken(self, colreg_rules):
        """Golden test: Own vessel being overtaken"""
        # Own vessel heading East (slower)
        own_vessel = Vessel(
            mmsi="GOLDEN_OWN_5",
            position=(37.8, -122.5),
            speed=8.0,  # Slower
            course=90.0,  # East
            heading=90.0,
            vessel_type=VesselType.POWER_DRIVEN,
            nav_status=NavigationStatus.UNDERWAY_USING_ENGINE
        )
        
        # Target vessel behind, also heading East (faster)
        target = Vessel(
            mmsi="GOLDEN_TGT_5",
            position=(37.8, -122.51),  # Behind (West)
            speed=20.0,  # Faster
            course=90.0,  # East
            heading=90.0,
            vessel_type=VesselType.POWER_DRIVEN,
            nav_status=NavigationStatus.UNDERWAY_USING_ENGINE
        )
        
        # Assess situation
        assessment = colreg_rules.assess_situation(own_vessel, target)
        
        # Golden assertions
        assert assessment.encounter_type == EncounterType.OVERTAKING
        assert assessment.own_is_give_way == False  # Being overtaken - stand on
        assert assessment.recommended_action == ActionType.MAINTAIN_COURSE
        assert 13 in assessment.applicable_rules  # Rule 13: Overtaking
        
        # Store golden result
        self._store_golden_result("overtaking_target", assessment)
    
    def test_golden_no_risk(self, colreg_rules):
        """Golden test: No risk situation"""
        # Own vessel heading North
        own_vessel = Vessel(
            mmsi="GOLDEN_OWN_6",
            position=(37.8, -122.5),
            speed=12.0,
            course=0.0,  # North
            heading=0.0,
            vessel_type=VesselType.POWER_DRIVEN,
            nav_status=NavigationStatus.UNDERWAY_USING_ENGINE
        )
        
        # Target vessel far away heading South
        target = Vessel(
            mmsi="GOLDEN_TGT_6",
            position=(37.85, -122.45),  # Far North-East
            speed=12.0,
            course=180.0,  # South
            heading=180.0,
            vessel_type=VesselType.POWER_DRIVEN,
            nav_status=NavigationStatus.UNDERWAY_USING_ENGINE
        )
        
        # Assess situation
        assessment = colreg_rules.assess_situation(own_vessel, target)
        
        # Golden assertions
        assert assessment.encounter_type == EncounterType.NO_RISK
        assert assessment.own_is_give_way == False
        assert assessment.recommended_action == ActionType.MAINTAIN_COURSE
        assert assessment.risk_level == 'none'
        
        # Store golden result
        self._store_golden_result("no_risk", assessment)
    
    def test_golden_narrow_channel(self, colreg_rules):
        """Golden test: Narrow channel scenario"""
        # Own vessel in narrow channel
        own_vessel = Vessel(
            mmsi="GOLDEN_OWN_7",
            position=(37.8, -122.5),
            speed=10.0,
            course=90.0,  # East
            heading=90.0,
            vessel_type=VesselType.POWER_DRIVEN,
            nav_status=NavigationStatus.UNDERWAY_USING_ENGINE
        )
        
        # Target vessel approaching in same channel
        target = Vessel(
            mmsi="GOLDEN_TGT_7",
            position=(37.8, -122.48),  # Ahead in channel
            speed=10.0,
            course=270.0,  # West (opposite direction)
            heading=270.0,
            vessel_type=VesselType.POWER_DRIVEN,
            nav_status=NavigationStatus.UNDERWAY_USING_ENGINE
        )
        
        # Assess situation (assuming narrow channel context)
        assessment = colreg_rules.assess_situation(own_vessel, target, in_narrow_channel=True)
        
        # Golden assertions
        assert assessment.encounter_type == EncounterType.HEAD_ON
        assert assessment.recommended_action == ActionType.ALTER_COURSE_STARBOARD
        assert 9 in assessment.applicable_rules or 14 in assessment.applicable_rules
        
        # Store golden result
        self._store_golden_result("narrow_channel", assessment)
    
    def test_golden_tss_compliance(self, colreg_rules):
        """Golden test: TSS compliance scenario"""
        # Own vessel in TSS lane
        own_vessel = Vessel(
            mmsi="GOLDEN_OWN_8",
            position=(37.8, -122.5),
            speed=12.0,
            course=90.0,  # East in TSS
            heading=90.0,
            vessel_type=VesselType.POWER_DRIVEN,
            nav_status=NavigationStatus.UNDERWAY_USING_ENGINE
        )
        
        # Target vessel crossing TSS
        target = Vessel(
            mmsi="GOLDEN_TGT_8",
            position=(37.79, -122.49),  # Crossing from starboard
            speed=8.0,
            course=0.0,  # North (crossing TSS)
            heading=0.0,
            vessel_type=VesselType.POWER_DRIVEN,
            nav_status=NavigationStatus.UNDERWAY_USING_ENGINE
        )
        
        # Assess situation (assuming TSS context)
        assessment = colreg_rules.assess_situation(own_vessel, target, in_tss=True)
        
        # Golden assertions
        # In TSS, vessel in lane generally has priority
        assert assessment.encounter_type in [EncounterType.CROSSING, EncounterType.NO_RISK]
        if assessment.encounter_type == EncounterType.CROSSING:
            # TSS vessel may maintain course
            assert 10 in assessment.applicable_rules or 15 in assessment.applicable_rules
        
        # Store golden result
        self._store_golden_result("tss_compliance", assessment)
    
    def test_golden_restricted_visibility(self, colreg_rules):
        """Golden test: Restricted visibility scenario"""
        # Own vessel in fog
        own_vessel = Vessel(
            mmsi="GOLDEN_OWN_9",
            position=(37.8, -122.5),
            speed=6.0,  # Reduced speed
            course=90.0,
            heading=90.0,
            vessel_type=VesselType.POWER_DRIVEN,
            nav_status=NavigationStatus.UNDERWAY_USING_ENGINE
        )
        
        # Target vessel detected on radar
        target = Vessel(
            mmsi="GOLDEN_TGT_9",
            position=(37.8, -122.48),
            speed=6.0,
            course=270.0,
            heading=270.0,
            vessel_type=VesselType.POWER_DRIVEN,
            nav_status=NavigationStatus.UNDERWAY_USING_ENGINE
        )
        
        # Assess situation in restricted visibility
        from lib.colreg import Visibility
        assessment = colreg_rules.assess_situation(
            own_vessel, target, 
            visibility=Visibility.RESTRICTED
        )
        
        # Golden assertions
        assert 19 in assessment.applicable_rules  # Rule 19: Restricted visibility
        # In restricted visibility, avoid port alteration for vessel forward of beam
        
        # Store golden result
        self._store_golden_result("restricted_visibility", assessment)
    
    def test_golden_multi_vessel_scenario(self, validator):
        """Golden test: Multiple vessel encounter"""
        # Own vessel
        own_vessel = Vessel(
            mmsi="GOLDEN_OWN_10",
            position=(37.8, -122.5),
            speed=12.0,
            course=90.0,
            heading=90.0,
            vessel_type=VesselType.POWER_DRIVEN,
            nav_status=NavigationStatus.UNDERWAY_USING_ENGINE
        )
        
        # Multiple targets
        targets = [
            Vessel(
                mmsi="GOLDEN_TGT_10A",
                position=(37.79, -122.49),  # Crossing from starboard
                speed=10.0,
                course=0.0,
                heading=0.0,
                vessel_type=VesselType.POWER_DRIVEN,
                nav_status=NavigationStatus.UNDERWAY_USING_ENGINE
            ),
            Vessel(
                mmsi="GOLDEN_TGT_10B",
                position=(37.81, -122.49),  # Crossing from port
                speed=8.0,
                course=180.0,
                heading=180.0,
                vessel_type=VesselType.POWER_DRIVEN,
                nav_status=NavigationStatus.UNDERWAY_USING_ENGINE
            )
        ]
        
        # Validate against multiple targets
        validation = validator.validate_route_segment(
            own_vessel, targets,
            segment_start=(37.8, -122.5),
            segment_end=(37.8, -122.48)
        )
        
        # Golden assertions
        assert validation.has_violations == True
        assert len(validation.assessments) == 2
        
        # Priority should be given to starboard crossing vessel
        priority_assessment = validation.get_priority_assessment()
        assert priority_assessment is not None
        
        # Store golden result
        self._store_golden_validation("multi_vessel", validation)
    
    def test_golden_scenario_runner(self):
        """Golden test: Complete scenario execution"""
        runner = COLREGScenarioRunner()
        
        # Run all golden scenarios
        golden_scenarios = [
            "scenarios/colreg/crossing.yaml",
            "scenarios/colreg/head_on.yaml",
            "scenarios/colreg/overtaking.yaml",
            "scenarios/colreg/narrow.yaml",
            "scenarios/colreg/tss_lane.yaml"
        ]
        
        results = []
        for scenario_path in golden_scenarios:
            if Path(scenario_path).exists():
                scenario = COLREGScenario(scenario_path)
                result = runner.run_scenario(scenario)
                results.append(result)
                
                # Golden assertion
                assert result['passed'], f"Golden scenario {scenario_path} failed"
        
        # Generate golden report
        if results:
            report = runner.generate_report(results)
            self._store_golden_report("scenario_runner", report, results)
    
    def _store_golden_result(self, test_name: str, assessment):
        """Store golden test result for future comparison"""
        golden_dir = Path("tests/golden/results")
        golden_dir.mkdir(parents=True, exist_ok=True)
        
        result = {
            "test_name": test_name,
            "timestamp": datetime.now().isoformat(),
            "encounter_type": assessment.encounter_type.name,
            "risk_level": assessment.risk_level,
            "own_is_give_way": assessment.own_is_give_way,
            "recommended_action": assessment.recommended_action.name,
            "applicable_rules": assessment.applicable_rules,
            "explanation": assessment.explanation
        }
        
        with open(golden_dir / f"{test_name}.json", "w") as f:
            json.dump(result, f, indent=2)
    
    def _store_golden_validation(self, test_name: str, validation):
        """Store golden validation result"""
        golden_dir = Path("tests/golden/results")
        golden_dir.mkdir(parents=True, exist_ok=True)
        
        result = {
            "test_name": test_name,
            "timestamp": datetime.now().isoformat(),
            "has_violations": validation.has_violations,
            "num_assessments": len(validation.assessments),
            "high_risk_count": sum(1 for a in validation.assessments if a.risk_level == 'high'),
            "medium_risk_count": sum(1 for a in validation.assessments if a.risk_level == 'medium')
        }
        
        with open(golden_dir / f"{test_name}_validation.json", "w") as f:
            json.dump(result, f, indent=2)
    
    def _store_golden_report(self, test_name: str, report: str, results: List[Dict]):
        """Store golden report"""
        golden_dir = Path("tests/golden/results")
        golden_dir.mkdir(parents=True, exist_ok=True)
        
        # Store report text
        with open(golden_dir / f"{test_name}_report.txt", "w") as f:
            f.write(report)
        
        # Store results summary
        summary = {
            "test_name": test_name,
            "timestamp": datetime.now().isoformat(),
            "total_scenarios": len(results),
            "passed": sum(1 for r in results if r['passed']),
            "failed": sum(1 for r in results if not r['passed'])
        }
        
        with open(golden_dir / f"{test_name}_summary.json", "w") as f:
            json.dump(summary, f, indent=2)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])