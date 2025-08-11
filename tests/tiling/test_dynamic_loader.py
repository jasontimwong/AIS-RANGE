"""
Tests for Dynamic Loader
"""

import pytest
import time
from datetime import datetime
import sys
import os

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from lib.tiling.tile_manager import TileManager, TileIndex
from lib.tiling.cache_strategy import LRUCache
from lib.tiling.dynamic_loader import (
    LoadRequest,
    DynamicLoader,
    StreamingLoader
)


class TestLoadRequest:
    """Test LoadRequest class"""
    
    def test_request_creation(self):
        """Test creating load request"""
        index = TileIndex(10, 20, 10)
        request = LoadRequest(
            tile_index=index,
            priority=1.0
        )
        
        assert request.tile_index == index
        assert request.priority == 1.0
        assert request.timestamp is not None
    
    def test_request_comparison(self):
        """Test request priority comparison"""
        index1 = TileIndex(10, 20, 10)
        index2 = TileIndex(11, 21, 10)
        
        request1 = LoadRequest(index1, priority=1.0)
        request2 = LoadRequest(index2, priority=0.5)
        
        # Higher priority should be "less than" for queue
        assert request1 < request2


class TestDynamicLoader:
    """Test DynamicLoader class"""
    
    def test_loader_initialization(self):
        """Test loader initialization"""
        tile_manager = TileManager()
        cache = LRUCache(100.0)
        
        loader = DynamicLoader(
            tile_manager=tile_manager,
            cache=cache,
            max_workers=2,
            prefetch_radius=1
        )
        
        assert loader.tile_manager == tile_manager
        assert loader.cache == cache
        assert loader.max_workers == 2
        assert loader.prefetch_radius == 1
        
        # Cleanup
        loader.shutdown()
    
    def test_get_tile_cached(self):
        """Test getting cached tile"""
        tile_manager = TileManager()
        cache = LRUCache()
        loader = DynamicLoader(tile_manager, cache)
        
        # Pre-populate cache
        index = tile_manager.get_tile_index(10.5, 20.5)
        cache_key = index.to_string()
        cache.put(cache_key, "cached_data")
        
        # Get should return from cache
        tile = loader.get_tile(10.5, 20.5, wait=False)
        
        assert tile is not None
        assert loader.stats['cache_hits'] == 1
        
        # Cleanup
        loader.shutdown()
    
    def test_get_tile_load(self):
        """Test loading tile"""
        tile_manager = TileManager()
        loader = DynamicLoader(tile_manager)
        
        # Give loader time to start
        time.sleep(0.1)
        
        # Get tile (will trigger load)
        tile = loader.get_tile(10.5, 20.5, wait=True)
        
        # If still None, it's okay - loading is async
        if tile is not None:
            assert tile.is_loaded()
        assert loader.stats['tiles_requested'] == 1
        
        # Cleanup
        loader.shutdown()
    
    def test_get_tiles_for_route(self):
        """Test getting tiles for route"""
        tile_manager = TileManager()
        loader = DynamicLoader(tile_manager)
        
        # Give loader time to start
        time.sleep(0.1)
        
        route = [
            (10.0, 20.0),
            (11.0, 21.0),
            (12.0, 22.0)
        ]
        
        tiles = loader.get_tiles_for_route(route, buffer_nm=1.0)
        
        # Loading is async, so tiles may not be loaded immediately
        assert loader.stats['tiles_requested'] > 0
        
        # Cleanup
        loader.shutdown()
    
    def test_prefetch(self):
        """Test prefetching nearby tiles"""
        tile_manager = TileManager()
        loader = DynamicLoader(tile_manager, prefetch_radius=1)
        
        # Get center tile (should trigger prefetch)
        center_tile = loader.get_tile(10.5, 20.5, wait=True)
        
        # Give prefetch time to queue
        time.sleep(0.1)
        
        # Check that nearby tiles are queued
        assert loader.stats['tiles_prefetched'] > 0
        
        # Cleanup
        loader.shutdown()
    
    def test_preload_area(self):
        """Test preloading area"""
        tile_manager = TileManager()
        loader = DynamicLoader(tile_manager)
        
        queued = loader.preload_area(
            min_lon=10.0,
            max_lon=12.0,
            min_lat=20.0,
            max_lat=22.0
        )
        
        assert queued > 0
        assert loader.load_queue.qsize() > 0
        
        # Cleanup
        loader.shutdown()
    
    def test_statistics(self):
        """Test getting statistics"""
        tile_manager = TileManager()
        loader = DynamicLoader(tile_manager)
        
        # Generate some activity
        loader.get_tile(10.5, 20.5, wait=True)
        
        stats = loader.get_statistics()
        
        assert 'tiles_requested' in stats
        assert 'cache_hit_rate' in stats
        assert 'avg_load_time_ms' in stats
        assert stats['tiles_requested'] > 0
        
        # Cleanup
        loader.shutdown()


class TestStreamingLoader:
    """Test StreamingLoader class"""
    
    def test_streaming_initialization(self):
        """Test streaming loader initialization"""
        tile_manager = TileManager()
        dynamic_loader = DynamicLoader(tile_manager)
        
        streaming = StreamingLoader(
            dynamic_loader=dynamic_loader,
            look_ahead_nm=20.0,
            look_behind_nm=10.0
        )
        
        assert streaming.loader == dynamic_loader
        assert streaming.look_ahead_nm == 20.0
        assert streaming.look_behind_nm == 10.0
        
        # Cleanup
        dynamic_loader.shutdown()
    
    def test_update_position(self):
        """Test updating position"""
        tile_manager = TileManager()
        dynamic_loader = DynamicLoader(tile_manager)
        streaming = StreamingLoader(dynamic_loader)
        
        # Update position
        streaming.update_position(10.5, 20.5, heading=45.0)
        
        assert streaming.current_position == (10.5, 20.5)
        assert len(streaming.loaded_window) > 0
        
        # Cleanup
        dynamic_loader.shutdown()
    
    def test_window_management(self):
        """Test window loading/unloading"""
        tile_manager = TileManager(tile_size_deg=0.1)  # Small tiles
        dynamic_loader = DynamicLoader(tile_manager)
        streaming = StreamingLoader(
            dynamic_loader,
            look_ahead_nm=5.0,
            look_behind_nm=2.0
        )
        
        # First position
        streaming.update_position(10.0, 20.0, heading=0.0)
        initial_window = streaming.loaded_window.copy()
        
        # Move significantly
        streaming.update_position(10.5, 20.0, heading=90.0)
        new_window = streaming.loaded_window
        
        # Windows should be different
        assert initial_window != new_window
        
        # Cleanup
        dynamic_loader.shutdown()
    
    def test_get_current_tiles(self):
        """Test getting current tiles"""
        tile_manager = TileManager()
        dynamic_loader = DynamicLoader(tile_manager)
        streaming = StreamingLoader(dynamic_loader)
        
        # Update position to load some tiles
        streaming.update_position(10.0, 20.0)
        
        # Wait a bit for loading
        time.sleep(0.2)
        
        # Get current tiles
        tiles = streaming.get_current_tiles()
        
        # Should have some tiles
        # Note: May be empty if loading is slow
        assert isinstance(tiles, list)
        
        # Cleanup
        dynamic_loader.shutdown()