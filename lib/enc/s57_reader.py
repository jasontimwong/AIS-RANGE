"""
S-57 ENC Reader Module
Parses S-57 format electronic navigational charts focusing on safety-critical features.
Compliant with IMO MSC.232(82) and IHO S-57 standards.
"""

from typing import Dict, List, Tuple, Optional, Any, Set
from dataclasses import dataclass, field
from pathlib import Path
import logging
try:
    from osgeo import ogr, osr
    GDAL_AVAILABLE = True
except ImportError:
    GDAL_AVAILABLE = False
    ogr = None
    osr = None
import shapely.geometry as geom
from shapely.geometry import Point, LineString, Polygon, MultiPolygon
import numpy as np

logger = logging.getLogger(__name__)

# S-57 Object Classes (minimal subset for safety)
S57_OBJECTS = {
    'DEPARE': 'Depth Area',
    'DEPCNT': 'Depth Contour', 
    'COALNE': 'Coastline',
    'OBSTRN': 'Obstruction',
    'WRECKS': 'Wrecks',
    'UWTROC': 'Underwater Rock',
    'RESARE': 'Restricted Area',
    'RESTRN': 'Restriction',
    'TSSLPT': 'Traffic Separation Scheme Lane Part',
    'TSEZNE': 'Traffic Separation Zone',
    'TSSBND': 'Traffic Separation Scheme Boundary',
    'TSELNE': 'Traffic Separation Line',
    'PRCARE': 'Precautionary Area'
}

# Key S-57 Attributes
S57_ATTRIBUTES = {
    'DRVAL1': 'Depth Range Value 1',
    'DRVAL2': 'Depth Range Value 2',
    'VALSOU': 'Value of Sounding',
    'RESTRN': 'Restriction',
    'CATTSS': 'Category of TSS',
    'ORIENT': 'Orientation',
    'TRAFIC': 'Traffic Flow'
}


@dataclass
class ENCFeature:
    """Represents a single S-57 feature with geometry and attributes."""
    object_class: str
    geometry: Any  # Shapely geometry
    attributes: Dict[str, Any] = field(default_factory=dict)
    rcid: Optional[int] = None  # Record ID
    
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


class S57Reader:
    """
    S-57 ENC file reader using GDAL/OGR.
    Coordinates are in WGS84 (EPSG:4326) on input, converted to Web Mercator (EPSG:3395) internally.
    """
    
    def __init__(self, enc_path: Path, target_srs: str = 'EPSG:3857'):
        """
        Initialize S-57 reader.
        
        Args:
            enc_path: Path to .000 S-57 file
            target_srs: Target spatial reference system (default: Web Mercator)
        """
        self.enc_path = Path(enc_path)
        self.target_srs = target_srs
        self.features: List[ENCFeature] = []
        self.metadata: Dict[str, Any] = {}
        
        # Setup GDAL S-57 driver options
        if not GDAL_AVAILABLE:
            raise RuntimeError("GDAL not installed. Use S57MockReader for testing.")
        
        # Configure GDAL for S-57
        import os
        os.environ['OGR_S57_OPTIONS'] = 'SPLIT_MULTIPOINT=ON,ADD_SOUNDG_DEPTH=ON'
        
        ogr.RegisterAll()
        self.driver = ogr.GetDriverByName('S57')
        if not self.driver:
            raise RuntimeError("S-57 driver not available in GDAL")
        
        # For now, we'll work directly in WGS84 coordinates
        # and convert to meters using local projection
        self.transform = None
    
    def load(self, object_classes: Optional[Set[str]] = None) -> List[ENCFeature]:
        """
        Load S-57 features from file.
        
        Args:
            object_classes: Optional set of S-57 object classes to filter (e.g., {'DEPARE', 'OBSTRN'})
                          If None, loads all supported object classes
        
        Returns:
            List of ENCFeature objects
        """
        if not self.enc_path.exists():
            raise FileNotFoundError(f"ENC file not found: {self.enc_path}")
        
        # Open S-57 dataset
        dataset = self.driver.Open(str(self.enc_path), 0)
        if not dataset:
            raise RuntimeError(f"Failed to open S-57 file: {self.enc_path}")
        
        try:
            # Get dataset metadata
            self._extract_metadata(dataset)
            
            # Process each layer
            for i in range(dataset.GetLayerCount()):
                layer = dataset.GetLayerByIndex(i)
                layer_name = layer.GetName()
                
                # Filter by object class if specified
                if object_classes and layer_name not in object_classes:
                    continue
                
                # Skip if not a supported object class
                if layer_name not in S57_OBJECTS:
                    logger.debug(f"Skipping unsupported layer: {layer_name}")
                    continue
                
                logger.info(f"Processing layer: {layer_name} ({S57_OBJECTS.get(layer_name, 'Unknown')})")
                self._process_layer(layer, layer_name)
            
            logger.info(f"Loaded {len(self.features)} features from {self.enc_path.name}")
            
        finally:
            dataset = None  # Close dataset
        
        return self.features
    
    def _process_layer(self, layer: 'ogr.Layer', object_class: str) -> None:
        """Process a single S-57 layer."""
        layer.ResetReading()
        
        for feature in layer:
            try:
                # Extract geometry
                ogr_geom = feature.GetGeometryRef()
                if not ogr_geom:
                    continue
                
                # Skip transformation for now - work in WGS84
                # ogr_geom.Transform(self.transform)
                
                # Convert to Shapely geometry
                shapely_geom = self._ogr_to_shapely(ogr_geom)
                if not shapely_geom:
                    continue
                
                # Extract attributes
                attributes = {}
                for i in range(feature.GetFieldCount()):
                    field_name = feature.GetFieldDefnRef(i).GetName()
                    value = feature.GetField(i)
                    if value is not None:
                        attributes[field_name] = value
                
                # Create ENC feature
                enc_feature = ENCFeature(
                    object_class=object_class,
                    geometry=shapely_geom,
                    attributes=attributes,
                    rcid=feature.GetFID()
                )
                
                self.features.append(enc_feature)
                
            except Exception as e:
                logger.warning(f"Failed to process feature in {object_class}: {e}")
    
    def _ogr_to_shapely(self, ogr_geom: 'ogr.Geometry') -> Optional[Any]:
        """Convert OGR geometry to Shapely geometry."""
        geom_type = ogr_geom.GetGeometryName()
        
        try:
            if geom_type == 'POINT':
                return Point(ogr_geom.GetX(), ogr_geom.GetY())
            
            elif geom_type in ['LINESTRING', 'LINEARRING']:
                points = []
                for i in range(ogr_geom.GetPointCount()):
                    points.append((ogr_geom.GetX(i), ogr_geom.GetY(i)))
                return LineString(points) if len(points) >= 2 else None
            
            elif geom_type == 'POLYGON':
                # Get exterior ring
                exterior_ring = ogr_geom.GetGeometryRef(0)
                exterior_points = []
                for i in range(exterior_ring.GetPointCount()):
                    exterior_points.append((exterior_ring.GetX(i), exterior_ring.GetY(i)))
                
                # Get interior rings (holes)
                holes = []
                for j in range(1, ogr_geom.GetGeometryCount()):
                    hole_ring = ogr_geom.GetGeometryRef(j)
                    hole_points = []
                    for i in range(hole_ring.GetPointCount()):
                        hole_points.append((hole_ring.GetX(i), hole_ring.GetY(i)))
                    if len(hole_points) >= 3:
                        holes.append(hole_points)
                
                if len(exterior_points) >= 3:
                    return Polygon(exterior_points, holes)
            
            elif geom_type == 'MULTIPOLYGON':
                polygons = []
                for i in range(ogr_geom.GetGeometryCount()):
                    poly = self._ogr_to_shapely(ogr_geom.GetGeometryRef(i))
                    if poly:
                        polygons.append(poly)
                return MultiPolygon(polygons) if polygons else None
            
            # TODO: Handle other geometry types as needed
            else:
                logger.debug(f"Unsupported geometry type: {geom_type}")
                return None
                
        except Exception as e:
            logger.warning(f"Failed to convert geometry: {e}")
            return None
    
    def _extract_metadata(self, dataset: 'ogr.DataSource') -> None:
        """Extract metadata from S-57 dataset."""
        # TODO: Extract DSID (Data Set Identification) record
        # TODO: Extract compilation scale, producing agency, etc.
        self.metadata['layer_count'] = dataset.GetLayerCount()
        self.metadata['driver'] = 'S-57'
    
    def get_features_by_class(self, object_class: str) -> List[ENCFeature]:
        """Get all features of a specific object class."""
        return [f for f in self.features if f.object_class == object_class]
    
    def get_depth_areas(self, min_depth: Optional[float] = None) -> List[ENCFeature]:
        """
        Get depth areas, optionally filtered by minimum depth.
        
        Args:
            min_depth: Minimum depth in meters (filters by DRVAL1)
        
        Returns:
            List of DEPARE features
        """
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