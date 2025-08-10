"""
TSS (Traffic Separation Scheme) Layers Module
Handles TSS zones, lanes, and compliance rules per IMO regulations.
"""

from typing import List, Dict, Optional, Tuple
from dataclasses import dataclass
from enum import Enum
import numpy as np
from shapely.geometry import Polygon, LineString, Point, MultiPolygon
from shapely.ops import unary_union
import logging

logger = logging.getLogger(__name__)


class TSSDirection(Enum):
    """TSS traffic flow direction."""
    INBOUND = "inbound"
    OUTBOUND = "outbound"
    TWO_WAY = "two-way"
    UNDEFINED = "undefined"


@dataclass
class TSSLane:
    """Represents a single TSS traffic lane."""
    geometry: Polygon  # Lane polygon (TSSLPT)
    direction: TSSDirection
    orientation: Optional[float] = None  # Orientation in degrees
    category: Optional[int] = None  # CATTSS value
    lane_id: Optional[str] = None
    
    def get_centerline(self) -> LineString:
        """Extract approximate centerline of lane."""
        # TODO: Implement proper centerline extraction
        # For now, use simple centroid-based approach
        bounds = self.geometry.bounds
        return LineString([
            (bounds[0], (bounds[1] + bounds[3]) / 2),
            (bounds[2], (bounds[1] + bounds[3]) / 2)
        ])
    
    def is_compliant_heading(self, heading: float, tolerance: float = 20.0) -> bool:
        """
        Check if vessel heading is compliant with lane direction.
        
        Args:
            heading: Vessel heading in degrees (0-360)
            tolerance: Allowed deviation in degrees
            
        Returns:
            True if heading is compliant
        """
        if self.orientation is None:
            return True  # No orientation restriction
        
        # Calculate angular difference
        diff = abs(heading - self.orientation)
        if diff > 180:
            diff = 360 - diff
        
        return diff <= tolerance


@dataclass
class TSSZones:
    """Complete TSS structure with all components."""
    lanes: List[TSSLane]  # Traffic lanes (TSSLPT)
    separation_zones: List[Polygon]  # Separation zones (TSEZNE)
    boundaries: List[LineString]  # Scheme boundaries (TSSBND)
    separation_lines: List[LineString]  # Separation lines (TSELNE)
    precautionary_areas: List[Polygon]  # Precautionary areas (PRCARE)
    bounds: Tuple[float, float, float, float]  # Overall bounds
    
    def get_lane_for_point(self, x: float, y: float) -> Optional[TSSLane]:
        """Find which TSS lane contains a point."""
        pt = Point(x, y)
        for lane in self.lanes:
            if lane.geometry.contains(pt):
                return lane
        return None
    
    def is_in_separation_zone(self, x: float, y: float) -> bool:
        """Check if point is in a separation zone."""
        pt = Point(x, y)
        for zone in self.separation_zones:
            if zone.contains(pt):
                return True
        return False
    
    def is_in_precautionary_area(self, x: float, y: float) -> bool:
        """Check if point is in a precautionary area."""
        pt = Point(x, y)
        for area in self.precautionary_areas:
            if area.contains(pt):
                return True
        return False
    
    def get_compliance_status(self, x: float, y: float, heading: float) -> Dict[str, any]:
        """
        Get TSS compliance status for a vessel position and heading.
        
        Returns:
            Dictionary with compliance information
        """
        status = {
            'in_tss': False,
            'in_correct_lane': False,
            'in_separation_zone': False,
            'in_precautionary_area': False,
            'heading_compliant': False,
            'current_lane': None,
            'violations': []
        }
        
        # Check position
        lane = self.get_lane_for_point(x, y)
        if lane:
            status['in_tss'] = True
            status['current_lane'] = lane.lane_id
            
            # Check heading compliance
            if lane.is_compliant_heading(heading):
                status['heading_compliant'] = True
                status['in_correct_lane'] = True
            else:
                status['violations'].append('Wrong direction in TSS lane')
        
        # Check violations
        if self.is_in_separation_zone(x, y):
            status['in_separation_zone'] = True
            status['violations'].append('Vessel in TSS separation zone')
        
        if self.is_in_precautionary_area(x, y):
            status['in_precautionary_area'] = True
            # Not necessarily a violation
        
        return status


class TSSLayerBuilder:
    """Builds TSS layer structure from ENC features."""
    
    def build_from_features(self, tss_features: Dict[str, List]) -> Optional[TSSZones]:
        """
        Build TSS zones from S-57 features.
        
        Args:
            tss_features: Dictionary of TSS features by object class
            
        Returns:
            TSSZones object or None if no TSS present
        """
        if not tss_features:
            return None
        
        # Extract lanes (TSSLPT)
        lanes = self._build_lanes(tss_features.get('TSSLPT', []))
        
        # Extract separation zones (TSEZNE)
        sep_zones = self._extract_polygons(tss_features.get('TSEZNE', []))
        
        # Extract boundaries (TSSBND)
        boundaries = self._extract_lines(tss_features.get('TSSBND', []))
        
        # Extract separation lines (TSELNE)
        sep_lines = self._extract_lines(tss_features.get('TSELNE', []))
        
        # Extract precautionary areas (PRCARE)
        prec_areas = self._extract_polygons(tss_features.get('PRCARE', []))
        
        # Calculate overall bounds
        all_geoms = []
        for lane in lanes:
            all_geoms.append(lane.geometry)
        all_geoms.extend(sep_zones)
        all_geoms.extend(boundaries)
        all_geoms.extend(sep_lines)
        all_geoms.extend(prec_areas)
        
        if all_geoms:
            combined = unary_union(all_geoms)
            bounds = combined.bounds
        else:
            bounds = (0, 0, 0, 0)
        
        return TSSZones(
            lanes=lanes,
            separation_zones=sep_zones,
            boundaries=boundaries,
            separation_lines=sep_lines,
            precautionary_areas=prec_areas,
            bounds=bounds
        )
    
    def _build_lanes(self, lane_features: List) -> List[TSSLane]:
        """Build TSS lanes from TSSLPT features."""
        lanes = []
        
        for idx, feature in enumerate(lane_features):
            if not isinstance(feature.geometry, Polygon):
                continue
            
            # Extract attributes
            orient = feature.attributes.get('ORIENT')
            cattss = feature.attributes.get('CATTSS')
            trafic = feature.attributes.get('TRAFIC')
            
            # Determine direction
            direction = TSSDirection.UNDEFINED
            if trafic == 1:
                direction = TSSDirection.INBOUND
            elif trafic == 2:
                direction = TSSDirection.OUTBOUND
            elif trafic == 3:
                direction = TSSDirection.TWO_WAY
            
            lane = TSSLane(
                geometry=feature.geometry,
                direction=direction,
                orientation=float(orient) if orient else None,
                category=int(cattss) if cattss else None,
                lane_id=f"lane_{idx}"
            )
            
            lanes.append(lane)
        
        return lanes
    
    def _extract_polygons(self, features: List) -> List[Polygon]:
        """Extract polygon geometries from features."""
        polygons = []
        for feature in features:
            if isinstance(feature.geometry, Polygon):
                polygons.append(feature.geometry)
            elif isinstance(feature.geometry, MultiPolygon):
                polygons.extend(feature.geometry.geoms)
        return polygons
    
    def _extract_lines(self, features: List) -> List[LineString]:
        """Extract line geometries from features."""
        lines = []
        for feature in features:
            if isinstance(feature.geometry, LineString):
                lines.append(feature.geometry)
        return lines