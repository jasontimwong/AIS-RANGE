"""
Tests for Cache Strategy
"""

import pytest
import numpy as np
from datetime import datetime
import tempfile
import shutil
import sys
import os

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from lib.tiling.cache_strategy import (
    CacheEntry,
    LRUCache,
    PredictiveCache,
    TieredCache,
    CacheWarmer
)


class TestCacheEntry:
    """Test CacheEntry class"""
    
    def test_entry_creation(self):
        """Test creating cache entry"""
        entry = CacheEntry(
            key="test_key",
            data=np.array([1, 2, 3]),
            size_bytes=24,
            created_at=datetime.now(),
            last_accessed=datetime.now()
        )
        
        assert entry.key == "test_key"
        assert entry.size_bytes == 24
        assert entry.access_count == 0
    
    def test_update_access(self):
        """Test updating access info"""
        entry = CacheEntry(
            key="test",
            data="data",
            size_bytes=4,
            created_at=datetime.now(),
            last_accessed=datetime.now()
        )
        
        old_time = entry.last_accessed
        old_count = entry.access_count
        
        entry.update_access()
        
        assert entry.last_accessed > old_time
        assert entry.access_count == old_count + 1


class TestLRUCache:
    """Test LRUCache class"""
    
    def test_cache_initialization(self):
        """Test cache initialization"""
        cache = LRUCache(max_size_mb=10.0)
        
        assert cache.max_size_bytes == 10 * 1024 * 1024
        assert cache.current_size_bytes == 0
        assert len(cache.cache) == 0
    
    def test_put_and_get(self):
        """Test basic put and get"""
        cache = LRUCache(max_size_mb=1.0)
        
        # Put item
        success = cache.put("key1", "value1", size_bytes=100)
        assert success
        
        # Get item
        value = cache.get("key1")
        assert value == "value1"
        assert cache.stats['hits'] == 1
        
        # Get non-existent
        value = cache.get("key2")
        assert value is None
        assert cache.stats['misses'] == 1
    
    def test_lru_eviction(self):
        """Test LRU eviction"""
        cache = LRUCache(max_size_mb=0.001)  # Very small cache
        
        # Add items that will cause eviction
        cache.put("key1", "value1", size_bytes=500)
        cache.put("key2", "value2", size_bytes=500)
        cache.put("key3", "value3", size_bytes=500)
        
        # key1 should be evicted
        assert cache.get("key1") is None
        assert cache.get("key3") is not None
        assert cache.stats['evictions'] > 0
    
    def test_update_existing(self):
        """Test updating existing entry"""
        cache = LRUCache()
        
        cache.put("key1", "value1", size_bytes=100)
        old_size = cache.current_size_bytes
        
        cache.put("key1", "value2", size_bytes=200)
        
        assert cache.get("key1") == "value2"
        # Size should be updated correctly
        assert cache.current_size_bytes == old_size + 100
    
    def test_compression(self):
        """Test data compression"""
        cache = LRUCache()
        
        # Large data that triggers compression
        large_data = np.random.rand(1000, 1000)  # ~8MB
        
        success = cache.put("large", large_data)
        assert success
        
        # Check it was compressed
        entry = cache.cache["large"]
        assert entry.compressed
        
        # Get should decompress
        retrieved = cache.get("large")
        assert np.array_equal(retrieved, large_data)
    
    def test_cache_stats(self):
        """Test cache statistics"""
        cache = LRUCache()
        
        # Generate some activity
        cache.put("key1", "value1", size_bytes=100)
        cache.get("key1")  # Hit
        cache.get("key2")  # Miss
        
        stats = cache.get_stats()
        
        assert stats['hits'] == 1
        assert stats['misses'] == 1
        assert stats['hit_rate'] == 0.5
        assert stats['items'] == 1


class TestPredictiveCache:
    """Test PredictiveCache class"""
    
    def test_predictive_initialization(self):
        """Test predictive cache initialization"""
        cache = PredictiveCache(max_size_mb=10.0, prefetch_threshold=0.7)
        
        assert cache.prefetch_threshold == 0.7
        assert len(cache.access_patterns) == 0
    
    def test_access_tracking(self):
        """Test access pattern tracking"""
        cache = PredictiveCache()
        
        # Create access pattern
        cache.put("tile1", "data1")
        cache.put("tile2", "data2")
        cache.put("tile3", "data3")
        
        cache.get("tile1")
        cache.get("tile2")
        cache.get("tile1")
        cache.get("tile3")
        
        # Check transitions are tracked
        assert len(cache.transition_counts) > 0
        assert ("tile1", "tile2") in cache.transition_counts
    
    def test_prediction(self):
        """Test next access prediction"""
        cache = PredictiveCache()
        
        # Create strong pattern
        for _ in range(10):
            cache.get("A")
            cache.get("B")
            cache.get("C")
        
        # Now predict after A
        cache.get("A")
        predictions = cache._predict_next("A")
        
        # Should predict B with high confidence
        assert len(predictions) > 0
        assert predictions[0][0] == "B"
        assert predictions[0][1] > 0.8
    
    def test_prefetch_queue(self):
        """Test prefetch queueing"""
        cache = PredictiveCache(prefetch_threshold=0.5)
        
        # Create pattern
        for _ in range(5):
            cache.get("X")
            cache.get("Y")
        
        # Clear queue
        cache.prefetch_queue.clear()
        
        # Access X should queue Y for prefetch
        cache.get("X")
        
        assert "Y" in cache.prefetch_queue


class TestTieredCache:
    """Test TieredCache class"""
    
    def test_tiered_initialization(self):
        """Test tiered cache initialization"""
        with tempfile.TemporaryDirectory() as tmpdir:
            cache = TieredCache(
                memory_size_mb=1.0,
                disk_size_mb=10.0,
                disk_path=tmpdir
            )
            
            assert cache.memory_cache.max_size_bytes == 1024 * 1024
            assert cache.disk_size_mb == 10.0
            assert os.path.exists(tmpdir)
    
    def test_memory_then_disk(self):
        """Test fallback from memory to disk"""
        with tempfile.TemporaryDirectory() as tmpdir:
            cache = TieredCache(
                memory_size_mb=0.001,  # Very small memory
                disk_size_mb=10.0,
                disk_path=tmpdir
            )
            
            # Put items - should go to disk
            data1 = np.random.rand(100, 100)
            data2 = np.random.rand(100, 100)
            
            cache.put("key1", data1)
            cache.put("key2", data2)
            
            # Get should retrieve from disk
            retrieved1 = cache.get("key1")
            assert np.array_equal(retrieved1, data1)
    
    def test_promotion_to_memory(self):
        """Test promotion from disk to memory"""
        with tempfile.TemporaryDirectory() as tmpdir:
            cache = TieredCache(
                memory_size_mb=1.0,
                disk_size_mb=10.0,
                disk_path=tmpdir
            )
            
            # Save to disk directly
            cache._save_to_disk("disk_key", "disk_data")
            
            # Get should promote to memory
            data = cache.get("disk_key")
            assert data == "disk_data"
            
            # Should now be in memory cache
            assert cache.memory_cache.get("disk_key") == "disk_data"
    
    def test_clear_disk_cache(self):
        """Test clearing disk cache"""
        with tempfile.TemporaryDirectory() as tmpdir:
            cache = TieredCache(disk_path=tmpdir)
            
            # Add to disk
            cache._save_to_disk("key1", "data1")
            cache._save_to_disk("key2", "data2")
            
            assert len(cache.disk_index) == 2
            
            # Clear
            cache.clear_disk_cache()
            
            assert len(cache.disk_index) == 0


class TestCacheWarmer:
    """Test CacheWarmer class"""
    
    def test_warmer_initialization(self):
        """Test cache warmer initialization"""
        cache = LRUCache()
        warmer = CacheWarmer(cache)
        
        assert warmer.cache == cache
        assert len(warmer.warmup_queue) == 0
    
    def test_add_to_warmup(self):
        """Test adding to warmup queue"""
        cache = LRUCache()
        warmer = CacheWarmer(cache)
        
        warmer.add_to_warmup("key1", priority=1.0)
        warmer.add_to_warmup("key2", priority=0.5)
        
        assert len(warmer.warmup_queue) == 2
        assert warmer.warmup_queue[0] == ("key1", 1.0)
    
    def test_add_route_tiles(self):
        """Test adding route tiles"""
        cache = LRUCache()
        warmer = CacheWarmer(cache)
        
        tile_indices = ["tile1", "tile2", "tile3"]
        warmer.add_route_tiles(tile_indices, base_priority=1.0)
        
        assert len(warmer.warmup_queue) == 3
        
        # Check priority decreases along route
        priorities = [p for _, p in warmer.warmup_queue]
        assert priorities[0] > priorities[-1]
    
    def test_warm_cache(self):
        """Test warming cache"""
        cache = LRUCache()
        warmer = CacheWarmer(cache)
        
        # Add items to warm
        warmer.add_to_warmup("key1", 1.0)
        warmer.add_to_warmup("key2", 0.5)
        
        # Define load function
        def load_func(key):
            return f"data_{key}"
        
        # Warm cache
        loaded = warmer.warm_cache(load_func, max_items=2)
        
        assert loaded == 2
        assert cache.get("key1") == "data_key1"
        assert cache.get("key2") == "data_key2"