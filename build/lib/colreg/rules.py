#!/usr/bin/env python3
"""
COLREG Rules Formalization Module

Implements International Regulations for Preventing Collisions at Sea (COLREG)
Rules 7, 8, 10, 13, 14, 15, 16, 17, 19 as per IMO requirements.

Reference: IMO COLREG 1972 (as amended)
"""

from dataclasses import dataclass, field
from enum import Enum, auto
from typing import List, Optional, Tuple, Dict, Any
import numpy as np
from datetime import datetime
import logging

logger = logging.getLogger(__name__)


class VesselType(Enum):
    """Vessel types per COLREG Rule 3"""
    POWER_DRIVEN = auto()
    SAILING = auto()
    FISHING = auto()
    NOT_UNDER_COMMAND = auto()
    RESTRICTED_MANEUVERABILITY = auto()
    CONSTRAINED_BY_DRAFT = auto()
    ENGAGED_IN_TOWING = auto()
    SEAPLANE = auto()


class NavigationStatus(Enum):
    """Navigation status per AIS/COLREG"""
    UNDERWAY_USING_ENGINE = 0
    AT_ANCHOR = 1
    NOT_UNDER_COMMAND = 2
    RESTRICTED_MANEUVERABILITY = 3
    CONSTRAINED_BY_DRAFT = 4
    MOORED = 5
    AGROUND = 6
    ENGAGED_IN_FISHING = 7
    UNDERWAY_SAILING = 8
    RESERVED = 9


class EncounterType(Enum):
    """Types of vessel encounters"""
    HEAD_ON = auto()  # Rule 14
    CROSSING = auto()  # Rule 15
    OVERTAKING = auto()  # Rule 13
    NO_RISK = auto()
    SAFE_PASSING = auto()


class ActionType(Enum):
    """COLREG action types"""
    MAINTAIN_COURSE = auto()
    ALTER_COURSE_STARBOARD = auto()
    ALTER_COURSE_PORT = auto()
    REDUCE_SPEED = auto()
    STOP = auto()
    REVERSE = auto()
    SOUND_SIGNAL = auto()


class Visibility(Enum):
    """Visibility conditions"""
    GOOD = auto()  # > 5 nm
    MODERATE = auto()  # 2-5 nm
    POOR = auto()  # 0.5-2 nm
    FOG = auto()  # < 0.5 nm


@dataclass
class Vessel:
    """Vessel data structure"""
    mmsi: str
    position: Tuple[float, float]  # (lat, lon)
    speed: float  # knots
    course: float  # degrees
    heading: float  # degrees
    vessel_type: VesselType = VesselType.POWER_DRIVEN
    nav_status: NavigationStatus = NavigationStatus.UNDERWAY_USING_ENGINE
    length: float = 100.0  # meters
    beam: float = 20.0  # meters
    draft: float = 5.0  # meters
    timestamp: datetime = field(default_factory=datetime.now)


@dataclass
class CPAData:
    """Closest Point of Approach data"""
    distance: float  # nautical miles
    time: float  # minutes
    bearing: float  # degrees
    relative_bearing: float  # degrees
    crossing_situation: Optional[str] = None  # "port", "starboard", "ahead", "astern"


@dataclass
class COLREGAssessment:
    """COLREG situation assessment"""
    encounter_type: EncounterType
    applicable_rules: List[int]
    own_vessel_obligations: List[str]
    target_vessel_obligations: List[str]
    recommended_action: ActionType
    action_details: Dict[str, Any]
    risk_level: str  # "high", "medium", "low", "none"
    explanation: str
    sound_signals: Optional[List[str]] = None


class COLREGRules:
    """
    COLREG Rules implementation
    
    Implements Rules 7, 8, 10, 13, 14, 15, 16, 17, 19
    """
    
    def __init__(self, safety_distance_nm: float = 1.0, safety_time_min: float = 10.0):
        """
        Initialize COLREG rules engine
        
        Args:
            safety_distance_nm: Minimum safe CPA distance in nautical miles
            safety_time_min: Minimum safe TCPA in minutes
        """
        self.safety_distance_nm = safety_distance_nm
        self.safety_time_min = safety_time_min
        
    def assess_situation(self, 
                        own_vessel: Vessel, 
                        target_vessel: Vessel,
                        visibility: Visibility = Visibility.GOOD) -> COLREGAssessment:
        """
        Assess COLREG situation between two vessels
        
        Args:
            own_vessel: Own vessel data
            target_vessel: Target vessel data
            visibility: Current visibility conditions
            
        Returns:
            COLREGAssessment with recommendations
        """
        # Calculate CPA/TCPA
        cpa_data = self._calculate_cpa(own_vessel, target_vessel)
        
        # Rule 7: Risk of collision assessment
        risk_exists = self._assess_risk_of_collision(cpa_data)
        
        if not risk_exists:
            return COLREGAssessment(
                encounter_type=EncounterType.NO_RISK,
                applicable_rules=[7],
                own_vessel_obligations=["Maintain watch"],
                target_vessel_obligations=["Maintain watch"],
                recommended_action=ActionType.MAINTAIN_COURSE,
                action_details={},
                risk_level="none",
                explanation="No risk of collision exists"
            )
        
        # Determine encounter type
        encounter_type = self._determine_encounter_type(own_vessel, target_vessel, cpa_data)
        
        # Apply appropriate rules based on encounter type
        if encounter_type == EncounterType.HEAD_ON:
            return self._apply_rule_14(own_vessel, target_vessel, cpa_data)
        elif encounter_type == EncounterType.CROSSING:
            return self._apply_rule_15(own_vessel, target_vessel, cpa_data)
        elif encounter_type == EncounterType.OVERTAKING:
            return self._apply_rule_13(own_vessel, target_vessel, cpa_data)
        else:
            return self._apply_rule_8(own_vessel, target_vessel, cpa_data)
    
    def _calculate_cpa(self, own_vessel: Vessel, target_vessel: Vessel) -> CPAData:
        """
        Calculate Closest Point of Approach (CPA) and Time to CPA (TCPA)
        
        Args:
            own_vessel: Own vessel data
            target_vessel: Target vessel data
            
        Returns:
            CPAData with CPA/TCPA information
        """
        # Convert positions to cartesian coordinates (simplified flat earth)
        lat1, lon1 = own_vessel.position
        lat2, lon2 = target_vessel.position
        
        # Relative position (nm) - Note: x is east-west, y is north-south
        dx = (lon2 - lon1) * 60 * np.cos(np.radians((lat1 + lat2) / 2))
        dy = (lat2 - lat1) * 60
        
        # Relative velocity (knots) - Course is bearing from north
        # In navigation: 0° = North, 90° = East, 180° = South, 270° = West
        vx1 = own_vessel.speed * np.sin(np.radians(own_vessel.course))
        vy1 = own_vessel.speed * np.cos(np.radians(own_vessel.course))
        vx2 = target_vessel.speed * np.sin(np.radians(target_vessel.course))
        vy2 = target_vessel.speed * np.cos(np.radians(target_vessel.course))
        
        # Relative velocity of target with respect to own vessel
        dvx = vx2 - vx1
        dvy = vy2 - vy1
        
        # Calculate TCPA
        dv_squared = dvx**2 + dvy**2
        if dv_squared < 0.01:  # Nearly parallel courses or both stopped
            tcpa = float('inf') if np.sqrt(dx**2 + dy**2) > self.safety_distance_nm else 0.1
            cpa = np.sqrt(dx**2 + dy**2)
        else:
            tcpa = -(dx * dvx + dy * dvy) / dv_squared * 60  # minutes
            if tcpa <= 0:  # Vessels diverging or past CPA
                tcpa = 0.001  # Small positive value to indicate past/diverging
                cpa = np.sqrt(dx**2 + dy**2)
            else:
                # Position at CPA
                x_cpa = dx + dvx * tcpa / 60
                y_cpa = dy + dvy * tcpa / 60
                cpa = np.sqrt(x_cpa**2 + y_cpa**2)
        
        # Calculate bearing from own vessel to target (true bearing)
        # Note: atan2(east, north) for navigation bearing
        bearing = (np.degrees(np.arctan2(dx, dy)) % 360)
        
        # Calculate relative bearing from own vessel's heading
        relative_bearing = (bearing - own_vessel.heading) % 360
        
        # Determine crossing situation based on relative bearing
        # According to COLREG sectors:
        # Ahead: 355° to 5° (or within 10° arc ahead)
        # Starboard: 5° to 112.5° (starboard beam)
        # Port: 247.5° to 355° (port beam) 
        # Astern: 112.5° to 247.5° (abaft the beam)
        
        if relative_bearing <= 10 or relative_bearing >= 350:
            crossing_situation = "ahead"
        elif 10 < relative_bearing <= 112.5:
            crossing_situation = "starboard"
        elif 247.5 <= relative_bearing < 350:
            crossing_situation = "port"
        else:  # 112.5 < relative_bearing < 247.5
            crossing_situation = "astern"
        
        return CPAData(
            distance=cpa,
            time=max(tcpa, 0),  # Ensure non-negative
            bearing=bearing,
            relative_bearing=relative_bearing,
            crossing_situation=crossing_situation
        )
    
    def _assess_risk_of_collision(self, cpa_data: CPAData) -> bool:
        """
        Rule 7: Risk of Collision
        
        Determines if risk of collision exists based on CPA/TCPA
        """
        if cpa_data.time <= 0 or cpa_data.time == float('inf'):
            return False
        
        # Risk exists if:
        # 1. CPA is within safety distance AND time is reasonable, OR
        # 2. CPA is very close (< 0.1 nm) regardless of time (up to 30 min), OR  
        # 3. TCPA is very short (< 2 min) and CPA is within 2x safety distance
        very_close_cpa = cpa_data.distance < 0.1  # 185 meters
        close_cpa = cpa_data.distance < self.safety_distance_nm
        moderate_cpa = cpa_data.distance < self.safety_distance_nm * 2
        
        imminent = cpa_data.time < 2.0
        near_term = cpa_data.time < self.safety_time_min
        reasonable_time = cpa_data.time < 30.0
        
        return (
            (very_close_cpa and reasonable_time) or
            (close_cpa and near_term) or
            (moderate_cpa and imminent)
        )
    
    def _determine_encounter_type(self, 
                                 own_vessel: Vessel,
                                 target_vessel: Vessel,
                                 cpa_data: CPAData) -> EncounterType:
        """
        Determine the type of encounter based on relative positions and courses
        """
        # Calculate relative course difference
        relative_course = abs(own_vessel.course - target_vessel.course)
        if relative_course > 180:
            relative_course = 360 - relative_course
        
        # Rule 13: Overtaking
        # A vessel is overtaking when coming up from more than 22.5° abaft the beam
        # This means the overtaking vessel sees the other vessel ahead in sectors > 112.5°
        if cpa_data.crossing_situation == "ahead":
            # Check if we're overtaking (coming from behind, faster speed)
            if own_vessel.speed > target_vessel.speed * 1.1:  # 10% faster
                # Check if courses are similar (within 45 degrees)
                if relative_course < 45:
                    return EncounterType.OVERTAKING
        
        # For target vessel perspective - if target is astern and approaching
        if cpa_data.crossing_situation == "astern":
            # Target is behind us - check if they're overtaking us
            if target_vessel.speed > own_vessel.speed * 1.1:
                if relative_course < 45:
                    # We're being overtaken but not the overtaking vessel
                    return EncounterType.SAFE_PASSING
        
        # Rule 14: Head-on situation
        # Vessels meeting on reciprocal or nearly reciprocal courses
        if relative_course > 165:  # Within 15 degrees of reciprocal
            if cpa_data.crossing_situation == "ahead":
                # Also check that vessels are actually approaching
                if cpa_data.time > 0 and cpa_data.time < self.safety_time_min * 2:
                    return EncounterType.HEAD_ON
        
        # Rule 15: Crossing situation
        # Not head-on, not overtaking, but risk exists
        if cpa_data.crossing_situation in ["port", "starboard"]:
            # Crossing requires intersecting courses
            if 30 < relative_course < 150:  # Not parallel, not head-on
                return EncounterType.CROSSING
        
        return EncounterType.SAFE_PASSING
    
    def _apply_rule_8(self, 
                     own_vessel: Vessel,
                     target_vessel: Vessel,
                     cpa_data: CPAData) -> COLREGAssessment:
        """
        Rule 8: Action to avoid collision
        
        Any action shall be positive, made in ample time and with due regard
        to the observance of good seamanship
        """
        return COLREGAssessment(
            encounter_type=EncounterType.SAFE_PASSING,
            applicable_rules=[7, 8],
            own_vessel_obligations=[
                "Take early and substantial action",
                "Result in passing at safe distance",
                "Check effectiveness until finally past"
            ],
            target_vessel_obligations=["Maintain watch"],
            recommended_action=ActionType.ALTER_COURSE_STARBOARD,
            action_details={
                "course_change": 30,
                "resume_after_nm": 2
            },
            risk_level="medium",
            explanation="Rule 8: Take early and substantial action to avoid collision"
        )
    
    def _apply_rule_10(self, 
                      own_vessel: Vessel,
                      target_vessel: Vessel,
                      is_tss: bool = False) -> Dict[str, Any]:
        """
        Rule 10: Traffic Separation Schemes
        
        Returns TSS-specific requirements if applicable
        """
        if not is_tss:
            return {}
        
        return {
            "tss_obligations": [
                "Proceed in appropriate traffic lane",
                "Keep clear of separation line/zone",
                "Join/leave at smallest angle",
                "Avoid crossing traffic lanes"
            ]
        }
    
    def _apply_rule_13(self,
                      own_vessel: Vessel,
                      target_vessel: Vessel,
                      cpa_data: CPAData) -> COLREGAssessment:
        """
        Rule 13: Overtaking
        
        Any vessel overtaking shall keep out of the way of the vessel being overtaken
        """
        return COLREGAssessment(
            encounter_type=EncounterType.OVERTAKING,
            applicable_rules=[13, 16],
            own_vessel_obligations=[
                "Keep out of way of vessel being overtaken",
                "Give way vessel - take early and substantial action"
            ],
            target_vessel_obligations=[
                "Stand-on vessel - maintain course and speed"
            ],
            recommended_action=ActionType.ALTER_COURSE_PORT if cpa_data.crossing_situation == "starboard" 
                             else ActionType.ALTER_COURSE_STARBOARD,
            action_details={
                "course_change": 20,
                "maintain_until": "finally past and clear"
            },
            risk_level="medium",
            explanation="Rule 13: Overtaking vessel must keep clear",
            sound_signals=["Two prolonged, one short"] if cpa_data.crossing_situation == "starboard"
                        else ["Two prolonged, two short"]
        )
    
    def _apply_rule_14(self,
                      own_vessel: Vessel,
                      target_vessel: Vessel,
                      cpa_data: CPAData) -> COLREGAssessment:
        """
        Rule 14: Head-on situation
        
        When two power-driven vessels are meeting head-on, each shall alter course to starboard
        """
        return COLREGAssessment(
            encounter_type=EncounterType.HEAD_ON,
            applicable_rules=[14],
            own_vessel_obligations=[
                "Alter course to starboard",
                "Pass port to port"
            ],
            target_vessel_obligations=[
                "Alter course to starboard",
                "Pass port to port"
            ],
            recommended_action=ActionType.ALTER_COURSE_STARBOARD,
            action_details={
                "course_change": 15,
                "pass_on": "port"
            },
            risk_level="high",
            explanation="Rule 14: Head-on situation - both vessels alter to starboard",
            sound_signals=["One short blast"]
        )
    
    def _apply_rule_15(self,
                      own_vessel: Vessel,
                      target_vessel: Vessel,
                      cpa_data: CPAData) -> COLREGAssessment:
        """
        Rule 15: Crossing situation
        
        When two power-driven vessels are crossing, the vessel with the other
        on her starboard side shall keep out of the way
        """
        # Determine give-way vessel
        if cpa_data.crossing_situation == "starboard":
            # Target on our starboard - we are give-way vessel
            return COLREGAssessment(
                encounter_type=EncounterType.CROSSING,
                applicable_rules=[15, 16],
                own_vessel_obligations=[
                    "Give way vessel",
                    "Avoid crossing ahead",
                    "Take early and substantial action"
                ],
                target_vessel_obligations=[
                    "Stand-on vessel",
                    "Maintain course and speed",
                    "May take action per Rule 17(a)(ii) if needed"
                ],
                recommended_action=ActionType.ALTER_COURSE_STARBOARD,
                action_details={
                    "course_change": 30,
                    "avoid": "crossing ahead",
                    "preference": "pass astern"
                },
                risk_level="high",
                explanation="Rule 15: Give way to vessel on starboard - alter course to starboard to pass astern",
                sound_signals=["One short blast"]
            )
        else:
            # Target on our port - we are stand-on vessel
            return COLREGAssessment(
                encounter_type=EncounterType.CROSSING,
                applicable_rules=[15, 17],
                own_vessel_obligations=[
                    "Stand-on vessel",
                    "Maintain course and speed",
                    "May take action if other vessel not taking action",
                    "Shall take action if collision cannot be avoided"
                ],
                target_vessel_obligations=[
                    "Give way vessel",
                    "Take early and substantial action",
                    "Avoid crossing ahead"
                ],
                recommended_action=ActionType.MAINTAIN_COURSE,
                action_details={
                    "monitor": True,
                    "ready_action": "reduce speed or alter course to starboard if needed"
                },
                risk_level="medium",
                explanation="Rule 15/17: Stand-on vessel - maintain course and speed, monitor give-way vessel"
            )
    
    def _apply_rule_16(self,
                      own_vessel: Vessel,
                      target_vessel: Vessel) -> Dict[str, Any]:
        """
        Rule 16: Action by give-way vessel
        
        Every vessel directed to keep out of the way shall take early and substantial action
        """
        return {
            "give_way_requirements": [
                "Take early action",
                "Take substantial action",
                "Result in passing at safe distance"
            ]
        }
    
    def _apply_rule_17(self,
                      own_vessel: Vessel,
                      target_vessel: Vessel,
                      cpa_data: CPAData) -> Dict[str, Any]:
        """
        Rule 17: Action by stand-on vessel
        
        (a)(i) Stand-on vessel shall maintain course and speed
        (a)(ii) May take action to avoid collision if give-way vessel not taking action
        (b) Shall take action when collision cannot be avoided by give-way vessel alone
        """
        return {
            "stand_on_requirements": [
                "Initially maintain course and speed",
                "Monitor give-way vessel action",
                "May take avoiding action if needed",
                "Shall not alter course to port for vessel on port side"
            ],
            "escalation_thresholds": {
                "may_act_tcpa_min": 5,
                "shall_act_tcpa_min": 2
            }
        }
    
    def _apply_rule_19(self,
                      own_vessel: Vessel,
                      target_vessel: Vessel,
                      visibility: Visibility) -> COLREGAssessment:
        """
        Rule 19: Conduct in restricted visibility
        
        Special rules apply when vessels are not in sight of one another in restricted visibility
        """
        if visibility not in [Visibility.POOR, Visibility.FOG]:
            return None
        
        return COLREGAssessment(
            encounter_type=EncounterType.NO_RISK,
            applicable_rules=[19],
            own_vessel_obligations=[
                "Proceed at safe speed",
                "Sound fog signals",
                "Navigate with extreme caution",
                "Stop engines when fog signal heard forward of beam"
            ],
            target_vessel_obligations=["Same obligations"],
            recommended_action=ActionType.REDUCE_SPEED,
            action_details={
                "speed_reduction": 0.5,
                "fog_signals": True,
                "radar_watch": True
            },
            risk_level="high",
            explanation="Rule 19: Restricted visibility - reduce speed and sound fog signals",
            sound_signals=["One prolonged blast every 2 minutes"]
        )
    
    def validate_action(self, 
                       assessment: COLREGAssessment,
                       proposed_action: Dict[str, Any]) -> Tuple[bool, str]:
        """
        Validate that a proposed action complies with COLREG rules
        
        Args:
            assessment: Current COLREG assessment
            proposed_action: Proposed maneuver action
            
        Returns:
            (is_valid, explanation)
        """
        # Check basic compliance
        if assessment.recommended_action == ActionType.MAINTAIN_COURSE:
            if proposed_action.get("course_change", 0) > 5:
                return (False, "Stand-on vessel should maintain course and speed")
        
        if assessment.recommended_action == ActionType.ALTER_COURSE_STARBOARD:
            if proposed_action.get("course_change", 0) < -5:  # Port turn
                return (False, "Should alter course to starboard per COLREG rules")
        
        # Check for sufficient action (Rule 8)
        if "Give way" in assessment.own_vessel_obligations[0]:
            if abs(proposed_action.get("course_change", 0)) < 10:
                return (False, "Action must be substantial and readily apparent (Rule 8)")
        
        return (True, "Action complies with COLREG rules")


class COLREGValidator:
    """
    Validates route plans against COLREG rules
    """
    
    def __init__(self, rules: COLREGRules = None):
        self.rules = rules or COLREGRules()
    
    def validate_route(self, 
                       planned_route: List[Tuple[float, float]],
                       own_vessel: Vessel,
                       traffic_vessels: List[Vessel],
                       timestamps: List[datetime] = None) -> List[Dict[str, Any]]:
        """
        Validate a planned route against COLREG rules with traffic
        
        Args:
            planned_route: List of (lat, lon) waypoints
            own_vessel: Own vessel characteristics
            traffic_vessels: List of traffic vessels
            timestamps: Expected time at each waypoint
            
        Returns:
            List of validation results with any violations
        """
        violations = []
        
        for i, waypoint in enumerate(planned_route):
            # Update own vessel position for this waypoint
            own_vessel.position = waypoint
            if timestamps:
                own_vessel.timestamp = timestamps[i]
            
            # Check against each traffic vessel
            for target in traffic_vessels:
                assessment = self.rules.assess_situation(own_vessel, target)
                
                # Check if route violates COLREG rules
                if assessment.risk_level in ["high", "medium"]:
                    if assessment.recommended_action != ActionType.MAINTAIN_COURSE:
                        violations.append({
                            "waypoint_index": i,
                            "position": waypoint,
                            "target_mmsi": target.mmsi,
                            "encounter_type": assessment.encounter_type.name,
                            "violated_rules": assessment.applicable_rules,
                            "required_action": assessment.recommended_action.name,
                            "explanation": assessment.explanation
                        })
        
        return violations


def format_colreg_report(assessment: COLREGAssessment) -> str:
    """
    Format COLREG assessment into human-readable report
    
    Args:
        assessment: COLREG assessment result
        
    Returns:
        Formatted report string
    """
    report = []
    report.append("=" * 60)
    report.append("COLREG ASSESSMENT REPORT")
    report.append("=" * 60)
    report.append(f"Encounter Type: {assessment.encounter_type.name}")
    report.append(f"Risk Level: {assessment.risk_level.upper()}")
    report.append(f"Applicable Rules: {', '.join(map(str, assessment.applicable_rules))}")
    report.append("")
    
    report.append("Own Vessel Obligations:")
    for obligation in assessment.own_vessel_obligations:
        report.append(f"  • {obligation}")
    report.append("")
    
    report.append("Target Vessel Obligations:")
    for obligation in assessment.target_vessel_obligations:
        report.append(f"  • {obligation}")
    report.append("")
    
    report.append(f"Recommended Action: {assessment.recommended_action.name}")
    if assessment.action_details:
        report.append("Action Details:")
        for key, value in assessment.action_details.items():
            report.append(f"  • {key}: {value}")
    report.append("")
    
    if assessment.sound_signals:
        report.append("Sound Signals:")
        for signal in assessment.sound_signals:
            report.append(f"  • {signal}")
        report.append("")
    
    report.append(f"Explanation: {assessment.explanation}")
    report.append("=" * 60)
    
    return "\n".join(report)