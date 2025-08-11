"""
Fault Injection Testing Framework
Systematic testing of failure modes and recovery
"""

import random
import numpy as np
from dataclasses import dataclass, field
from typing import List, Dict, Any, Optional, Callable, Tuple
from datetime import datetime, timedelta
from enum import Enum
import logging
import json

logger = logging.getLogger(__name__)


class FaultType(Enum):
    """Types of faults that can be injected"""
    SENSOR_FAILURE = "sensor_failure"
    SENSOR_DEGRADATION = "sensor_degradation"
    NETWORK_LATENCY = "network_latency"
    NETWORK_LOSS = "network_loss"
    DATA_CORRUPTION = "data_corruption"
    TIMING_DRIFT = "timing_drift"
    RESOURCE_EXHAUSTION = "resource_exhaustion"
    BYZANTINE = "byzantine"  # Incorrect but plausible data


@dataclass
class FaultScenario:
    """Definition of a fault scenario"""
    name: str
    fault_type: FaultType
    target: str  # Component or sensor ID
    parameters: Dict[str, Any]
    duration_seconds: float
    probability: float = 1.0  # Probability of occurrence
    
    def should_trigger(self) -> bool:
        """Check if fault should trigger based on probability"""
        return random.random() < self.probability


@dataclass
class FaultInjectionResult:
    """Result of fault injection test"""
    scenario: FaultScenario
    start_time: datetime
    end_time: datetime
    system_response: Dict[str, Any]
    recovery_time_seconds: Optional[float]
    success: bool
    failure_mode: Optional[str] = None
    metrics: Dict[str, float] = field(default_factory=dict)


class FaultInjector:
    """Inject faults into system components"""
    
    def __init__(self, seed: Optional[int] = None):
        """
        Initialize fault injector.
        
        Args:
            seed: Random seed for reproducibility
        """
        if seed:
            random.seed(seed)
            np.random.seed(seed)
        
        self.active_faults: Dict[str, FaultScenario] = {}
        self.injection_history: List[FaultInjectionResult] = []
        self.fault_handlers: Dict[FaultType, Callable] = {}
        
        self._register_default_handlers()
    
    def _register_default_handlers(self):
        """Register default fault handlers"""
        self.fault_handlers[FaultType.SENSOR_FAILURE] = self._inject_sensor_failure
        self.fault_handlers[FaultType.SENSOR_DEGRADATION] = self._inject_sensor_degradation
        self.fault_handlers[FaultType.NETWORK_LATENCY] = self._inject_network_latency
        self.fault_handlers[FaultType.DATA_CORRUPTION] = self._inject_data_corruption
        self.fault_handlers[FaultType.BYZANTINE] = self._inject_byzantine_fault
    
    def inject_fault(self, scenario: FaultScenario) -> Any:
        """
        Inject a fault according to scenario.
        
        Args:
            scenario: Fault scenario to inject
            
        Returns:
            Modified data or behavior
        """
        if not scenario.should_trigger():
            return None
        
        # Record fault injection
        self.active_faults[scenario.target] = scenario
        logger.warning(f"Injecting fault: {scenario.name} on {scenario.target}")
        
        # Apply fault handler
        handler = self.fault_handlers.get(scenario.fault_type)
        if handler:
            return handler(scenario)
        else:
            logger.error(f"No handler for fault type: {scenario.fault_type}")
            return None
    
    def _inject_sensor_failure(self, scenario: FaultScenario) -> Dict[str, Any]:
        """Inject sensor failure"""
        return {
            'type': 'sensor_failure',
            'target': scenario.target,
            'effect': 'no_data',
            'parameters': scenario.parameters
        }
    
    def _inject_sensor_degradation(self, scenario: FaultScenario) -> Dict[str, Any]:
        """Inject sensor degradation"""
        noise_level = scenario.parameters.get('noise_level', 0.1)
        drift_rate = scenario.parameters.get('drift_rate', 0.01)
        
        return {
            'type': 'sensor_degradation',
            'target': scenario.target,
            'effect': 'noisy_data',
            'noise_level': noise_level,
            'drift_rate': drift_rate
        }
    
    def _inject_network_latency(self, scenario: FaultScenario) -> Dict[str, Any]:
        """Inject network latency"""
        latency_ms = scenario.parameters.get('latency_ms', 1000)
        jitter_ms = scenario.parameters.get('jitter_ms', 100)
        
        actual_latency = latency_ms + random.gauss(0, jitter_ms)
        
        return {
            'type': 'network_latency',
            'target': scenario.target,
            'effect': 'delayed_data',
            'latency_ms': actual_latency
        }
    
    def _inject_data_corruption(self, scenario: FaultScenario) -> Dict[str, Any]:
        """Inject data corruption"""
        corruption_rate = scenario.parameters.get('corruption_rate', 0.01)
        corruption_type = scenario.parameters.get('corruption_type', 'bit_flip')
        
        return {
            'type': 'data_corruption',
            'target': scenario.target,
            'effect': corruption_type,
            'rate': corruption_rate
        }
    
    def _inject_byzantine_fault(self, scenario: FaultScenario) -> Dict[str, Any]:
        """Inject Byzantine fault (plausible but incorrect data)"""
        offset = scenario.parameters.get('offset', 0.1)
        scale = scenario.parameters.get('scale', 1.1)
        
        return {
            'type': 'byzantine',
            'target': scenario.target,
            'effect': 'incorrect_but_plausible',
            'offset': offset,
            'scale': scale
        }
    
    def apply_to_sensor_data(self, 
                            data: Any,
                            sensor_id: str,
                            timestamp: datetime) -> Tuple[Any, bool]:
        """
        Apply active faults to sensor data.
        
        Args:
            data: Original sensor data
            sensor_id: Sensor identifier
            timestamp: Data timestamp
            
        Returns:
            Tuple of (modified_data, was_modified)
        """
        if sensor_id not in self.active_faults:
            return data, False
        
        fault = self.active_faults[sensor_id]
        
        if fault.fault_type == FaultType.SENSOR_FAILURE:
            return None, True
        
        elif fault.fault_type == FaultType.SENSOR_DEGRADATION:
            # Add noise
            if isinstance(data, (int, float)):
                noise_level = fault.parameters.get('noise_level', 0.1)
                noise = np.random.normal(0, noise_level * abs(data))
                return data + noise, True
            return data, False
        
        elif fault.fault_type == FaultType.DATA_CORRUPTION:
            # Random corruption
            if random.random() < fault.parameters.get('corruption_rate', 0.01):
                if isinstance(data, (int, float)):
                    # Bit flip simulation
                    return data * random.choice([-1, 2, 0.5]), True
            return data, False
        
        elif fault.fault_type == FaultType.BYZANTINE:
            # Plausible but wrong
            if isinstance(data, (int, float)):
                offset = fault.parameters.get('offset', 0.1)
                scale = fault.parameters.get('scale', 1.1)
                return data * scale + offset, True
            return data, False
        
        return data, False
    
    def clear_fault(self, target: str):
        """Clear fault from target component"""
        if target in self.active_faults:
            del self.active_faults[target]
            logger.info(f"Cleared fault from {target}")
    
    def clear_all_faults(self):
        """Clear all active faults"""
        self.active_faults.clear()
        logger.info("Cleared all faults")


class FaultTestRunner:
    """Run systematic fault injection tests"""
    
    def __init__(self, system_under_test: Any):
        """
        Initialize test runner.
        
        Args:
            system_under_test: System to test
        """
        self.system = system_under_test
        self.injector = FaultInjector()
        self.test_results: List[FaultInjectionResult] = []
        
    def run_scenario(self, 
                    scenario: FaultScenario,
                    duration_seconds: float = 60.0) -> FaultInjectionResult:
        """
        Run a single fault injection scenario.
        
        Args:
            scenario: Fault scenario to test
            duration_seconds: Test duration
            
        Returns:
            Test result
        """
        logger.info(f"Starting fault scenario: {scenario.name}")
        
        start_time = datetime.now()
        
        # Inject fault
        self.injector.inject_fault(scenario)
        
        # Monitor system response
        response = self._monitor_system(duration_seconds)
        
        # Clear fault
        self.injector.clear_fault(scenario.target)
        
        # Measure recovery
        recovery_time = self._measure_recovery(scenario.target)
        
        end_time = datetime.now()
        
        # Evaluate success
        success = self._evaluate_success(response, scenario)
        
        result = FaultInjectionResult(
            scenario=scenario,
            start_time=start_time,
            end_time=end_time,
            system_response=response,
            recovery_time_seconds=recovery_time,
            success=success,
            failure_mode=response.get('failure_mode'),
            metrics=self._calculate_metrics(response)
        )
        
        self.test_results.append(result)
        return result
    
    def run_campaign(self, scenarios: List[FaultScenario]) -> Dict[str, Any]:
        """
        Run a campaign of fault injection tests.
        
        Args:
            scenarios: List of scenarios to test
            
        Returns:
            Campaign summary
        """
        logger.info(f"Starting fault injection campaign with {len(scenarios)} scenarios")
        
        results = []
        for scenario in scenarios:
            result = self.run_scenario(scenario)
            results.append(result)
            
            # Allow system to stabilize between tests
            import time
            time.sleep(0.1)  # Reduced for faster testing
        
        # Generate summary
        summary = self._generate_campaign_summary(results)
        
        return summary
    
    def _monitor_system(self, duration_seconds: float) -> Dict[str, Any]:
        """Monitor system during fault injection"""
        # This is a placeholder - actual implementation would monitor real system
        import time
        
        metrics = {
            'errors': 0,
            'warnings': 0,
            'interventions': 0,
            'mode_changes': [],
            'performance': []
        }
        
        start = time.time()
        while time.time() - start < duration_seconds:
            # Simulate monitoring
            if hasattr(self.system, 'get_status'):
                status = self.system.get_status()
                metrics['performance'].append(status)
            
            time.sleep(0.1)
        
        return metrics
    
    def _measure_recovery(self, target: str) -> float:
        """Measure recovery time after fault cleared"""
        # Placeholder - actual implementation would measure real recovery
        return random.uniform(1.0, 10.0)
    
    def _evaluate_success(self, response: Dict[str, Any], scenario: FaultScenario) -> bool:
        """Evaluate if system handled fault successfully"""
        # Success criteria:
        # - No critical errors
        # - System remained operational
        # - Recovery completed
        
        if response.get('errors', 0) > 10:
            return False
        
        if response.get('failure_mode') == 'critical':
            return False
        
        return True
    
    def _calculate_metrics(self, response: Dict[str, Any]) -> Dict[str, float]:
        """Calculate test metrics"""
        metrics = {}
        
        if 'performance' in response and response['performance']:
            # Calculate degradation
            metrics['performance_degradation'] = 0.0  # Placeholder
        
        metrics['error_rate'] = response.get('errors', 0) / 60.0  # Errors per second
        metrics['intervention_rate'] = response.get('interventions', 0) / 60.0
        
        return metrics
    
    def _generate_campaign_summary(self, results: List[FaultInjectionResult]) -> Dict[str, Any]:
        """Generate summary of test campaign"""
        total_tests = len(results)
        successful_tests = sum(1 for r in results if r.success)
        
        fault_type_results = {}
        for result in results:
            fault_type = result.scenario.fault_type.value
            if fault_type not in fault_type_results:
                fault_type_results[fault_type] = {'total': 0, 'success': 0}
            fault_type_results[fault_type]['total'] += 1
            if result.success:
                fault_type_results[fault_type]['success'] += 1
        
        # Calculate success rates
        for fault_type in fault_type_results:
            stats = fault_type_results[fault_type]
            stats['success_rate'] = stats['success'] / stats['total'] if stats['total'] > 0 else 0
        
        # Average recovery time
        recovery_times = [r.recovery_time_seconds for r in results if r.recovery_time_seconds]
        avg_recovery = np.mean(recovery_times) if recovery_times else 0
        
        return {
            'total_tests': total_tests,
            'successful_tests': successful_tests,
            'overall_success_rate': successful_tests / total_tests if total_tests > 0 else 0,
            'fault_type_results': fault_type_results,
            'average_recovery_time': avg_recovery,
            'critical_failures': [r.scenario.name for r in results if not r.success and r.failure_mode == 'critical'],
            'timestamp': datetime.now().isoformat()
        }


class ChaosEngineer:
    """Chaos engineering for maritime systems"""
    
    def __init__(self):
        """Initialize chaos engineer"""
        self.scenarios = self._define_chaos_scenarios()
        self.test_runner = None
        
    def _define_chaos_scenarios(self) -> List[FaultScenario]:
        """Define standard chaos scenarios"""
        return [
            # GPS failure scenarios
            FaultScenario(
                name="GPS_Total_Failure",
                fault_type=FaultType.SENSOR_FAILURE,
                target="gps_primary",
                parameters={},
                duration_seconds=300,
                probability=1.0
            ),
            FaultScenario(
                name="GPS_Degradation",
                fault_type=FaultType.SENSOR_DEGRADATION,
                target="gps_primary",
                parameters={'noise_level': 0.5, 'drift_rate': 0.1},
                duration_seconds=600,
                probability=1.0
            ),
            
            # Radar scenarios
            FaultScenario(
                name="Radar_Intermittent",
                fault_type=FaultType.NETWORK_LOSS,
                target="radar",
                parameters={'loss_rate': 0.3},
                duration_seconds=300,
                probability=1.0
            ),
            
            # AIS scenarios
            FaultScenario(
                name="AIS_Byzantine",
                fault_type=FaultType.BYZANTINE,
                target="ais",
                parameters={'offset': 0.5, 'scale': 1.2},
                duration_seconds=300,
                probability=1.0
            ),
            
            # Depth sensor scenarios
            FaultScenario(
                name="Depth_Sensor_Drift",
                fault_type=FaultType.TIMING_DRIFT,
                target="depth_sounder",
                parameters={'drift_rate': 0.05},
                duration_seconds=600,
                probability=1.0
            ),
            
            # Network scenarios
            FaultScenario(
                name="High_Latency",
                fault_type=FaultType.NETWORK_LATENCY,
                target="network",
                parameters={'latency_ms': 2000, 'jitter_ms': 500},
                duration_seconds=300,
                probability=1.0
            ),
            
            # Multiple simultaneous failures
            FaultScenario(
                name="Cascade_Failure",
                fault_type=FaultType.SENSOR_FAILURE,
                target="multiple",
                parameters={'targets': ['gps_primary', 'radar', 'ais']},
                duration_seconds=180,
                probability=1.0
            )
        ]
    
    def run_chaos_tests(self, system: Any) -> Dict[str, Any]:
        """Run chaos engineering tests"""
        self.test_runner = FaultTestRunner(system)
        return self.test_runner.run_campaign(self.scenarios)
    
    def generate_report(self, results: Dict[str, Any]) -> str:
        """Generate chaos engineering report"""
        report = []
        report.append("=" * 60)
        report.append("CHAOS ENGINEERING TEST REPORT")
        report.append("=" * 60)
        report.append("")
        
        report.append(f"Timestamp: {results['timestamp']}")
        report.append(f"Total Tests: {results['total_tests']}")
        report.append(f"Successful: {results['successful_tests']}")
        report.append(f"Success Rate: {results['overall_success_rate']:.1%}")
        report.append(f"Avg Recovery Time: {results['average_recovery_time']:.1f}s")
        report.append("")
        
        report.append("Fault Type Results:")
        for fault_type, stats in results['fault_type_results'].items():
            report.append(f"  {fault_type}:")
            report.append(f"    Tests: {stats['total']}")
            report.append(f"    Success Rate: {stats['success_rate']:.1%}")
        report.append("")
        
        if results['critical_failures']:
            report.append("Critical Failures:")
            for failure in results['critical_failures']:
                report.append(f"  - {failure}")
        else:
            report.append("No critical failures detected")
        
        report.append("")
        report.append("=" * 60)
        
        return "\n".join(report)