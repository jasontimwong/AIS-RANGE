"""
Tests for Fault Injection Framework
"""

import pytest
import random
from datetime import datetime, timedelta
import sys
import os

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from lib.testing.fault_injection import (
    FaultType,
    FaultScenario,
    FaultInjectionResult,
    FaultInjector,
    FaultTestRunner,
    ChaosEngineer
)


class TestFaultScenario:
    """Test FaultScenario class"""
    
    def test_scenario_creation(self):
        """Test creating fault scenario"""
        scenario = FaultScenario(
            name="GPS_Failure",
            fault_type=FaultType.SENSOR_FAILURE,
            target="gps_primary",
            parameters={},
            duration_seconds=60,
            probability=1.0
        )
        
        assert scenario.name == "GPS_Failure"
        assert scenario.fault_type == FaultType.SENSOR_FAILURE
        assert scenario.target == "gps_primary"
        assert scenario.duration_seconds == 60
    
    def test_probability_trigger(self):
        """Test probability-based triggering"""
        # Always triggers
        scenario1 = FaultScenario(
            name="Always",
            fault_type=FaultType.SENSOR_FAILURE,
            target="sensor1",
            parameters={},
            duration_seconds=60,
            probability=1.0
        )
        assert scenario1.should_trigger() == True
        
        # Never triggers
        scenario2 = FaultScenario(
            name="Never",
            fault_type=FaultType.SENSOR_FAILURE,
            target="sensor2",
            parameters={},
            duration_seconds=60,
            probability=0.0
        )
        assert scenario2.should_trigger() == False


class TestFaultInjector:
    """Test FaultInjector class"""
    
    def test_initialization(self):
        """Test injector initialization"""
        injector = FaultInjector(seed=42)
        
        assert len(injector.active_faults) == 0
        assert len(injector.fault_handlers) > 0
    
    def test_inject_sensor_failure(self):
        """Test injecting sensor failure"""
        injector = FaultInjector()
        
        scenario = FaultScenario(
            name="GPS_Fail",
            fault_type=FaultType.SENSOR_FAILURE,
            target="gps",
            parameters={},
            duration_seconds=60,
            probability=1.0
        )
        
        result = injector.inject_fault(scenario)
        
        assert result['type'] == 'sensor_failure'
        assert result['target'] == 'gps'
        assert result['effect'] == 'no_data'
        assert 'gps' in injector.active_faults
    
    def test_inject_sensor_degradation(self):
        """Test injecting sensor degradation"""
        injector = FaultInjector()
        
        scenario = FaultScenario(
            name="GPS_Degrade",
            fault_type=FaultType.SENSOR_DEGRADATION,
            target="gps",
            parameters={'noise_level': 0.2, 'drift_rate': 0.05},
            duration_seconds=60,
            probability=1.0
        )
        
        result = injector.inject_fault(scenario)
        
        assert result['type'] == 'sensor_degradation'
        assert result['noise_level'] == 0.2
        assert result['drift_rate'] == 0.05
    
    def test_inject_network_latency(self):
        """Test injecting network latency"""
        injector = FaultInjector()
        
        scenario = FaultScenario(
            name="High_Latency",
            fault_type=FaultType.NETWORK_LATENCY,
            target="network",
            parameters={'latency_ms': 1000, 'jitter_ms': 100},
            duration_seconds=60,
            probability=1.0
        )
        
        result = injector.inject_fault(scenario)
        
        assert result['type'] == 'network_latency'
        assert result['effect'] == 'delayed_data'
        assert 'latency_ms' in result
    
    def test_apply_to_sensor_data(self):
        """Test applying faults to sensor data"""
        injector = FaultInjector(seed=42)
        
        # Inject degradation fault
        scenario = FaultScenario(
            name="Noisy",
            fault_type=FaultType.SENSOR_DEGRADATION,
            target="sensor1",
            parameters={'noise_level': 0.1},
            duration_seconds=60,
            probability=1.0
        )
        injector.inject_fault(scenario)
        
        # Apply to data
        original_data = 100.0
        modified_data, was_modified = injector.apply_to_sensor_data(
            original_data, "sensor1", datetime.now()
        )
        
        assert was_modified == True
        assert modified_data != original_data
        assert abs(modified_data - original_data) < 50  # Reasonable noise
    
    def test_sensor_failure_application(self):
        """Test sensor failure application"""
        injector = FaultInjector()
        
        # Inject failure
        scenario = FaultScenario(
            name="Fail",
            fault_type=FaultType.SENSOR_FAILURE,
            target="sensor2",
            parameters={},
            duration_seconds=60,
            probability=1.0
        )
        injector.inject_fault(scenario)
        
        # Apply to data
        data, was_modified = injector.apply_to_sensor_data(
            100.0, "sensor2", datetime.now()
        )
        
        assert was_modified == True
        assert data is None  # Failed sensor returns None
    
    def test_byzantine_fault(self):
        """Test Byzantine fault injection"""
        injector = FaultInjector()
        
        scenario = FaultScenario(
            name="Byzantine",
            fault_type=FaultType.BYZANTINE,
            target="sensor3",
            parameters={'offset': 10.0, 'scale': 1.5},
            duration_seconds=60,
            probability=1.0
        )
        injector.inject_fault(scenario)
        
        # Apply to data
        original = 100.0
        modified, was_modified = injector.apply_to_sensor_data(
            original, "sensor3", datetime.now()
        )
        
        assert was_modified == True
        # Byzantine: data * scale + offset
        expected = original * 1.5 + 10.0
        assert modified == expected
    
    def test_clear_fault(self):
        """Test clearing faults"""
        injector = FaultInjector()
        
        # Inject fault
        scenario = FaultScenario(
            name="Test",
            fault_type=FaultType.SENSOR_FAILURE,
            target="sensor1",
            parameters={},
            duration_seconds=60,
            probability=1.0
        )
        injector.inject_fault(scenario)
        
        assert "sensor1" in injector.active_faults
        
        # Clear fault
        injector.clear_fault("sensor1")
        assert "sensor1" not in injector.active_faults
    
    def test_clear_all_faults(self):
        """Test clearing all faults"""
        injector = FaultInjector()
        
        # Inject multiple faults
        for i in range(3):
            scenario = FaultScenario(
                name=f"Fault_{i}",
                fault_type=FaultType.SENSOR_FAILURE,
                target=f"sensor_{i}",
                parameters={},
                duration_seconds=60,
                probability=1.0
            )
            injector.inject_fault(scenario)
        
        assert len(injector.active_faults) == 3
        
        # Clear all
        injector.clear_all_faults()
        assert len(injector.active_faults) == 0


class MockSystem:
    """Mock system for testing"""
    
    def __init__(self):
        self.status = {'operational': True}
    
    def get_status(self):
        return self.status


class TestFaultTestRunner:
    """Test FaultTestRunner class"""
    
    def test_initialization(self):
        """Test runner initialization"""
        system = MockSystem()
        runner = FaultTestRunner(system)
        
        assert runner.system == system
        assert len(runner.test_results) == 0
    
    def test_run_scenario(self):
        """Test running a single scenario"""
        system = MockSystem()
        runner = FaultTestRunner(system)
        
        # Override _monitor_system to avoid actual sleep
        def mock_monitor(duration):
            return {
                'errors': 0,
                'warnings': 0,
                'interventions': 0,
                'mode_changes': [],
                'performance': []
            }
        runner._monitor_system = mock_monitor
        
        scenario = FaultScenario(
            name="Test_Scenario",
            fault_type=FaultType.SENSOR_FAILURE,
            target="gps",
            parameters={},
            duration_seconds=0.01,  # Very short duration for testing
            probability=1.0
        )
        
        result = runner.run_scenario(scenario, duration_seconds=0.01)
        
        assert isinstance(result, FaultInjectionResult)
        assert result.scenario == scenario
        assert result.start_time < result.end_time
        assert 'errors' in result.system_response
    
    def test_run_campaign(self):
        """Test running a test campaign"""
        system = MockSystem()
        runner = FaultTestRunner(system)
        
        # Override _monitor_system to avoid actual sleep
        def mock_monitor(duration):
            return {
                'errors': 0,
                'warnings': 0,
                'interventions': 0,
                'mode_changes': [],
                'performance': []
            }
        runner._monitor_system = mock_monitor
        
        scenarios = [
            FaultScenario(
                name=f"Scenario_{i}",
                fault_type=FaultType.SENSOR_FAILURE,
                target=f"sensor_{i}",
                parameters={},
                duration_seconds=0.01,  # Very short duration
                probability=1.0
            )
            for i in range(3)
        ]
        
        summary = runner.run_campaign(scenarios)
        
        assert summary['total_tests'] == 3
        assert 'overall_success_rate' in summary
        assert 'fault_type_results' in summary
        assert 'average_recovery_time' in summary


class TestChaosEngineer:
    """Test ChaosEngineer class"""
    
    def test_initialization(self):
        """Test chaos engineer initialization"""
        chaos = ChaosEngineer()
        
        assert len(chaos.scenarios) > 0
        assert chaos.test_runner is None
    
    def test_scenario_definitions(self):
        """Test predefined chaos scenarios"""
        chaos = ChaosEngineer()
        
        # Check some expected scenarios exist
        scenario_names = [s.name for s in chaos.scenarios]
        
        assert "GPS_Total_Failure" in scenario_names
        assert "GPS_Degradation" in scenario_names
        assert "High_Latency" in scenario_names
        
        # Check scenario properties
        gps_scenario = next(s for s in chaos.scenarios if s.name == "GPS_Total_Failure")
        assert gps_scenario.fault_type == FaultType.SENSOR_FAILURE
        assert gps_scenario.target == "gps_primary"
    
    def test_generate_report(self):
        """Test report generation"""
        chaos = ChaosEngineer()
        
        # Mock results
        results = {
            'timestamp': datetime.now().isoformat(),
            'total_tests': 10,
            'successful_tests': 8,
            'overall_success_rate': 0.8,
            'average_recovery_time': 5.5,
            'fault_type_results': {
                'sensor_failure': {'total': 5, 'success': 4, 'success_rate': 0.8},
                'network_latency': {'total': 5, 'success': 4, 'success_rate': 0.8}
            },
            'critical_failures': ['GPS_Total_Failure']
        }
        
        report = chaos.generate_report(results)
        
        assert "CHAOS ENGINEERING TEST REPORT" in report
        assert "Total Tests: 10" in report
        assert "Success Rate: 80.0%" in report
        assert "GPS_Total_Failure" in report