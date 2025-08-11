"""
Tests for Tile Manager
"""

import pytest
import numpy as np
from datetime import datetime
import sys
import os

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from lib.tiling.tile_manager import (
    TileIndex,
    TileBounds,
    Tile,
    TileManager,
    TileIndexer
)


class TestTileIndex:
    """Test TileIndex class"""
    
    def test_index_creation(self):
        """Test creating tile index"""
        index = TileIndex(x=10, y=20, zoom=10)
        
        assert index.x == 10
        assert index.y == 20
        assert index.zoom == 10
    
    def test_index_equality(self):
        """Test index equality"""
        index1 = TileIndex(10, 20, 10)
        index2 = TileIndex(10, 20, 10)
        index3 = TileIndex(11, 20, 10)
        
        assert index1 == index2
        assert index1 != index3
    
    def test_index_string_conversion(self):
        """Test string conversion"""
        index = TileIndex(10, 20, 12)
        
        string = index.to_string()
        assert string == "12/10/20"
        
        restored = TileIndex.from_string(string)
        assert restored == index


class TestTileBounds:
    """Test TileBounds class"""
    
    def test_bounds_creation(self):
        """Test creating tile bounds"""
        bounds = TileBounds(
            min_lon=10.0,
            max_lon=11.0,
            min_lat=20.0,
            max_lat=21.0
        )
        
        assert bounds.min_lon == 10.0
        assert bounds.max_lon == 11.0
        assert bounds.min_lat == 20.0
        assert bounds.max_lat == 21.0
    
    def test_contains_point(self):
        """Test point containment"""
        bounds = TileBounds(10.0, 11.0, 20.0, 21.0)
        
        # Inside
        assert bounds.contains_point(10.5, 20.5)
        
        # On boundary
        assert bounds.contains_point(10.0, 20.0)
        assert bounds.contains_point(11.0, 21.0)
        
        # Outside
        assert not bounds.contains_point(9.9, 20.5)
        assert not bounds.contains_point(10.5, 21.1)
    
    def test_intersects(self):
        """Test bounds intersection"""
        bounds1 = TileBounds(10.0, 12.0, 20.0, 22.0)
        bounds2 = TileBounds(11.0, 13.0, 21.0, 23.0)  # Overlapping
        bounds3 = TileBounds(13.0, 14.0, 23.0, 24.0)  # Non-overlapping
        
        assert bounds1.intersects(bounds2)
        assert bounds2.intersects(bounds1)
        assert not bounds1.intersects(bounds3)
    
    def test_area(self):
        """Test area calculation"""
        bounds = TileBounds(10.0, 12.0, 20.0, 22.0)
        
        area = bounds.area()
        assert area == 4.0  # 2 * 2


class TestTile:
    """Test Tile class"""
    
    def test_tile_creation(self):
        """Test creating tile"""
        index = TileIndex(10, 20, 10)
        bounds = TileBounds(10.0, 11.0, 20.0, 21.0)
        
        tile = Tile(index=index, bounds=bounds)
        
        assert tile.index == index
        assert tile.bounds == bounds
        assert not tile.is_loaded()
    
    def test_tile_loading(self):
        """Test tile loading state"""
        index = TileIndex(10, 20, 10)
        bounds = TileBounds(10.0, 11.0, 20.0, 21.0)
        tile = Tile(index=index, bounds=bounds)
        
        # Initially not loaded
        assert not tile.is_loaded()
        
        # Load data
        tile.data = np.random.rand(100, 100)
        tile.loaded_at = datetime.now()
        
        assert tile.is_loaded()
        
        # Unload
        tile.unload()
        assert not tile.is_loaded()
        assert tile.data is None


class TestTileManager:
    """Test TileManager class"""
    
    def test_manager_initialization(self):
        """Test manager initialization"""
        manager = TileManager(tile_size_deg=1.0, zoom_level=10)
        
        assert manager.tile_size_deg == 1.0
        assert manager.zoom_level == 10
        assert len(manager.tiles) == 0
    
    def test_get_tile_index(self):
        """Test getting tile index for point"""
        manager = TileManager(tile_size_deg=1.0)
        
        # Test various points
        index = manager.get_tile_index(10.5, 20.5)
        assert index.x == 10
        assert index.y == 20
        
        index = manager.get_tile_index(-0.5, -0.5)
        assert index.x == -1
        assert index.y == -1
    
    def test_get_tile_bounds(self):
        """Test getting tile bounds"""
        manager = TileManager(tile_size_deg=1.0)
        
        index = TileIndex(10, 20, 10)
        bounds = manager.get_tile_bounds(index)
        
        assert bounds.min_lon == 10.0
        assert bounds.max_lon == 11.0
        assert bounds.min_lat == 20.0
        assert bounds.max_lat == 21.0
    
    def test_create_tile(self):
        """Test tile creation"""
        manager = TileManager()
        
        index = TileIndex(10, 20, 10)
        tile = manager.create_tile(index)
        
        assert tile.index == index
        assert tile in manager.tiles.values()
        assert manager.stats['tiles_created'] == 1
    
    def test_load_tile_data(self):
        """Test loading tile data"""
        manager = TileManager()
        
        index = TileIndex(10, 20, 10)
        tile = manager.create_tile(index)
        
        # Load with sample data
        success = manager.load_tile_data(tile)
        
        assert success
        assert tile.is_loaded()
        assert tile.data is not None
        assert manager.stats['tiles_loaded'] == 1
    
    def test_unload_tile(self):
        """Test unloading tile"""
        manager = TileManager()
        
        # Create and load tile
        index = TileIndex(10, 20, 10)
        tile = manager.create_tile(index)
        manager.load_tile_data(tile)
        
        assert tile.is_loaded()
        
        # Unload
        success = manager.unload_tile(index)
        
        assert success
        assert not tile.is_loaded()
        assert manager.stats['tiles_unloaded'] == 1
    
    def test_get_tiles_for_bounds(self):
        """Test getting tiles for geographic bounds"""
        manager = TileManager(tile_size_deg=1.0)
        
        indices = manager.get_tiles_for_bounds(
            min_lon=10.5,
            max_lon=12.5,
            min_lat=20.5,
            max_lat=21.5
        )
        
        # Should cover 3x2 tiles (10-12 x 20-21)
        assert len(indices) == 6
        
        # Check all expected indices are present
        expected = [
            TileIndex(10, 20, 10),
            TileIndex(10, 21, 10),
            TileIndex(11, 20, 10),
            TileIndex(11, 21, 10),
            TileIndex(12, 20, 10),
            TileIndex(12, 21, 10)
        ]
        
        for index in indices:
            assert index.x in [10, 11, 12]
            assert index.y in [20, 21]
    
    def test_get_tiles_for_route(self):
        """Test getting tiles for route"""
        manager = TileManager(tile_size_deg=1.0)
        
        route = [
            (10.0, 20.0),
            (11.0, 21.0),
            (12.0, 22.0)
        ]
        
        indices = manager.get_tiles_for_route(route, buffer_nm=5.0)
        
        # Should include tiles along route plus buffer
        assert len(indices) > 0
        
        # Check route tiles are included
        assert TileIndex(10, 20, 10) in indices
        assert TileIndex(11, 21, 10) in indices
        assert TileIndex(12, 22, 10) in indices
    
    def test_stitch_tiles(self):
        """Test stitching tiles"""
        manager = TileManager(tile_size_deg=1.0)
        
        # Create and load tiles
        indices = [
            TileIndex(10, 20, 10),
            TileIndex(11, 20, 10),
            TileIndex(10, 21, 10),
            TileIndex(11, 21, 10)
        ]
        
        for index in indices:
            tile = manager.create_tile(index)
            manager.load_tile_data(tile)
        
        # Stitch
        stitched = manager.stitch_tiles(indices)
        
        assert stitched is not None
        assert stitched.shape[0] > 0
        assert stitched.shape[1] > 0
    
    def test_memory_usage(self):
        """Test memory usage tracking"""
        manager = TileManager()
        
        # Create and load some tiles
        for i in range(3):
            index = TileIndex(i, 0, 10)
            tile = manager.create_tile(index)
            manager.load_tile_data(tile)
        
        usage = manager.get_memory_usage()
        
        assert usage['total_tiles'] == 3
        assert usage['loaded_tiles'] == 3
        assert usage['total_size_mb'] > 0


class TestTileIndexer:
    """Test TileIndexer class"""
    
    def test_indexer_initialization(self):
        """Test indexer initialization"""
        indexer = TileIndexer()
        
        assert len(indexer.spatial_index) == 0
        assert len(indexer.tile_metadata) == 0
    
    def test_add_tile(self):
        """Test adding tile to index"""
        indexer = TileIndexer()
        
        index = TileIndex(10, 20, 10)
        metadata = {'type': 'bathymetry'}
        
        indexer.add_tile(index, metadata)
        
        assert index in indexer.tile_metadata
        assert indexer.tile_metadata[index] == metadata
    
    def test_find_nearby_tiles(self):
        """Test finding nearby tiles"""
        indexer = TileIndexer()
        
        center = TileIndex(10, 20, 10)
        nearby = indexer.find_nearby_tiles(center, radius=1)
        
        # Should return 3x3 grid
        assert len(nearby) == 9
        
        # Check center is included
        assert center in nearby
        
        # Check adjacent tiles
        assert TileIndex(9, 20, 10) in nearby
        assert TileIndex(11, 20, 10) in nearby
        assert TileIndex(10, 19, 10) in nearby
        assert TileIndex(10, 21, 10) in nearby
    
    def test_get_tile_clusters(self):
        """Test clustering tiles"""
        indexer = TileIndexer()
        
        # Create two separate clusters
        cluster1 = [
            TileIndex(10, 20, 10),
            TileIndex(11, 20, 10),
            TileIndex(10, 21, 10)
        ]
        
        cluster2 = [
            TileIndex(20, 30, 10),
            TileIndex(21, 30, 10)
        ]
        
        all_indices = cluster1 + cluster2
        
        clusters = indexer.get_tile_cluster(all_indices)
        
        # Should identify 2 clusters
        assert len(clusters) == 2
        
        # Check cluster sizes
        sizes = [len(c) for c in clusters]
        assert 3 in sizes
        assert 2 in sizes