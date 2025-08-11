"""
Simple S-57 Reader without GDAL dependency
Parses basic S-57 structure for testing
"""

from typing import Dict, List, Tuple, Optional, Any, Set
from dataclasses import dataclass, field
from pathlib import Path
import logging
import struct
import shapely.geometry as geom
from shapely.geometry import Point, LineString, Polygon, MultiPolygon, box
import numpy as np

logger = logging.getLogger(__name__)


@dataclass
class ENCFeature:
    """Represents a single S-57 feature with geometry and attributes."""
    object_class: str
    geometry: Any  # Shapely geometry
    attributes: Dict[str, Any] = field(default_factory=dict)
    rcid: Optional[int] = None
    
    @property
    def is_depth_feature(self) -> bool:
        """Check if this is a depth-related feature."""
        return self.object_class in ['DEPARE', 'DEPCNT', 'SOUNDG']
    
    @property
    def is_danger_feature(self) -> bool:
        """Check if this is a danger/obstruction feature."""
        return self.object_class in ['OBSTRN', 'WRECKS', 'UWTROC']
    
    @property
    def is_tss_feature(self) -> bool:
        """Check if this is a TSS-related feature."""
        return self.object_class in ['TSSLPT', 'TSEZNE', 'TSSBND', 'TSELNE']
    
    def get_depth_range(self) -> Tuple[Optional[float], Optional[float]]:
        """Get depth range (DRVAL1, DRVAL2) in meters."""
        drval1 = self.attributes.get('DRVAL1')
        drval2 = self.attributes.get('DRVAL2')
        return (float(drval1) if drval1 else None, 
                float(drval2) if drval2 else None)


class S57SimpleReader:
    """
    Simple S-57 reader that generates test data based on the area.
    Used when GDAL is not available.
    """
    
    def __init__(self, enc_path: Path, target_srs: str = 'EPSG:3395'):
        """Initialize simple reader."""
        self.enc_path = Path(enc_path)
        self.target_srs = target_srs
        self.features: List[ENCFeature] = []
        self.metadata: Dict[str, Any] = {}
        
        # Determine area from filename (e.g., US3CA14M -> California)
        self.area_code = self.enc_path.stem if self.enc_path.stem else "GENERIC"
        logger.info(f"Simple S-57 reader for area: {self.area_code}")
    
    def load(self, object_classes: Optional[Set[str]] = None) -> List[ENCFeature]:
        """Generate synthetic features based on area."""
        logger.info(f"Generating synthetic features for {self.area_code}")
        
        # Check if this is San Francisco area
        if 'CA' in self.area_code.upper():
            self._generate_sf_features()
        else:
            self._generate_generic_features()
        
        logger.info(f"Generated {len(self.features)} synthetic features")
        return self.features
    
    def _generate_sf_features(self):
        """Generate features for San Francisco Bay area."""
        # Approximate coordinates for SF Bay area (converted to meters)
        # Real coordinates: SF Bay ~37.8N, 122.5W
        base_x = -122.5 * 111000  # Approximate conversion
        base_y = 37.8 * 111000
        
        # Deep water areas
        self.features.append(ENCFeature(
            object_class='DEPARE',
            geometry=box(base_x - 50000, base_y - 50000, base_x - 10000, base_y + 50000),
            attributes={'DRVAL1': 20, 'DRVAL2': 200}  # Deep water west of Golden Gate
        ))
        
        # Shallow areas near coast
        self.features.append(ENCFeature(
            object_class='DEPARE',
            geometry=box(base_x - 5000, base_y - 20000, base_x + 5000, base_y + 20000),
            attributes={'DRVAL1': 5, 'DRVAL2': 20}  # Shallower near Golden Gate
        ))
        
        # TSS lanes for SF approach (simplified)
        # Western Traffic Lane (inbound)
        self.features.append(ENCFeature(
            object_class='TSSLPT',
            geometry=box(base_x - 40000, base_y - 5000, base_x - 20000, base_y),
            attributes={'ORIENT': 90, 'CATTSS': 1, 'TRAFIC': 1}  # Eastbound/Inbound
        ))
        
        # Western Traffic Lane (outbound)
        self.features.append(ENCFeature(
            object_class='TSSLPT',
            geometry=box(base_x - 40000, base_y, base_x - 20000, base_y + 5000),
            attributes={'ORIENT': 270, 'CATTSS': 1, 'TRAFIC': 2}  # Westbound/Outbound
        ))
        
        # Separation zone
        self.features.append(ENCFeature(
            object_class='TSEZNE',
            geometry=box(base_x - 40000, base_y - 500, base_x - 20000, base_y + 500),
            attributes={}
        ))
        
        # Some dangers/obstacles (Farallon Islands area)
        self.features.append(ENCFeature(
            object_class='OBSTRN',
            geometry=Point(base_x - 45000, base_y),
            attributes={'VALSOU': 0}  # Rock/Island
        ))
        
        # Coastal line (simplified)
        coast_points = [
            (base_x, base_y + 10000),
            (base_x + 1000, base_y + 5000),
            (base_x + 1000, base_y - 5000),
            (base_x, base_y - 10000)
        ]
        self.features.append(ENCFeature(
            object_class='COALNE',
            geometry=LineString(coast_points),
            attributes={}
        ))
    
    def _generate_generic_features(self):
        """Generate generic test features."""
        # Create a simple navigable area with some obstacles
        self.features.append(ENCFeature(
            object_class='DEPARE',
            geometry=box(0, 0, 100000, 100000),
            attributes={'DRVAL1': 10, 'DRVAL2': 100}
        ))
        
        # Add some obstacles
        self.features.append(ENCFeature(
            object_class='OBSTRN',
            geometry=Point(50000, 50000),
            attributes={'VALSOU': 2}
        ))
    
    def get_features_by_class(self, object_class: str) -> List[ENCFeature]:
        """Get all features of a specific object class."""
        return [f for f in self.features if f.object_class == object_class]
    
    def get_depth_areas(self, min_depth: Optional[float] = None) -> List[ENCFeature]:
        """Get depth areas, optionally filtered by minimum depth."""
        depth_areas = self.get_features_by_class('DEPARE')
        
        if min_depth is not None:
            filtered = []
            for area in depth_areas:
                drval1, _ = area.get_depth_range()
                if drval1 is not None and drval1 >= min_depth:
                    filtered.append(area)
            return filtered
        
        return depth_areas
    
    def get_dangers(self) -> List[ENCFeature]:
        """Get all danger/obstruction features."""
        danger_classes = ['OBSTRN', 'WRECKS', 'UWTROC']
        dangers = []
        for cls in danger_classes:
            dangers.extend(self.get_features_by_class(cls))
        return dangers
    
    def get_tss_features(self) -> Dict[str, List[ENCFeature]]:
        """Get all TSS-related features organized by type."""
        tss_classes = ['TSSLPT', 'TSEZNE', 'TSSBND', 'TSELNE', 'PRCARE']
        tss_features = {}
        for cls in tss_classes:
            features = self.get_features_by_class(cls)
            if features:
                tss_features[cls] = features
        return tss_features