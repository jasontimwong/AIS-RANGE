"""
COLREG Module - International Regulations for Preventing Collisions at Sea

This module implements COLREG rules for maritime collision avoidance.
"""

from .rules import (
    COLREGRules,
    COLREGValidator,
    COLREGAssessment,
    Vessel,
    VesselType,
    NavigationStatus,
    EncounterType,
    ActionType,
    Visibility,
    CPAData,
    format_colreg_report
)

__all__ = [
    'COLREGRules',
    'COLREGValidator',
    'COLREGAssessment',
    'Vessel',
    'VesselType',
    'NavigationStatus',
    'EncounterType',
    'ActionType',
    'Visibility',
    'CPAData',
    'format_colreg_report'
]