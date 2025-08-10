#!/usr/bin/env python3
"""
Test COLREG Scenarios
"""

import pytest
from pathlib import Path

from lib.colreg.scenario_runner import (
    COLREGScenario,
    COLREGScenarioRunner
)


class TestCOLREGScenarios:
    """Test all COLREG scenarios"""
    
    def setup_method(self):
        """Setup test fixtures"""
        self.runner = COLREGScenarioRunner()
        self.scenario_dir = Path("scenarios/colreg")
    
    def test_crossing_scenario(self):
        """Test crossing give-way scenario"""
        scenario = COLREGScenario(self.scenario_dir / "crossing.yaml")
        result = self.runner.run_scenario(scenario)
        
        assert result['passed'], f"Scenario failed: {result.get('failure_reason')}"
        assert len(result['assessments']) == 1
        
        assessment = result['assessments'][0]
        assert assessment['encounter_type'] == 'CROSSING'
        assert assessment['risk_level'] in ['high', 'medium']
        assert 15 in assessment['applicable_rules']
        assert 16 in assessment['applicable_rules']
    
    def test_head_on_scenario(self):
        """Test head-on meeting scenario"""
        scenario = COLREGScenario(self.scenario_dir / "head_on.yaml")
        result = self.runner.run_scenario(scenario)
        
        assert result['passed'], f"Scenario failed: {result.get('failure_reason')}"
        assert len(result['assessments']) == 1
        
        assessment = result['assessments'][0]
        assert assessment['encounter_type'] == 'HEAD_ON'
        assert assessment['risk_level'] == 'high'
        assert 14 in assessment['applicable_rules']
        assert assessment['recommended_action'] == 'ALTER_COURSE_STARBOARD'
    
    def test_overtaking_scenario(self):
        """Test overtaking scenario"""
        scenario = COLREGScenario(self.scenario_dir / "overtaking.yaml")
        result = self.runner.run_scenario(scenario)
        
        assert result['passed'], f"Scenario failed: {result.get('failure_reason')}"
        assert len(result['assessments']) == 1
        
        assessment = result['assessments'][0]
        assert assessment['encounter_type'] == 'OVERTAKING'
        assert 13 in assessment['applicable_rules']
        assert assessment['recommended_action'] in [
            'ALTER_COURSE_PORT', 
            'ALTER_COURSE_STARBOARD'
        ]
    
    def test_narrow_channel_scenario(self):
        """Test narrow channel scenario"""
        scenario = COLREGScenario(self.scenario_dir / "narrow.yaml")
        result = self.runner.run_scenario(scenario)
        
        assert result['passed'], f"Scenario failed: {result.get('failure_reason')}"
        
        # Should detect head-on in narrow channel
        assessment = result['assessments'][0]
        assert assessment['encounter_type'] == 'HEAD_ON'
        assert assessment['recommended_action'] == 'ALTER_COURSE_STARBOARD'
    
    def test_tss_lane_scenario(self):
        """Test TSS lane compliance scenario"""
        scenario = COLREGScenario(self.scenario_dir / "tss_lane.yaml")
        result = self.runner.run_scenario(scenario)
        
        assert result['passed'], f"Scenario failed: {result.get('failure_reason')}"
        
        # TSS crossing situation
        assessment = result['assessments'][0]
        assert assessment['encounter_type'] in ['CROSSING', 'NO_RISK']
        # In TSS, vessel in lane has priority
    
    def test_all_scenarios(self):
        """Test running all scenarios"""
        results = self.runner.run_all_scenarios("scenarios/colreg")
        
        # Should have results for all 5 scenarios
        assert len(results) >= 5
        
        # Check that scenarios were loaded
        scenario_names = {r['scenario'] for r in results}
        expected_names = {
            'Crossing - Give Way',
            'Head-on Meeting',
            'Overtaking Situation',
            'Narrow Channel Meeting',
            'TSS Lane Compliance'
        }
        
        assert expected_names.issubset(scenario_names)
        
        # Generate report
        report = self.runner.generate_report(results)
        assert "COLREG SCENARIO TEST REPORT" in report
        assert "Total Scenarios:" in report
    
    def test_scenario_export(self, tmp_path):
        """Test exporting scenario results"""
        results = self.runner.run_all_scenarios("scenarios/colreg")
        
        output_file = tmp_path / "test_results.json"
        self.runner.export_results(results, str(output_file))
        
        assert output_file.exists()
        
        # Load and check exported data
        import json
        with open(output_file) as f:
            data = json.load(f)
        
        assert 'timestamp' in data
        assert 'summary' in data
        assert 'scenarios' in data
        assert data['summary']['total'] >= 5


if __name__ == "__main__":
    pytest.main([__file__, "-v"])