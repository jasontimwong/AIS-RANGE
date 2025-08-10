"""
Feasible Region Module
Constructs navigable regions from ENC data considering safety constraints.
Generates no-go areas, feasible channels, and TSS compliance zones.
"""

from typing import List, Tuple, Optional, Dict, Set
from dataclasses import dataclass
import numpy as np
from shapely.geometry import (
    Polygon, MultiPolygon, Point, LineString, 
    GeometryCollection, box
)
from shapely.ops import unary_union
from shapely.prepared import prep
import logging
from pathlib import Path

# Conditional import for testing
try:
    from lib.enc.s57_reader import S57Reader, ENCFeature
except (ImportError, RuntimeError):
    # For testing without GDAL
    from lib.enc.s57_reader_mock import S57MockReader as S57Reader, ENCFeature

logger = logging.getLogger(__name__)


@dataclass
class SafetyParameters:
    """Safety parameters for feasible region generation."""
    safety_depth: float  # Minimum safe water depth in meters
    safety_contour: float  # Safety contour depth in meters
    xtd_margin: float  # Cross-track distance margin in meters
    under_keel_clearance: float  # UKC in meters
    vessel_draft: float  # Vessel draft in meters
    
    @property
    def minimum_depth(self) -> float:
        """Calculate minimum required water depth."""
        return self.vessel_draft + self.under_keel_clearance


@dataclass  
class FeasibleRegion:
    """Represents navigable and non-navigable regions."""
    bounds: Tuple[float, float, float, float]  # (minx, miny, maxx, maxy)
    no_go_areas: MultiPolygon  # Combined no-go zones
    navigable_area: MultiPolygon  # Safe navigable waters
    depth_contours: Dict[float, List[LineString]]  # Depth contour lines
    danger_zones: List[Polygon]  # Individual danger areas
    restricted_areas: List[Polygon]  # Restricted/regulated areas
    tss_zones: Optional['TSSZones'] = None  # TSS structure if present
    
    def is_point_safe(self, x: float, y: float) -> bool:
        """Check if a point is in safe navigable water."""
        pt = Point(x, y)
        return self.navigable_area.contains(pt) and not self.no_go_areas.contains(pt)
    
    def get_clearance(self, x: float, y: float) -> float:
        """Get minimum distance to nearest hazard."""
        pt = Point(x, y)
        if not self.is_point_safe(x, y):
            return 0.0
        return self.no_go_areas.distance(pt)
    
    def to_raster(self, resolution: float = 10.0) -> np.ndarray:
        """
        Convert to binary raster grid.
        
        Args:
            resolution: Grid cell size in meters
            
        Returns:
            2D numpy array where 1=navigable, 0=no-go
        """
        minx, miny, maxx, maxy = self.bounds
        
        # Calculate grid dimensions
        width = int((maxx - minx) / resolution) + 1
        height = int((maxy - miny) / resolution) + 1
        
        # Initialize grid (1 = navigable by default)
        grid = np.ones((height, width), dtype=np.uint8)
        
        # Rasterize no-go areas
        # TODO: Implement efficient polygon rasterization
        # For now, use simple point-in-polygon checks (inefficient for large grids)
        for i in range(height):
            for j in range(width):
                x = minx + j * resolution
                y = miny + i * resolution
                if not self.is_point_safe(x, y):
                    grid[i, j] = 0
        
        return grid


class FeasibleRegionBuilder:
    """Builds feasible navigation regions from ENC data."""
    
    def __init__(self, safety_params: SafetyParameters):
        """
        Initialize region builder.
        
        Args:
            safety_params: Safety parameters for region generation
        """
        self.safety_params = safety_params
        self.enc_features: List[ENCFeature] = []
        
    def build_from_enc(self, enc_reader: S57Reader) -> FeasibleRegion:
        """
        Build feasible region from loaded ENC data.
        
        Args:
            enc_reader: Loaded S57Reader with ENC features
            
        Returns:
            FeasibleRegion object
        """
        logger.info(f"Building feasible region with safety depth: {self.safety_params.minimum_depth}m")
        
        # Extract relevant features
        depth_areas = enc_reader.get_depth_areas()
        dangers = enc_reader.get_dangers()
        coastlines = enc_reader.get_features_by_class('COALNE')
        restricted = enc_reader.get_features_by_class('RESARE')
        depth_contours = enc_reader.get_features_by_class('DEPCNT')
        
        # Build no-go areas
        no_go_polygons = []
        
        # 1. Shallow water areas (depth < safety threshold)
        shallow_areas = self._extract_shallow_areas(depth_areas)
        no_go_polygons.extend(shallow_areas)
        
        # 2. Danger zones (obstructions, wrecks, rocks)
        danger_zones = self._extract_danger_zones(dangers)
        no_go_polygons.extend(danger_zones)
        
        # 3. Land areas (inferred from coastlines)
        land_areas = self._extract_land_areas(coastlines)
        no_go_polygons.extend(land_areas)
        
        # 4. Restricted areas (based on RESTRN attributes)
        restricted_zones = self._extract_restricted_areas(restricted)
        
        # Combine all no-go areas
        if no_go_polygons:
            no_go_union = unary_union(no_go_polygons)
            if isinstance(no_go_union, Polygon):
                no_go_areas = MultiPolygon([no_go_union])
            else:
                no_go_areas = no_go_union
        else:
            no_go_areas = MultiPolygon([])
        
        # Calculate bounds
        all_geoms = []
        for feature in enc_reader.features:
            if feature.geometry:
                all_geoms.append(feature.geometry)
        
        if all_geoms:
            combined = unary_union(all_geoms)
            bounds = combined.bounds
        else:
            bounds = (0, 0, 1000, 1000)  # Default bounds
        
        # Create navigable area (inverse of no-go within bounds)
        bbox = box(*bounds)
        # Only compute difference if no-go areas are valid and within bounds
        if no_go_areas and not no_go_areas.is_empty:
            # Check if no-go areas are in reasonable coordinate range
            no_go_bounds = no_go_areas.bounds
            if (abs(no_go_bounds[0]) < 360 and abs(no_go_bounds[1]) < 180 and 
                abs(no_go_bounds[2]) < 360 and abs(no_go_bounds[3]) < 180):
                navigable = bbox.difference(no_go_areas)
            else:
                # No-go areas have invalid coordinates, use full bbox
                logger.warning("No-go areas have invalid coordinates, using full bbox as navigable")
                navigable = bbox
        else:
            navigable = bbox
        
        if isinstance(navigable, Polygon):
            navigable_area = MultiPolygon([navigable])
        elif isinstance(navigable, MultiPolygon):
            navigable_area = navigable
        else:
            navigable_area = MultiPolygon([])
        
        # Extract depth contour lines
        contour_dict = self._organize_depth_contours(depth_contours)
        
        # Build TSS zones if present
        tss_features = enc_reader.get_tss_features()
        tss_zones = None
        if tss_features:
            tss_zones = self._build_tss_zones(tss_features)
        
        return FeasibleRegion(
            bounds=bounds,
            no_go_areas=no_go_areas,
            navigable_area=navigable_area,
            depth_contours=contour_dict,
            danger_zones=danger_zones,
            restricted_areas=restricted_zones,
            tss_zones=tss_zones
        )
    
    def _extract_shallow_areas(self, depth_areas: List[ENCFeature]) -> List[Polygon]:
        """Extract shallow water polygons."""
        shallow_polygons = []
        min_depth = self.safety_params.minimum_depth
        
        for area in depth_areas:
            drval1, drval2 = area.get_depth_range()
            
            # Check if this is a shallow area
            is_shallow = False
            if drval2 is not None and drval2 < min_depth:
                is_shallow = True
            elif drval1 is not None and drval1 < min_depth and drval2 is None:
                is_shallow = True
            
            if is_shallow and isinstance(area.geometry, (Polygon, MultiPolygon)):
                if isinstance(area.geometry, Polygon):
                    shallow_polygons.append(area.geometry)
                else:
                    shallow_polygons.extend(area.geometry.geoms)
        
        return shallow_polygons
    
    def _extract_danger_zones(self, dangers: List[ENCFeature]) -> List[Polygon]:
        """Extract danger zones with safety buffer."""
        danger_polygons = []
        buffer_dist = self.safety_params.xtd_margin
        
        for danger in dangers:
            geom = danger.geometry
            
            # Apply safety buffer around dangers
            if geom:
                buffered = geom.buffer(buffer_dist)
                if isinstance(buffered, Polygon):
                    danger_polygons.append(buffered)
                elif isinstance(buffered, MultiPolygon):
                    danger_polygons.extend(buffered.geoms)
        
        return danger_polygons
    
    def _extract_land_areas(self, coastlines: List[ENCFeature]) -> List[Polygon]:
        """Infer land areas from coastline features."""
        land_polygons = []
        
        # Collect all coastline segments
        coast_lines = []
        for coast in coastlines:
            if isinstance(coast.geometry, LineString):
                coast_lines.append(coast.geometry)
        
        # TODO: Implement proper land area inference from coastlines
        # This requires topological reconstruction which is complex
        # For now, buffer coastlines as a simple approximation
        for line in coast_lines:
            # Small buffer on "land side" of coastline
            # Note: Determining land side requires additional logic
            buffered = line.buffer(50)  # 50m buffer as placeholder
            if isinstance(buffered, Polygon):
                land_polygons.append(buffered)
        
        return land_polygons
    
    def _extract_restricted_areas(self, restricted: List[ENCFeature]) -> List[Polygon]:
        """Extract restricted/regulated areas based on RESTRN attribute."""
        restricted_polygons = []
        
        for area in restricted:
            restrn = area.attributes.get('RESTRN', [])
            
            # Check restriction types (S-57 RESTRN enumeration)
            # 1=anchoring prohibited, 2=anchoring restricted, 
            # 3=fishing prohibited, etc.
            if restrn and isinstance(area.geometry, (Polygon, MultiPolygon)):
                # TODO: Filter based on specific restriction types
                if isinstance(area.geometry, Polygon):
                    restricted_polygons.append(area.geometry)
                else:
                    restricted_polygons.extend(area.geometry.geoms)
        
        return restricted_polygons
    
    def _organize_depth_contours(self, contours: List[ENCFeature]) -> Dict[float, List[LineString]]:
        """Organize depth contours by depth value."""
        contour_dict = {}
        
        for contour in contours:
            valdco = contour.attributes.get('VALDCO')  # Depth value
            if valdco and isinstance(contour.geometry, LineString):
                depth = float(valdco)
                if depth not in contour_dict:
                    contour_dict[depth] = []
                contour_dict[depth].append(contour.geometry)
        
        return contour_dict
    
    def _build_tss_zones(self, tss_features: Dict[str, List[ENCFeature]]) -> Optional['TSSZones']:
        """Build TSS zone structure."""
        # Delegate to specialized TSS handler
        from lib.region.tss_layers import TSSZones, TSSLayerBuilder
        
        builder = TSSLayerBuilder()
        return builder.build_from_features(tss_features)