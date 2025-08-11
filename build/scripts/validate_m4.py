#!/usr/bin/env python3
"""
M4 COLREG Development Validation Script
Validates all M4 milestone requirements have been completed.
"""

import os
import sys
import subprocess
from pathlib import Path
from datetime import datetime
import json

# Add lib to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

class M4Validator:
    """Validates M4 COLREG development milestone"""
    
    def __init__(self):
        self.results = []
        self.passed = 0
        self.failed = 0
        
    def run_validation(self):
        """Run complete M4 validation"""
        print("=" * 70)
        print("M4 COLREG DEVELOPMENT VALIDATION")
        print("=" * 70)
        print(f"Validation Time: {datetime.now().isoformat()}")
        print()
        
        # Validate C4.1: COLREG Rules Implementation
        self.validate_colreg_rules()
        
        # Validate C4.2: Route Checker Integration
        self.validate_route_checker_integration()
        
        # Validate C4.3: COLREG Scenarios
        self.validate_colreg_scenarios()
        
        # Validate C4.4: Golden Sample Tests
        self.validate_golden_samples()
        
        # Validate Code Quality
        self.validate_code_quality()
        
        # Print summary
        self.print_summary()
        
        return self.failed == 0
    
    def validate_colreg_rules(self):
        """C4.1: Validate COLREG rules implementation"""
        print("C4.1: COLREG Rules Implementation")
        print("-" * 40)
        
        # Check if COLREG module exists
        colreg_path = Path("lib/colreg/rules.py")
        if colreg_path.exists():
            self.log_pass("COLREG rules module exists")
            
            # Check module can be imported
            try:
                from lib.colreg import COLREGRules, Vessel, COLREGAssessment
                self.log_pass("COLREG module imports successfully")
                
                # Test basic functionality
                rules = COLREGRules()
                own = Vessel(
                    mmsi="TEST_OWN",
                    position=(37.8, -122.5),
                    speed=12.0,
                    course=90.0,
                    heading=90.0
                )
                target = Vessel(
                    mmsi="TEST_TGT",
                    position=(37.79, -122.49),
                    speed=10.0,
                    course=0.0,
                    heading=0.0
                )
                assessment = rules.assess_situation(own, target)
                
                if assessment and hasattr(assessment, 'encounter_type'):
                    self.log_pass("COLREG assessment works")
                else:
                    self.log_fail("COLREG assessment failed")
                    
            except Exception as e:
                self.log_fail(f"COLREG module import failed: {e}")
        else:
            self.log_fail("COLREG rules module not found")
        
        # Run unit tests
        result = subprocess.run(
            ["python", "-m", "pytest", "tests/colreg/test_colreg_rules.py", "-q"],
            capture_output=True,
            text=True
        )
        
        if result.returncode == 0:
            # Extract test count
            if "passed" in result.stdout:
                test_count = result.stdout.split()[0]
                self.log_pass(f"COLREG unit tests passed ({test_count} tests)")
            else:
                self.log_pass("COLREG unit tests passed")
        else:
            self.log_fail("COLREG unit tests failed")
        
        print()
    
    def validate_route_checker_integration(self):
        """C4.2: Validate Route Checker integration"""
        print("C4.2: Route Checker Integration")
        print("-" * 40)
        
        # Check if Route Checker has COLREG support
        checker_path = Path("lib/checks/route_checker.py")
        if checker_path.exists():
            with open(checker_path) as f:
                content = f.read()
                
            if "colreg" in content.lower():
                self.log_pass("Route Checker has COLREG references")
                
                if "_check_colreg_compliance" in content:
                    self.log_pass("COLREG compliance method implemented")
                else:
                    self.log_fail("COLREG compliance method not found")
                    
                if "colreg_checks" in content:
                    self.log_pass("COLREG checks in validation report")
                else:
                    self.log_fail("COLREG checks not in report structure")
            else:
                self.log_fail("Route Checker missing COLREG integration")
        else:
            self.log_fail("Route Checker module not found")
        
        # Run integration tests
        test_file = "tests/test_route_checker_colreg.py"
        if Path(test_file).exists():
            result = subprocess.run(
                ["python", "-m", "pytest", test_file, "-q"],
                capture_output=True,
                text=True
            )
            
            if result.returncode == 0:
                if "passed" in result.stdout:
                    test_count = result.stdout.split()[0]
                    self.log_pass(f"Route Checker COLREG tests passed ({test_count} tests)")
                else:
                    self.log_pass("Route Checker COLREG tests passed")
            else:
                self.log_fail("Route Checker COLREG tests failed")
        else:
            self.log_warn("Route Checker COLREG tests not found")
        
        print()
    
    def validate_colreg_scenarios(self):
        """C4.3: Validate COLREG scenarios"""
        print("C4.3: COLREG Scenarios")
        print("-" * 40)
        
        required_scenarios = [
            "crossing",
            "head_on",
            "overtaking",
            "narrow",
            "tss_lane"
        ]
        
        scenario_dir = Path("scenarios/colreg")
        if scenario_dir.exists():
            self.log_pass("COLREG scenario directory exists")
            
            for scenario in required_scenarios:
                scenario_file = scenario_dir / f"{scenario}.yaml"
                if scenario_file.exists():
                    self.log_pass(f"Scenario '{scenario}' exists")
                else:
                    self.log_fail(f"Scenario '{scenario}' missing")
        else:
            self.log_fail("COLREG scenario directory not found")
        
        # Run scenario tests
        result = subprocess.run(
            ["python", "-m", "pytest", "tests/colreg/test_scenarios.py", "-q"],
            capture_output=True,
            text=True
        )
        
        if result.returncode == 0:
            if "passed" in result.stdout:
                test_count = result.stdout.split()[0]
                self.log_pass(f"Scenario tests passed ({test_count} tests)")
            else:
                self.log_pass("Scenario tests passed")
        else:
            self.log_fail("Scenario tests failed")
        
        print()
    
    def validate_golden_samples(self):
        """C4.4: Validate golden sample tests"""
        print("C4.4: Golden Sample Tests")
        print("-" * 40)
        
        golden_test = Path("tests/golden/test_colreg_golden.py")
        if golden_test.exists():
            self.log_pass("Golden sample test file exists")
            
            # Check test content
            with open(golden_test) as f:
                content = f.read()
                
            golden_tests = [
                "test_golden_crossing_give_way",
                "test_golden_crossing_stand_on",
                "test_golden_head_on",
                "test_golden_overtaking",
                "test_golden_no_risk"
            ]
            
            for test in golden_tests:
                if test in content:
                    self.log_pass(f"Golden test '{test}' defined")
                else:
                    self.log_warn(f"Golden test '{test}' missing")
        else:
            self.log_fail("Golden sample test file not found")
        
        # Check if golden results directory exists
        golden_dir = Path("tests/golden/results")
        if golden_dir.exists():
            self.log_pass("Golden results directory exists")
            
            # Count golden result files
            result_files = list(golden_dir.glob("*.json"))
            if result_files:
                self.log_pass(f"Found {len(result_files)} golden result files")
            else:
                self.log_info("No golden result files yet")
        else:
            self.log_info("Golden results directory not created yet")
        
        print()
    
    def validate_code_quality(self):
        """Validate code quality metrics"""
        print("Code Quality Metrics")
        print("-" * 40)
        
        # Count lines of code
        total_lines = 0
        test_lines = 0
        
        # COLREG module
        for py_file in Path("lib/colreg").glob("*.py"):
            with open(py_file) as f:
                lines = len(f.readlines())
                total_lines += lines
        
        # COLREG tests
        for py_file in Path("tests/colreg").glob("*.py"):
            if py_file.exists():
                with open(py_file) as f:
                    lines = len(f.readlines())
                    test_lines += lines
        
        self.log_info(f"Total COLREG code: {total_lines} lines")
        self.log_info(f"Total test code: {test_lines} lines")
        
        if test_lines > 0:
            ratio = test_lines / total_lines
            self.log_info(f"Test/Code ratio: {ratio:.2f}")
            
            if ratio >= 0.3:
                self.log_pass("Good test coverage ratio")
            else:
                self.log_warn("Low test coverage ratio")
        
        # Check documentation
        progress_file = Path("M4_COLREG_PROGRESS.md")
        if progress_file.exists():
            self.log_pass("M4 progress documentation exists")
        else:
            self.log_warn("M4 progress documentation missing")
        
        print()
    
    def log_pass(self, message):
        """Log passing test"""
        print(f"  ✅ {message}")
        self.results.append(("PASS", message))
        self.passed += 1
    
    def log_fail(self, message):
        """Log failing test"""
        print(f"  ❌ {message}")
        self.results.append(("FAIL", message))
        self.failed += 1
    
    def log_warn(self, message):
        """Log warning"""
        print(f"  ⚠️  {message}")
        self.results.append(("WARN", message))
    
    def log_info(self, message):
        """Log info"""
        print(f"  ℹ️  {message}")
        self.results.append(("INFO", message))
    
    def print_summary(self):
        """Print validation summary"""
        print("=" * 70)
        print("VALIDATION SUMMARY")
        print("=" * 70)
        
        total = self.passed + self.failed
        if total > 0:
            success_rate = (self.passed / total) * 100
        else:
            success_rate = 0
        
        print(f"Total Checks: {total}")
        print(f"Passed: {self.passed}")
        print(f"Failed: {self.failed}")
        print(f"Success Rate: {success_rate:.1f}%")
        print()
        
        if self.failed == 0:
            print("✅ M4 VALIDATION PASSED")
            print("All COLREG development requirements met!")
        else:
            print("❌ M4 VALIDATION FAILED")
            print(f"Fix {self.failed} failing checks before proceeding")
        
        print("=" * 70)
        
        # Save results
        results_file = Path("M4_validation_results.json")
        with open(results_file, "w") as f:
            json.dump({
                "timestamp": datetime.now().isoformat(),
                "passed": self.passed,
                "failed": self.failed,
                "success_rate": success_rate,
                "results": self.results
            }, f, indent=2)
        
        print(f"\nResults saved to: {results_file}")


if __name__ == "__main__":
    validator = M4Validator()
    success = validator.run_validation()
    
    # Exit with appropriate code
    sys.exit(0 if success else 1)