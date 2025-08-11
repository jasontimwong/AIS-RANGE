"""
Route Checker Module
Validates planned routes against safety, regulatory, and operational constraints.
Generates detailed validation reports with evidence.
"""

from typing import List, Dict, Optional, Any, Tuple
from dataclasses import dataclass, field
from enum import Enum
import numpy as np
from shapely.geometry import Point, LineString
import json
import logging
from datetime import datetime
from pathlib import Path

from lib.planner.hybrid_astar import Route
from lib.region.feasible_region import FeasibleRegion
from lib.region.tss_layers import TSSZones
from lib.colreg import (
    COLREGRules, 
    COLREGValidator,
    Vessel,
    VesselType,
    NavigationStatus
)

logger = logging.getLogger(__name__)

# 标准条款映射
CLAUSE_MAPPING = {
    'safety_depth': [
        {
            'standard': 'IMO MSC.232(82)',
            'clause': '4.7.1',
            'requirement': 'Maintain minimum safety depth'
        },
        {
            'standard': 'IHO S-52',
            'clause': '8.3.2',
            'requirement': 'Respect safety contour'
        }
    ],
    'xtd_corridor': [
        {
            'standard': 'IMO MSC.232(82)',
            'clause': '4.8.3',
            'requirement': 'Cross-track distance limits'
        }
    ],
    'tss_compliance': [
        {
            'standard': 'COLREG',
            'clause': 'Rule 10',
            'requirement': 'Traffic separation scheme compliance'
        },
        {
            'standard': 'IMO MSC.232(82)',
            'clause': '4.9.2',
            'requirement': 'TSS navigation rules'
        }
    ],
    'turn_radius': [
        {
            'standard': 'IMO MSC.232(82)',
            'clause': '4.7.3',
            'requirement': 'Minimum turning radius'
        }
    ],
    'speed_limits': [
        {
            'standard': 'IMO MSC.232(82)',
            'clause': '4.10.1',
            'requirement': 'Safe speed maintenance'
        }
    ],
    'no_go_areas': [
        {
            'standard': 'IMO MSC.232(82)',
            'clause': '4.7.2',
            'requirement': 'Avoidance of no-go areas'
        },
        {
            'standard': 'IHO S-52',
            'clause': '8.2.1',
            'requirement': 'Prohibited area avoidance'
        }
    ],
    'colreg_compliance': [
        {
            'standard': 'COLREG',
            'clause': 'Rule 7',
            'requirement': 'Risk of collision assessment'
        },
        {
            'standard': 'COLREG',
            'clause': 'Rule 8',
            'requirement': 'Action to avoid collision'
        },
        {
            'standard': 'COLREG',
            'clause': 'Rule 13',
            'requirement': 'Overtaking'
        },
        {
            'standard': 'COLREG',
            'clause': 'Rule 14',
            'requirement': 'Head-on situation'
        },
        {
            'standard': 'COLREG',
            'clause': 'Rule 15',
            'requirement': 'Crossing situation'
        }
    ]
}


class ValidationStatus(Enum):
    """Validation check status."""
    PASS = "pass"
    FAIL = "fail"
    WARNING = "warning"
    INFO = "info"


@dataclass
class ValidationCheck:
    """Single validation check result with clause references."""
    name: str
    status: ValidationStatus
    message: str
    category: str  # safety, tss, geometry, speed, cpa, colreg
    severity: str  # critical, high, medium, low
    clause_refs: List[Dict[str, str]] = field(default_factory=list)
    evidence: Dict[str, Any] = field(default_factory=dict)
    location: Optional[Tuple[float, float]] = None  # Where issue occurred
    waypoint_index: Optional[int] = None  # Which waypoint
    
    def set_clause_compliance(self, check_type: str):
        """Set clause references with compliance status."""
        if check_type in CLAUSE_MAPPING:
            for clause in CLAUSE_MAPPING[check_type]:
                ref = clause.copy()
                ref['status'] = 'COMPLIANT' if self.status == ValidationStatus.PASS else 'NON_COMPLIANT'
                self.clause_refs.append(ref)


@dataclass
class RouteValidationReport:
    """Complete route validation report."""
    route_name: str
    validation_time: datetime
    total_checks: int
    passed_checks: int
    failed_checks: int
    warnings: int
    
    # Check results by category
    safety_checks: List[ValidationCheck]
    tss_checks: List[ValidationCheck]
    geometry_checks: List[ValidationCheck]
    speed_checks: List[ValidationCheck]
    cpa_checks: List[ValidationCheck]
    colreg_checks: List[ValidationCheck]
    
    # Summary
    is_valid: bool
    critical_issues: List[str]
    recommendations: List[str]
    
    # Metrics
    metrics: Dict[str, float] = field(default_factory=dict)
    
    def to_json(self) -> str:
        """Convert report to JSON string with compliance summary."""
        # 收集所有条款引用
        all_clauses = {}
        all_checks = (self.safety_checks + self.tss_checks + 
                     self.geometry_checks + self.speed_checks + 
                     self.cpa_checks + self.colreg_checks)
        
        for check in all_checks:
            for clause in check.clause_refs:
                key = f"{clause['standard']}_{clause['clause']}"
                if key not in all_clauses:
                    all_clauses[key] = clause
                elif clause.get('status') == 'NON_COMPLIANT':
                    # 如果有不合规的，覆盖合规状态
                    all_clauses[key] = clause
        
        report_dict = {
            "route_name": self.route_name,
            "validation_time": self.validation_time.isoformat(),
            "summary": {
                "total_checks": self.total_checks,
                "passed": self.passed_checks,
                "failed": self.failed_checks,
                "warnings": self.warnings,
                "is_valid": self.is_valid
            },
            "checks": {
                "safety": [self._check_to_dict(c) for c in self.safety_checks],
                "tss": [self._check_to_dict(c) for c in self.tss_checks],
                "geometry": [self._check_to_dict(c) for c in self.geometry_checks],
                "speed": [self._check_to_dict(c) for c in self.speed_checks],
                "cpa": [self._check_to_dict(c) for c in self.cpa_checks],
                "colreg": [self._check_to_dict(c) for c in self.colreg_checks]
            },
            "critical_issues": self.critical_issues,
            "recommendations": self.recommendations,
            "metrics": self.metrics,
            "compliance_summary": {
                "total_clauses": len(all_clauses),
                "compliant": sum(1 for c in all_clauses.values() if c.get('status') == 'COMPLIANT'),
                "non_compliant": sum(1 for c in all_clauses.values() if c.get('status') == 'NON_COMPLIANT'),
                "clauses": list(all_clauses.values())
            }
        }
        
        return json.dumps(report_dict, indent=2)
    
    def _check_to_dict(self, check: ValidationCheck) -> Dict:
        """Convert validation check to dictionary with clause refs."""
        return {
            "name": check.name,
            "status": check.status.value,
            "message": check.message,
            "severity": check.severity,
            "evidence": check.evidence,
            "location": check.location,
            "waypoint_index": check.waypoint_index,
            "clause_refs": check.clause_refs
        }


class RouteChecker:
    """Performs comprehensive route validation."""
    
    def __init__(self, 
                 feasible_region: FeasibleRegion,
                 safety_depth: float = 10.0,
                 xtd_limit: float = 185.2,  # 0.1 NM in meters
                 min_cpa: float = 926.0,  # 0.5 NM in meters
                 enable_colreg: bool = True):
        """
        Initialize route checker.
        
        Args:
            feasible_region: Feasible navigation region
            safety_depth: Minimum safe water depth in meters
            xtd_limit: Cross-track distance limit in meters
            min_cpa: Minimum CPA to other vessels in meters
            enable_colreg: Enable COLREG compliance checking
        """
        self.region = feasible_region
        self.safety_depth = safety_depth
        self.xtd_limit = xtd_limit
        self.min_cpa = min_cpa
        self.enable_colreg = enable_colreg
        
        if self.enable_colreg:
            self.colreg_rules = COLREGRules(
                safety_distance_nm=min_cpa / 1852.0,  # Convert meters to nm
                safety_time_min=10.0
            )
            self.colreg_validator = COLREGValidator(self.colreg_rules)
        
        self.checks_performed = []
    
    def validate_route(self, route: Route, route_name: str = "Route", 
                      traffic_vessels: List[Vessel] = None) -> RouteValidationReport:
        """
        Perform complete route validation.
        
        Args:
            route: Route to validate
            route_name: Name for the route
            traffic_vessels: List of traffic vessels for COLREG checking
            
        Returns:
            Complete validation report
        """
        logger.info(f"Validating route: {route_name}")
        
        # Initialize check lists
        safety_checks = []
        tss_checks = []
        geometry_checks = []
        speed_checks = []
        cpa_checks = []
        colreg_checks = []
        
        # Perform safety checks
        safety_checks.extend(self._check_no_go_areas(route))
        safety_checks.extend(self._check_safety_contour(route))
        safety_checks.extend(self._check_under_keel_clearance(route))
        
        # Perform TSS compliance checks
        if self.region.tss_zones:
            tss_checks.extend(self._check_tss_compliance(route))
        
        # Perform geometry checks
        geometry_checks.extend(self._check_xtd_corridor(route))
        geometry_checks.extend(self._check_turn_radius(route))
        geometry_checks.extend(self._check_route_continuity(route))
        
        # Perform speed checks
        speed_checks.extend(self._check_speed_limits(route))
        speed_checks.extend(self._check_acceleration_limits(route))
        
        # Perform CPA checks (placeholder - requires traffic data)
        # cpa_checks.extend(self._check_cpa_tcpa(route, traffic_data))
        
        # Perform COLREG checks if enabled
        if self.enable_colreg and traffic_vessels is not None:
            colreg_checks.extend(self._check_colreg_compliance(route, traffic_vessels))
        
        # Compile all checks
        all_checks = (safety_checks + tss_checks + geometry_checks + 
                     speed_checks + cpa_checks + colreg_checks)
        
        # Count results
        total_checks = len(all_checks)
        passed = sum(1 for c in all_checks if c.status == ValidationStatus.PASS)
        failed = sum(1 for c in all_checks if c.status == ValidationStatus.FAIL)
        warnings = sum(1 for c in all_checks if c.status == ValidationStatus.WARNING)
        
        # Determine overall validity
        critical_fails = [c for c in all_checks 
                         if c.status == ValidationStatus.FAIL and c.severity == "critical"]
        is_valid = len(critical_fails) == 0
        
        # Generate critical issues list
        critical_issues = [c.message for c in critical_fails]
        
        # Generate recommendations
        recommendations = self._generate_recommendations(all_checks)
        
        # Calculate metrics
        metrics = {
            "route_length_m": route.get_length(),
            "waypoint_count": len(route.waypoints),
            "min_clearance_m": self._calculate_min_clearance(route),
            "max_turn_rate": self._calculate_max_turn_rate(route),
            "compliance_score": (passed / total_checks * 100) if total_checks > 0 else 0
        }
        
        return RouteValidationReport(
            route_name=route_name,
            validation_time=datetime.now(),
            total_checks=total_checks,
            passed_checks=passed,
            failed_checks=failed,
            warnings=warnings,
            safety_checks=safety_checks,
            tss_checks=tss_checks,
            geometry_checks=geometry_checks,
            speed_checks=speed_checks,
            cpa_checks=cpa_checks,
            colreg_checks=colreg_checks,
            is_valid=is_valid,
            critical_issues=critical_issues,
            recommendations=recommendations,
            metrics=metrics
        )
    
    def _check_no_go_areas(self, route: Route) -> List[ValidationCheck]:
        """Check route doesn't enter no-go areas."""
        checks = []
        
        route_line = route.to_linestring()
        
        # Check intersection with no-go areas
        if route_line.intersects(self.region.no_go_areas):
            intersection = route_line.intersection(self.region.no_go_areas)
            
            # Handle different geometry types for intersection
            intersection_points = []
            try:
                # Try to get coordinates if it's a simple geometry
                if intersection.geom_type in ['Point', 'LineString']:
                    intersection_points = list(intersection.coords)
            except (NotImplementedError, AttributeError):
                # Multi-part or complex geometry
                pass
            
            check = ValidationCheck(
                name="No-Go Area Avoidance",
                status=ValidationStatus.FAIL,
                message="Route enters no-go area",
                category="safety",
                severity="critical",
                evidence={
                    "intersection_length": intersection.length if hasattr(intersection, 'length') else 0,
                    "intersection_points": intersection_points
                }
            )
            check.set_clause_compliance('no_go_areas')
        else:
            check = ValidationCheck(
                name="No-Go Area Avoidance",
                status=ValidationStatus.PASS,
                message="Route avoids all no-go areas",
                category="safety",
                severity="critical"
            )
            check.set_clause_compliance('no_go_areas')
        
        checks.append(check)
        
        # Check each waypoint
        for i, (x, y) in enumerate(route.waypoints):
            if not self.region.is_point_safe(x, y):
                checks.append(ValidationCheck(
                    name=f"Waypoint {i+1} Safety",
                    status=ValidationStatus.FAIL,
                    message=f"Waypoint {i+1} is in unsafe waters",
                    category="safety",
                    severity="critical",
                    location=(x, y),
                    waypoint_index=i
                ))
        
        return checks
    
    def _check_safety_contour(self, route: Route) -> List[ValidationCheck]:
        """Check route maintains safe water depth."""
        checks = []
        
        # TODO: Implement depth checking along route
        # This requires depth data from ENC
        
        check = ValidationCheck(
            name="Safety Contour",
            status=ValidationStatus.INFO,
            message="Safety contour check requires depth data",
            category="safety",
            severity="medium"
        )
        check.set_clause_compliance('safety_depth')
        checks.append(check)
        
        return checks
    
    def _check_under_keel_clearance(self, route: Route) -> List[ValidationCheck]:
        """Check under-keel clearance along route."""
        checks = []
        
        # TODO: Implement UKC checking
        # Requires vessel draft and tidal data
        
        check = ValidationCheck(
            name="Under-Keel Clearance",
            status=ValidationStatus.INFO,
            message="UKC check requires vessel draft and tidal data",
            category="safety",
            severity="high"
        )
        checks.append(check)
        
        return checks
    
    def _check_tss_compliance(self, route: Route) -> List[ValidationCheck]:
        """Check TSS compliance."""
        checks = []
        tss = self.region.tss_zones
        
        for i, (x, y) in enumerate(route.waypoints):
            status = tss.get_compliance_status(x, y, route.headings[i])
            
            if status['violations']:
                for violation in status['violations']:
                    tss_check = ValidationCheck(
                        name=f"TSS Compliance WP{i+1}",
                        status=ValidationStatus.FAIL,
                        message=violation,
                        category="tss",
                        severity="high",
                        location=(x, y),
                        waypoint_index=i,
                        evidence=status
                    )
                    tss_check.set_clause_compliance('tss_compliance')
                    checks.append(tss_check)
            elif status['in_tss'] and status['in_correct_lane']:
                tss_check = ValidationCheck(
                    name=f"TSS Compliance WP{i+1}",
                    status=ValidationStatus.PASS,
                    message="Correct TSS lane and direction",
                    category="tss",
                    severity="high",
                    waypoint_index=i
                )
                tss_check.set_clause_compliance('tss_compliance')
                checks.append(tss_check)
        
        return checks
    
    def _check_xtd_corridor(self, route: Route) -> List[ValidationCheck]:
        """Check XTD corridor clearance."""
        checks = []
        
        route_line = route.to_linestring()
        
        # Create XTD corridor (buffer around route)
        corridor = route_line.buffer(self.xtd_limit)
        
        # Check if corridor intersects no-go areas
        if corridor.intersects(self.region.no_go_areas):
            check = ValidationCheck(
                name="XTD Corridor Clearance",
                status=ValidationStatus.WARNING,
                message=f"XTD corridor ({self.xtd_limit}m) enters restricted waters",
                category="geometry",
                severity="medium",
                evidence={
                    "xtd_limit_m": self.xtd_limit,
                    "corridor_area_m2": corridor.area
                }
            )
            check.set_clause_compliance('xtd_corridor')
        else:
            check = ValidationCheck(
                name="XTD Corridor Clearance",
                status=ValidationStatus.PASS,
                message="XTD corridor maintains safe clearance",
                category="geometry",
                severity="medium"
            )
            check.set_clause_compliance('xtd_corridor')
        
        checks.append(check)
        return checks
    
    def _check_turn_radius(self, route: Route) -> List[ValidationCheck]:
        """Check turn radius constraints."""
        checks = []
        min_radius = 100.0  # meters (placeholder)
        
        for i in range(1, len(route.waypoints) - 1):
            # Calculate turn radius using three consecutive points
            p1 = np.array(route.waypoints[i-1])
            p2 = np.array(route.waypoints[i])
            p3 = np.array(route.waypoints[i+1])
            
            # Simple radius calculation (needs improvement)
            v1 = p2 - p1
            v2 = p3 - p2
            angle = np.arccos(np.clip(np.dot(v1, v2) / (np.linalg.norm(v1) * np.linalg.norm(v2)), -1, 1))
            
            if angle > 0.1:  # Significant turn
                # Approximate radius
                radius = np.linalg.norm(v1) / (2 * np.sin(angle/2))
                
                if radius < min_radius:
                    turn_check = ValidationCheck(
                        name=f"Turn Radius WP{i+1}",
                        status=ValidationStatus.WARNING,
                        message=f"Turn radius {radius:.1f}m below minimum {min_radius}m",
                        category="geometry",
                        severity="medium",
                        waypoint_index=i,
                        evidence={"radius_m": radius, "min_radius_m": min_radius}
                    )
                    turn_check.set_clause_compliance('turn_radius')
                    checks.append(turn_check)
        
        if not any(c.status != ValidationStatus.PASS for c in checks):
            turn_check = ValidationCheck(
                name="Turn Radius Constraints",
                status=ValidationStatus.PASS,
                message="All turns within radius constraints",
                category="geometry",
                severity="medium"
            )
            turn_check.set_clause_compliance('turn_radius')
            checks.append(turn_check)
        
        return checks
    
    def _check_route_continuity(self, route: Route) -> List[ValidationCheck]:
        """Check route continuity and connectivity."""
        checks = []
        
        max_leg_length = 50000.0  # 50 km max leg length
        
        for i in range(len(route.waypoints) - 1):
            p1 = np.array(route.waypoints[i])
            p2 = np.array(route.waypoints[i+1])
            leg_length = np.linalg.norm(p2 - p1)
            
            if leg_length > max_leg_length:
                checks.append(ValidationCheck(
                    name=f"Leg Length WP{i+1}-WP{i+2}",
                    status=ValidationStatus.WARNING,
                    message=f"Leg length {leg_length:.1f}m exceeds maximum",
                    category="geometry",
                    severity="low",
                    waypoint_index=i,
                    evidence={"leg_length_m": leg_length, "max_length_m": max_leg_length}
                ))
        
        if not checks:
            checks.append(ValidationCheck(
                name="Route Continuity",
                status=ValidationStatus.PASS,
                message="Route is continuous with reasonable leg lengths",
                category="geometry",
                severity="low"
            ))
        
        return checks
    
    def _check_speed_limits(self, route: Route) -> List[ValidationCheck]:
        """Check speed limit compliance."""
        checks = []
        
        # TODO: Implement speed limit checking based on area restrictions
        
        max_speed = 20.0  # m/s (placeholder)
        
        for i, speed in enumerate(route.velocities):
            if speed > max_speed:
                speed_check = ValidationCheck(
                    name=f"Speed Limit WP{i+1}",
                    status=ValidationStatus.WARNING,
                    message=f"Speed {speed:.1f}m/s exceeds limit {max_speed}m/s",
                    category="speed",
                    severity="medium",
                    waypoint_index=i,
                    evidence={"speed_ms": speed, "limit_ms": max_speed}
                )
                speed_check.set_clause_compliance('speed_limits')
                checks.append(speed_check)
        
        if not checks:
            speed_check = ValidationCheck(
                name="Speed Limits",
                status=ValidationStatus.PASS,
                message="All speeds within limits",
                category="speed",
                severity="medium"
            )
            speed_check.set_clause_compliance('speed_limits')
            checks.append(speed_check)
        
        return checks
    
    def _check_acceleration_limits(self, route: Route) -> List[ValidationCheck]:
        """Check acceleration and deceleration limits."""
        checks = []
        
        max_accel = 0.5  # m/s² (placeholder)
        
        # TODO: Implement acceleration checking between waypoints
        
        checks.append(ValidationCheck(
            name="Acceleration Limits",
            status=ValidationStatus.INFO,
            message="Acceleration check pending implementation",
            category="speed",
            severity="low"
        ))
        
        return checks
    
    def _calculate_min_clearance(self, route: Route) -> float:
        """Calculate minimum clearance to hazards along route."""
        min_clearance = float('inf')
        
        for x, y in route.waypoints:
            clearance = self.region.get_clearance(x, y)
            min_clearance = min(min_clearance, clearance)
        
        return min_clearance
    
    def _calculate_max_turn_rate(self, route: Route) -> float:
        """Calculate maximum turn rate along route."""
        max_turn_rate = 0.0
        
        for i in range(len(route.headings) - 1):
            dtheta = abs(route.headings[i+1] - route.headings[i])
            if dtheta > np.pi:
                dtheta = 2 * np.pi - dtheta
            
            # Estimate time between waypoints
            distance = np.linalg.norm(
                np.array(route.waypoints[i+1]) - np.array(route.waypoints[i])
            )
            time = distance / route.velocities[i] if route.velocities[i] > 0 else 1.0
            
            turn_rate = dtheta / time
            max_turn_rate = max(max_turn_rate, turn_rate)
        
        return max_turn_rate
    
    def _generate_recommendations(self, checks: List[ValidationCheck]) -> List[str]:
        """Generate recommendations based on validation results."""
        recommendations = []
        
        # Check for common issues
        no_go_fails = [c for c in checks if c.name.startswith("No-Go") and c.status == ValidationStatus.FAIL]
        if no_go_fails:
            recommendations.append("Replan route to avoid no-go areas")
        
        tss_fails = [c for c in checks if c.category == "tss" and c.status == ValidationStatus.FAIL]
        if tss_fails:
            recommendations.append("Adjust route to comply with TSS regulations")
        
        speed_warnings = [c for c in checks if c.category == "speed" and c.status == ValidationStatus.WARNING]
        if speed_warnings:
            recommendations.append("Review and adjust speed profile for safety")
        
        colreg_warnings = [c for c in checks if c.category == "colreg" and c.status == ValidationStatus.WARNING]
        if colreg_warnings:
            recommendations.append("Adjust route to comply with COLREG collision avoidance rules")
            # Add specific COLREG recommendations
            encounter_types = set()
            for warning in colreg_warnings:
                if 'encounter_type' in warning.evidence:
                    encounter_types.add(warning.evidence['encounter_type'])
            
            if 'CROSSING' in encounter_types:
                recommendations.append("Consider altering course to starboard for crossing situations")
            if 'HEAD_ON' in encounter_types:
                recommendations.append("Alter course to starboard for head-on encounters")
            if 'OVERTAKING' in encounter_types:
                recommendations.append("Maintain adequate clearance when overtaking")
        
        return recommendations
    
    def _check_colreg_compliance(self, route: Route, traffic_vessels: List[Vessel]) -> List[ValidationCheck]:
        """Check COLREG compliance with traffic vessels."""
        checks = []
        
        if not traffic_vessels:
            checks.append(ValidationCheck(
                name="COLREG Compliance",
                status=ValidationStatus.INFO,
                message="No traffic vessels to check",
                category="colreg",
                severity="low"
            ))
            return checks
        
        # Create own vessel representation
        own_vessel = Vessel(
            mmsi="OWNSHIP",
            position=(0, 0),  # Will be updated for each waypoint
            speed=10.0,  # Default speed in knots
            course=90.0,  # Will be updated
            heading=90.0,
            vessel_type=VesselType.POWER_DRIVEN,
            nav_status=NavigationStatus.UNDERWAY_USING_ENGINE
        )
        
        # Check each waypoint against traffic
        violations_found = False
        for i, (x, y) in enumerate(route.waypoints):
            # Update own vessel position and course
            own_vessel.position = (y / 111000.0 + 37.8, x / 111000.0 / np.cos(np.radians(37.8)) - 122.5)  # Convert to lat/lon
            if i < len(route.headings):
                own_vessel.course = np.degrees(route.headings[i]) % 360
                own_vessel.heading = own_vessel.course
            if i < len(route.velocities):
                own_vessel.speed = route.velocities[i] * 1.94384  # m/s to knots
            
            # Check against each traffic vessel
            for target in traffic_vessels:
                assessment = self.colreg_rules.assess_situation(own_vessel, target)
                
                # Record any required actions
                if assessment.risk_level in ['high', 'medium']:
                    if assessment.recommended_action.name != 'MAINTAIN_COURSE':
                        violations_found = True
                        
                        colreg_check = ValidationCheck(
                            name=f"COLREG WP{i+1} vs {target.mmsi}",
                            status=ValidationStatus.WARNING,
                            message=f"{assessment.encounter_type.name}: {assessment.explanation}",
                            category="colreg",
                            severity="high" if assessment.risk_level == "high" else "medium",
                            location=(x, y),
                            waypoint_index=i,
                            evidence={
                                "encounter_type": assessment.encounter_type.name,
                                "risk_level": assessment.risk_level,
                                "recommended_action": assessment.recommended_action.name,
                                "applicable_rules": assessment.applicable_rules,
                                "target_mmsi": target.mmsi
                            }
                        )
                        
                        # Add clause references for applicable rules
                        for rule_num in assessment.applicable_rules:
                            colreg_check.clause_refs.append({
                                'standard': 'COLREG',
                                'clause': f'Rule {rule_num}',
                                'requirement': assessment.explanation,
                                'status': 'NON_COMPLIANT'
                            })
                        
                        checks.append(colreg_check)
        
        # Add overall pass check if no violations
        if not violations_found:
            colreg_check = ValidationCheck(
                name="COLREG Compliance",
                status=ValidationStatus.PASS,
                message="Route complies with COLREG rules for all traffic",
                category="colreg",
                severity="high"
            )
            colreg_check.set_clause_compliance('colreg_compliance')
            checks.append(colreg_check)
        
        return checks