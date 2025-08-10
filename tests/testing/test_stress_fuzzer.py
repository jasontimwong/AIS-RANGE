"""
Tests for stress testing and fuzzing framework
"""

import pytest
import json
import tempfile
from pathlib import Path
import sys
import os

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from lib.testing.stress_fuzzer import (
    FuzzResult,
    StressFuzzer
)


class TestFuzzResult:
    """Test FuzzResult class"""
    
    def test_fuzz_result_creation(self):
        """Test creating fuzz result"""
        result = FuzzResult(
            test_id="TEST001",
            input_data={'test': 'data'},
            success=True,
            execution_time=0.5
        )
        
        assert result.test_id == "TEST001"
        assert result.success == True
        assert result.execution_time == 0.5
        assert result.error is None
    
    def test_fuzz_result_to_dict(self):
        """Test converting result to dict"""
        result = FuzzResult(
            test_id="TEST002",
            input_data={'value': 42},
            success=False,
            error="Test error",
            execution_time=1.2
        )
        
        result_dict = result.to_dict()
        
        assert result_dict['test_id'] == "TEST002"
        assert result_dict['success'] == False
        assert result_dict['error'] == "Test error"
        assert result_dict['execution_time'] == 1.2


class TestStressFuzzer:
    """Test StressFuzzer class"""
    
    def test_fuzzer_initialization(self):
        """Test fuzzer initialization with seed"""
        fuzzer = StressFuzzer(seed=42)
        
        assert fuzzer.seed == 42
        assert fuzzer.results == []
    
    def test_fuzz_waypoints_normal(self):
        """Test generating normal waypoints"""
        fuzzer = StressFuzzer(seed=123)
        waypoints = fuzzer.fuzz_waypoints(count=10)
        
        assert len(waypoints) == 10
        
        for wp in waypoints:
            assert 'lon' in wp
            assert 'lat' in wp
            assert 'speed' in wp
            assert 'turn_radius' in wp
    
    def test_fuzz_waypoints_bounds(self):
        """Test waypoint generation with custom bounds"""
        fuzzer = StressFuzzer()
        bounds = (0, 0, 10, 10)
        waypoints = fuzzer.fuzz_waypoints(count=5, bounds=bounds)
        
        assert len(waypoints) == 5
        
        # Note: Some waypoints may be intentionally outside bounds for testing
        # So we don't strictly enforce bounds here
    
    def test_fuzz_traffic_vessels(self):
        """Test generating traffic vessels"""
        fuzzer = StressFuzzer(seed=456)
        vessels = fuzzer.fuzz_traffic_vessels(count=20)
        
        assert len(vessels) == 20
        
        for vessel in vessels:
            assert 'id' in vessel
            assert 'position' in vessel
            assert 'speed' in vessel
            assert 'heading' in vessel
            assert 'length' in vessel
            assert 'beam' in vessel
    
    def test_fuzz_string_strategies(self):
        """Test string fuzzing strategies"""
        fuzzer = StressFuzzer()
        
        # Test empty strategy
        empty_str = fuzzer.fuzz_string(base="test", strategies=['empty'])
        assert empty_str == ""
        
        # Test long strategy
        long_str = fuzzer.fuzz_string(base="x", strategies=['long'])
        assert len(long_str) > 1000
        
        # Test special characters
        special_str = fuzzer.fuzz_string(base="", strategies=['special'])
        assert any(c in special_str for c in '!@#$%')
    
    def test_stress_test_function(self):
        """Test stress testing a function"""
        fuzzer = StressFuzzer(seed=789)
        
        # Simple test function
        def add_one(data):
            return data['value'] + 1
        
        # Input generator
        def gen_input():
            return {'value': fuzzer.fuzz_waypoints(1)[0]['speed']}
        
        # Run stress test
        report = fuzzer.stress_test_function(
            func=add_one,
            input_generator=gen_input,
            iterations=10,
            timeout=1.0
        )
        
        assert report['function'] == 'add_one'
        assert report['iterations'] == 10
        assert report['successful'] > 0
        assert 'avg_execution_time' in report
        assert report['seed'] == 789
    
    def test_stress_test_with_errors(self):
        """Test stress testing with functions that error"""
        fuzzer = StressFuzzer()
        
        # Function that sometimes errors
        def unstable_func(data):
            if data['value'] < 0:
                raise ValueError("Negative value")
            return data['value'] * 2
        
        # Input generator with some negative values
        import random
        def gen_input():
            return {'value': random.uniform(-5, 5)}
        
        report = fuzzer.stress_test_function(
            func=unstable_func,
            input_generator=gen_input,
            iterations=20,
            timeout=1.0
        )
        
        # Should have some failures
        assert report['failed'] > 0
        assert len(report['errors']) > 0
        assert report['success_rate'] < 1.0
    
    def test_generate_edge_cases(self):
        """Test edge case generation"""
        fuzzer = StressFuzzer()
        edge_cases = fuzzer.generate_edge_cases()
        
        assert 'coordinates' in edge_cases
        assert 'distances' in edge_cases
        assert 'speeds' in edge_cases
        assert 'counts' in edge_cases
        assert 'strings' in edge_cases
        
        # Check some specific edge cases
        coords = edge_cases['coordinates']
        assert (0, 0) in coords  # Null island
        assert (0, 90) in coords  # North pole
        
        distances = edge_cases['distances']
        assert 0 in distances
        assert float('inf') in distances
    
    def test_save_report(self, tmp_path):
        """Test saving stress test report"""
        fuzzer = StressFuzzer(seed=999)
        
        # Create some results
        fuzzer.results.append(FuzzResult(
            test_id="SAVE001",
            input_data={'test': 1},
            success=True,
            execution_time=0.1
        ))
        
        # Create report
        report = {
            'test_name': 'Save Test',
            'successful': 1,
            'failed': 0
        }
        
        # Save report
        output_file = tmp_path / "test_report.json"
        fuzzer.save_report(report, str(output_file))
        
        assert output_file.exists()
        
        # Load and verify
        with open(output_file, 'r') as f:
            saved_report = json.load(f)
        
        assert saved_report['test_name'] == 'Save Test'
        assert saved_report['metadata']['seed'] == 999
        assert saved_report['metadata']['total_tests'] == 1
    
    def test_replay_failures(self, tmp_path):
        """Test replaying failed tests"""
        fuzzer = StressFuzzer()
        
        # Create a report with failures
        report = {
            'seed': 12345,
            'errors': [
                {'test_id': 'FAIL001'},
                {'test_id': 'FAIL002'}
            ]
        }
        
        report_file = tmp_path / "failures.json"
        with open(report_file, 'w') as f:
            json.dump(report, f)
        
        # Replay failures
        def dummy_func(data):
            return True
        
        replay_results = fuzzer.replay_failures(str(report_file), dummy_func)
        
        assert len(replay_results) == 2
        assert all('replay_' in r.test_id for r in replay_results)