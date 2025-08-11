"""
Tile Manager for Long Voyage Segments
Manages chart tiles for efficient memory usage
"""

import numpy as np
from dataclasses import dataclass, field
from typing import Dict, List, Tuple, Optional, Any, Set
from datetime import datetime
import hashlib
import logging
import math

logger = logging.getLogger(__name__)


@dataclass
class TileIndex:
    """Index for a single tile"""
    x: int  # Longitude index
    y: int  # Latitude index
    zoom: int = 10  # Zoom level (10 = ~1 degree tiles)
    
    def __hash__(self):
        return hash((self.x, self.y, self.zoom))
    
    def __eq__(self, other):
        return self.x == other.x and self.y == other.y and self.zoom == other.zoom
    
    def to_string(self) -> str:
        """Convert to string identifier"""
        return f"{self.zoom}/{self.x}/{self.y}"
    
    @classmethod
    def from_string(cls, s: str) -> 'TileIndex':
        """Create from string identifier"""
        parts = s.split('/')
        return cls(int(parts[1]), int(parts[2]), int(parts[0]))


@dataclass
class TileBounds:
    """Geographic bounds of a tile"""
    min_lon: float
    max_lon: float
    min_lat: float
    max_lat: float
    
    def contains_point(self, lon: float, lat: float) -> bool:
        """Check if point is within bounds"""
        return (self.min_lon <= lon <= self.max_lon and 
                self.min_lat <= lat <= self.max_lat)
    
    def intersects(self, other: 'TileBounds') -> bool:
        """Check if bounds intersect"""
        return not (self.max_lon < other.min_lon or 
                   self.min_lon > other.max_lon or
                   self.max_lat < other.min_lat or
                   self.min_lat > other.max_lat)
    
    def area(self) -> float:
        """Calculate area in square degrees"""
        return (self.max_lon - self.min_lon) * (self.max_lat - self.min_lat)


@dataclass
class Tile:
    """Single map tile"""
    index: TileIndex
    bounds: TileBounds
    data: Optional[np.ndarray] = None
    metadata: Dict[str, Any] = field(default_factory=dict)
    loaded_at: Optional[datetime] = None
    last_accessed: Optional[datetime] = None
    size_bytes: int = 0
    checksum: Optional[str] = None
    
    def is_loaded(self) -> bool:
        """Check if tile data is loaded"""
        return self.data is not None
    
    def calculate_checksum(self) -> str:
        """Calculate data checksum"""
        if self.data is not None:
            return hashlib.md5(self.data.tobytes()).hexdigest()
        return ""
    
    def unload(self):
        """Unload tile data to free memory"""
        self.data = None
        self.loaded_at = None


class TileManager:
    """Manages tiles for large area coverage"""
    
    def __init__(self,
                 tile_size_deg: float = 1.0,
                 zoom_level: int = 10,
                 data_resolution_m: float = 100.0):
        """
        Initialize tile manager.
        
        Args:
            tile_size_deg: Size of each tile in degrees
            zoom_level: Zoom level for tile indexing
            data_resolution_m: Data resolution in meters
        """
        self.tile_size_deg = tile_size_deg
        self.zoom_level = zoom_level
        self.data_resolution_m = data_resolution_m
        
        # Tile storage
        self.tiles: Dict[TileIndex, Tile] = {}
        self.loaded_tiles: Set[TileIndex] = set()
        
        # Statistics
        self.stats = {
            'tiles_created': 0,
            'tiles_loaded': 0,
            'tiles_unloaded': 0,
            'total_size_bytes': 0
        }
        
        logger.info(f"TileManager initialized with {tile_size_deg}° tiles")
    
    def get_tile_index(self, lon: float, lat: float) -> TileIndex:
        """
        Get tile index for a geographic point.
        
        Args:
            lon: Longitude
            lat: Latitude
            
        Returns:
            Tile index
        """
        # Simple tile indexing based on degree grid
        x = int(math.floor(lon / self.tile_size_deg))
        y = int(math.floor(lat / self.tile_size_deg))
        
        return TileIndex(x, y, self.zoom_level)
    
    def get_tile_bounds(self, index: TileIndex) -> TileBounds:
        """
        Get geographic bounds for a tile index.
        
        Args:
            index: Tile index
            
        Returns:
            Tile bounds
        """
        min_lon = index.x * self.tile_size_deg
        max_lon = (index.x + 1) * self.tile_size_deg
        min_lat = index.y * self.tile_size_deg
        max_lat = (index.y + 1) * self.tile_size_deg
        
        return TileBounds(min_lon, max_lon, min_lat, max_lat)
    
    def create_tile(self, index: TileIndex) -> Tile:
        """
        Create a new tile.
        
        Args:
            index: Tile index
            
        Returns:
            Created tile
        """
        bounds = self.get_tile_bounds(index)
        
        tile = Tile(
            index=index,
            bounds=bounds,
            metadata={
                'created_at': datetime.now(),
                'resolution_m': self.data_resolution_m
            }
        )
        
        self.tiles[index] = tile
        self.stats['tiles_created'] += 1
        
        logger.debug(f"Created tile {index.to_string()}")
        return tile
    
    def get_or_create_tile(self, index: TileIndex) -> Tile:
        """
        Get existing tile or create new one.
        
        Args:
            index: Tile index
            
        Returns:
            Tile
        """
        if index in self.tiles:
            return self.tiles[index]
        else:
            return self.create_tile(index)
    
    def load_tile_data(self, 
                       tile: Tile,
                       data_source: Optional[Any] = None) -> bool:
        """
        Load data for a tile.
        
        Args:
            tile: Tile to load
            data_source: Optional data source
            
        Returns:
            Success status
        """
        if tile.is_loaded():
            tile.last_accessed = datetime.now()
            return True
        
        # Calculate grid dimensions
        lon_points = int(self.tile_size_deg * 111000 / self.data_resolution_m)
        lat_points = int(self.tile_size_deg * 111000 / self.data_resolution_m)
        
        # Generate sample data (in production, load from data_source)
        if data_source is None:
            # Create sample bathymetry data
            np.random.seed(hash(tile.index) % 2**32)
            tile.data = np.random.uniform(10, 100, (lon_points, lat_points))
        else:
            # Load from data source
            tile.data = self._load_from_source(tile, data_source)
        
        tile.loaded_at = datetime.now()
        tile.last_accessed = datetime.now()
        tile.size_bytes = tile.data.nbytes if tile.data is not None else 0
        tile.checksum = tile.calculate_checksum()
        
        self.loaded_tiles.add(tile.index)
        self.stats['tiles_loaded'] += 1
        self.stats['total_size_bytes'] += tile.size_bytes
        
        logger.debug(f"Loaded tile {tile.index.to_string()} ({tile.size_bytes} bytes)")
        return True
    
    def _load_from_source(self, tile: Tile, source: Any) -> Optional[np.ndarray]:
        """Load tile data from external source"""
        # Placeholder for actual data loading
        # In production, this would load from S-57, database, etc.
        return None
    
    def unload_tile(self, index: TileIndex) -> bool:
        """
        Unload a tile to free memory.
        
        Args:
            index: Tile index
            
        Returns:
            Success status
        """
        if index not in self.tiles:
            return False
        
        tile = self.tiles[index]
        
        if tile.is_loaded():
            self.stats['total_size_bytes'] -= tile.size_bytes
            tile.unload()
            self.loaded_tiles.discard(index)
            self.stats['tiles_unloaded'] += 1
            
            logger.debug(f"Unloaded tile {index.to_string()}")
            return True
        
        return False
    
    def get_tiles_for_bounds(self, 
                            min_lon: float,
                            max_lon: float,
                            min_lat: float,
                            max_lat: float) -> List[TileIndex]:
        """
        Get all tile indices covering a geographic area.
        
        Args:
            min_lon: Minimum longitude
            max_lon: Maximum longitude
            min_lat: Minimum latitude
            max_lat: Maximum latitude
            
        Returns:
            List of tile indices
        """
        indices = []
        
        # Calculate tile range
        min_x = int(math.floor(min_lon / self.tile_size_deg))
        max_x = int(math.floor(max_lon / self.tile_size_deg))
        min_y = int(math.floor(min_lat / self.tile_size_deg))
        max_y = int(math.floor(max_lat / self.tile_size_deg))
        
        for x in range(min_x, max_x + 1):
            for y in range(min_y, max_y + 1):
                indices.append(TileIndex(x, y, self.zoom_level))
        
        return indices
    
    def get_tiles_for_route(self,
                           route: List[Tuple[float, float]],
                           buffer_nm: float = 5.0) -> List[TileIndex]:
        """
        Get all tiles needed for a route.
        
        Args:
            route: List of (lon, lat) waypoints
            buffer_nm: Buffer distance in nautical miles
            
        Returns:
            List of tile indices
        """
        indices = set()
        
        # Buffer in degrees (approximate)
        buffer_deg = buffer_nm / 60.0
        
        for lon, lat in route:
            # Get tiles covering buffered area around waypoint
            min_lon = lon - buffer_deg
            max_lon = lon + buffer_deg
            min_lat = lat - buffer_deg
            max_lat = lat + buffer_deg
            
            for index in self.get_tiles_for_bounds(min_lon, max_lon, min_lat, max_lat):
                indices.add(index)
        
        return list(indices)
    
    def stitch_tiles(self,
                    indices: List[TileIndex]) -> Optional[np.ndarray]:
        """
        Stitch multiple tiles into single array.
        
        Args:
            indices: List of tile indices to stitch
            
        Returns:
            Stitched data array or None
        """
        if not indices:
            return None
        
        # Find bounding box
        min_x = min(idx.x for idx in indices)
        max_x = max(idx.x for idx in indices)
        min_y = min(idx.y for idx in indices)
        max_y = max(idx.y for idx in indices)
        
        # Calculate output dimensions
        tiles_wide = max_x - min_x + 1
        tiles_high = max_y - min_y + 1
        
        # Get single tile dimensions
        sample_tile = self.get_or_create_tile(indices[0])
        if not sample_tile.is_loaded():
            self.load_tile_data(sample_tile)
        
        if sample_tile.data is None:
            return None
        
        tile_height, tile_width = sample_tile.data.shape
        
        # Create output array
        stitched = np.zeros((tiles_high * tile_height, tiles_wide * tile_width))
        
        # Copy tiles into output
        for index in indices:
            tile = self.get_or_create_tile(index)
            
            if not tile.is_loaded():
                self.load_tile_data(tile)
            
            if tile.data is not None:
                # Calculate position in output array
                x_offset = (index.x - min_x) * tile_width
                y_offset = (index.y - min_y) * tile_height
                
                # Copy data
                stitched[y_offset:y_offset + tile_height,
                        x_offset:x_offset + tile_width] = tile.data
        
        return stitched
    
    def get_memory_usage(self) -> Dict[str, Any]:
        """Get current memory usage statistics"""
        return {
            'total_tiles': len(self.tiles),
            'loaded_tiles': len(self.loaded_tiles),
            'total_size_mb': self.stats['total_size_bytes'] / (1024 * 1024),
            'average_tile_size_mb': (
                self.stats['total_size_bytes'] / (1024 * 1024) / len(self.loaded_tiles)
                if self.loaded_tiles else 0
            )
        }
    
    def clear_all(self):
        """Clear all tiles"""
        for index in list(self.loaded_tiles):
            self.unload_tile(index)
        
        self.tiles.clear()
        self.loaded_tiles.clear()
        
        logger.info("Cleared all tiles")


class TileIndexer:
    """Spatial indexer for efficient tile lookup"""
    
    def __init__(self):
        """Initialize tile indexer"""
        self.spatial_index: Dict[int, Set[TileIndex]] = {}
        self.tile_metadata: Dict[TileIndex, Dict[str, Any]] = {}
    
    def add_tile(self, index: TileIndex, metadata: Optional[Dict[str, Any]] = None):
        """Add tile to spatial index"""
        # Create spatial hash
        spatial_hash = self._compute_spatial_hash(index)
        
        if spatial_hash not in self.spatial_index:
            self.spatial_index[spatial_hash] = set()
        
        self.spatial_index[spatial_hash].add(index)
        
        if metadata:
            self.tile_metadata[index] = metadata
    
    def _compute_spatial_hash(self, index: TileIndex) -> int:
        """Compute spatial hash for tile index"""
        # Simple spatial hashing
        return (index.x // 10) * 1000 + (index.y // 10)
    
    def find_nearby_tiles(self, 
                         center: TileIndex,
                         radius: int = 1) -> List[TileIndex]:
        """Find tiles within radius of center"""
        nearby = []
        
        for dx in range(-radius, radius + 1):
            for dy in range(-radius, radius + 1):
                nearby.append(TileIndex(
                    center.x + dx,
                    center.y + dy,
                    center.zoom
                ))
        
        return nearby
    
    def get_tile_cluster(self, indices: List[TileIndex]) -> List[List[TileIndex]]:
        """Group tiles into connected clusters"""
        if not indices:
            return []
        
        # Build adjacency
        adjacency = {idx: set() for idx in indices}
        
        for i, idx1 in enumerate(indices):
            for idx2 in indices[i+1:]:
                # Check if adjacent
                if abs(idx1.x - idx2.x) <= 1 and abs(idx1.y - idx2.y) <= 1:
                    adjacency[idx1].add(idx2)
                    adjacency[idx2].add(idx1)
        
        # Find connected components
        visited = set()
        clusters = []
        
        for idx in indices:
            if idx not in visited:
                cluster = []
                stack = [idx]
                
                while stack:
                    current = stack.pop()
                    if current not in visited:
                        visited.add(current)
                        cluster.append(current)
                        stack.extend(adjacency[current] - visited)
                
                clusters.append(cluster)
        
        return clusters