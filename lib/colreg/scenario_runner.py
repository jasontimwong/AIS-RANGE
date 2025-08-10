#!/usr/bin/env python3
"""
COLREG Scenario Runner

Executes and validates COLREG scenarios from YAML files.
"""

import yaml
import json
from pathlib import Path
from typing import Dict, List, Any, Optional, Tuple
from datetime import datetime
import logging

from .rules import (
    COLREGRules,
    COLREGValidator,
    Vessel,
    VesselType,
    NavigationStatus,
    EncounterType,
    Visibility,
    format_colreg_report
)

logger = logging.getLogger(__name__)


class COLREGScenario:
    """Represents a COLREG test scenario"""
    
    def __init__(self, scenario_path: str):
        """
        Load scenario from YAML file
        
        Args:
            scenario_path: Path to scenario YAML file
        """
        self.path = Path(scenario_path)
        with open(self.path, 'r') as f:
            self.config = yaml.safe_load(f)
        
        self.name = self.config['meta']['name']
        self.version = self.config['meta'].get('version', 0)
        self.ownship = self._parse_vessel(self.config['ownship'], "ownship")
        self.targets = [self._parse_target(t) for t in self.config.get('targets', [])]
        self.params = self.config.get('params', {})
        self.expectation = self.config.get('expectation', {})
    
    def _parse_vessel(self, vessel_data: Dict, mmsi: str = "123456789") -> Vessel:
        """Parse vessel data from config"""
        return Vessel(
            mmsi=mmsi,
            position=(
                vessel_data.get('lat', 37.8),
                vessel_data.get('lon', -122.5)
            ),
            speed=vessel_data.get('sog', 10.0),
            course=vessel_data.get('cog', 90.0),
            heading=vessel_data.get('heading', vessel_data.get('cog', 90.0)),
            length=vessel_data.get('length_m', 200.0),
            beam=vessel_data.get('beam_m', 32.0),
            draft=vessel_data.get('draft_m', 10.0),
            vessel_type=VesselType.POWER_DRIVEN,
            nav_status=NavigationStatus.UNDERWAY_USING_ENGINE
        )
    
    def _parse_target(self, target_data: Dict) -> Vessel:
        """Parse target vessel from config"""
        return Vessel(
            mmsi=str(target_data.get('mmsi', '111000001')),
            position=(target_data['lat'], target_data['lon']),
            speed=target_data.get('sog', 10.0),
            course=target_data.get('cog', 0.0),
            heading=target_data.get('heading', target_data.get('cog', 0.0)),
            length=target_data.get('length_m', 150.0),
            beam=target_data.get('beam_m', 25.0),
            draft=target_data.get('draft_m', 8.0),
            vessel_type=VesselType.POWER_DRIVEN,
            nav_status=NavigationStatus.UNDERWAY_USING_ENGINE
        )


class COLREGScenarioRunner:
    """Runs and validates COLREG scenarios"""
    
    def __init__(self):
        """Initialize scenario runner"""
        self.rules = COLREGRules(
            safety_distance_nm=1.0,
            safety_time_min=10.0
        )
        self.validator = COLREGValidator(self.rules)
    
    def run_scenario(self, scenario: COLREGScenario) -> Dict[str, Any]:
        """
        Run a single COLREG scenario
        
        Args:
            scenario: COLREGScenario to execute
            
        Returns:
            Dictionary with scenario results
        """
        results = {
            'scenario': scenario.name,
            'timestamp': datetime.now().isoformat(),
            'assessments': [],
            'violations': [],
            'recommendations': [],
            'passed': True
        }
        
        # Assess each target vessel
        for target in scenario.targets:
            assessment = self.rules.assess_situation(
                scenario.ownship,
                target,
                visibility=Visibility.GOOD  # Could be parameterized
            )
            
            # Store assessment
            assessment_data = {
                'target_mmsi': target.mmsi,
                'encounter_type': assessment.encounter_type.name,
                'risk_level': assessment.risk_level,
                'applicable_rules': assessment.applicable_rules,
                'recommended_action': assessment.recommended_action.name,
                'own_obligations': assessment.own_vessel_obligations,
                'target_obligations': assessment.target_vessel_obligations,
                'explanation': assessment.explanation
            }
            
            if assessment.action_details:
                assessment_data['action_details'] = assessment.action_details
            
            if assessment.sound_signals:
                assessment_data['sound_signals'] = assessment.sound_signals
            
            results['assessments'].append(assessment_data)
            
            # Check for violations
            if assessment.risk_level in ['high', 'medium']:
                if assessment.recommended_action.name != 'MAINTAIN_COURSE':
                    violation = {
                        'target_mmsi': target.mmsi,
                        'type': 'COLLISION_RISK',
                        'rules': assessment.applicable_rules,
                        'required_action': assessment.recommended_action.name,
                        'explanation': assessment.explanation
                    }
                    results['violations'].append(violation)
            
            # Add recommendations
            if assessment.recommended_action.name != 'MAINTAIN_COURSE':
                recommendation = {
                    'target_mmsi': target.mmsi,
                    'action': assessment.recommended_action.name,
                    'details': assessment.action_details,
                    'explanation': assessment.explanation
                }
                results['recommendations'].append(recommendation)
        
        # Check expectations
        if scenario.expectation:
            expected_violations = scenario.expectation.get('violations', 0)
            actual_violations = len(results['violations'])
            
            if expected_violations != actual_violations:
                results['passed'] = False
                results['failure_reason'] = (
                    f"Expected {expected_violations} violations, "
                    f"got {actual_violations}"
                )
        
        return results
    
    def run_all_scenarios(self, scenario_dir: str) -> List[Dict[str, Any]]:
        """
        Run all scenarios in a directory
        
        Args:
            scenario_dir: Directory containing scenario YAML files
            
        Returns:
            List of scenario results
        """
        scenario_path = Path(scenario_dir)
        results = []
        
        for yaml_file in scenario_path.glob("*.yaml"):
            try:
                scenario = COLREGScenario(yaml_file)
                result = self.run_scenario(scenario)
                results.append(result)
                
                logger.info(f"Scenario '{scenario.name}': {'PASSED' if result['passed'] else 'FAILED'}")
                
            except Exception as e:
                logger.error(f"Failed to run scenario {yaml_file}: {e}")
                results.append({
                    'scenario': yaml_file.stem,
                    'passed': False,
                    'error': str(e)
                })
        
        return results
    
    def generate_report(self, results: List[Dict[str, Any]]) -> str:
        """
        Generate a human-readable report from scenario results
        
        Args:
            results: List of scenario results
            
        Returns:
            Formatted report string
        """
        report = []
        report.append("=" * 70)
        report.append("COLREG SCENARIO TEST REPORT")
        report.append("=" * 70)
        report.append(f"Timestamp: {datetime.now().isoformat()}")
        report.append("")
        
        total = len(results)
        passed = sum(1 for r in results if r.get('passed', False))
        
        report.append(f"Total Scenarios: {total}")
        report.append(f"Passed: {passed}")
        report.append(f"Failed: {total - passed}")
        report.append("")
        
        for result in results:
            report.append("-" * 70)
            report.append(f"Scenario: {result['scenario']}")
            report.append(f"Status: {'✓ PASSED' if result.get('passed') else '✗ FAILED'}")
            
            if 'error' in result:
                report.append(f"Error: {result['error']}")
                continue
            
            if 'failure_reason' in result:
                report.append(f"Failure: {result['failure_reason']}")
            
            report.append("")
            
            # Assessments
            for assessment in result.get('assessments', []):
                report.append(f"  Target {assessment['target_mmsi']}:")
                report.append(f"    Encounter: {assessment['encounter_type']}")
                report.append(f"    Risk: {assessment['risk_level']}")
                report.append(f"    Rules: {', '.join(map(str, assessment['applicable_rules']))}")
                report.append(f"    Action: {assessment['recommended_action']}")
            
            # Recommendations
            if result.get('recommendations'):
                report.append("")
                report.append("  Recommendations:")
                for rec in result['recommendations']:
                    report.append(f"    • {rec['action']}: {rec['explanation']}")
            
            report.append("")
        
        report.append("=" * 70)
        report.append(f"SUMMARY: {passed}/{total} scenarios passed")
        report.append("=" * 70)
        
        return "\n".join(report)
    
    def export_results(self, results: List[Dict[str, Any]], output_path: str):
        """
        Export results to JSON file
        
        Args:
            results: Scenario results
            output_path: Path for output JSON file
        """
        output = {
            'timestamp': datetime.now().isoformat(),
            'summary': {
                'total': len(results),
                'passed': sum(1 for r in results if r.get('passed', False)),
                'failed': sum(1 for r in results if not r.get('passed', False))
            },
            'scenarios': results
        }
        
        with open(output_path, 'w') as f:
            json.dump(output, f, indent=2)
        
        logger.info(f"Results exported to {output_path}")


def main():
    """Main entry point for scenario runner"""
    import argparse
    
    parser = argparse.ArgumentParser(description="Run COLREG scenarios")
    parser.add_argument(
        'scenario_dir',
        help='Directory containing scenario YAML files'
    )
    parser.add_argument(
        '--output',
        default='colreg_results.json',
        help='Output JSON file for results'
    )
    parser.add_argument(
        '--verbose',
        action='store_true',
        help='Enable verbose logging'
    )
    
    args = parser.parse_args()
    
    # Configure logging
    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format='%(asctime)s - %(levelname)s - %(message)s'
    )
    
    # Run scenarios
    runner = COLREGScenarioRunner()
    results = runner.run_all_scenarios(args.scenario_dir)
    
    # Generate report
    report = runner.generate_report(results)
    print(report)
    
    # Export results
    runner.export_results(results, args.output)


if __name__ == "__main__":
    main()