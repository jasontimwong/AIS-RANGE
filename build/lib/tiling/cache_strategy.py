"""
Cache Strategy for Tile Management
Implements LRU and predictive caching
"""

import heapq
import hashlib
from collections import OrderedDict
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Any, Set, Tuple
from datetime import datetime, timedelta
import logging
import pickle
import lz4.frame
import os

logger = logging.getLogger(__name__)


@dataclass
class CacheEntry:
    """Entry in the cache"""
    key: str
    data: Any
    size_bytes: int
    created_at: datetime
    last_accessed: datetime
    access_count: int = 0
    priority: float = 1.0
    compressed: bool = False
    
    def update_access(self):
        """Update access timestamp and count"""
        self.last_accessed = datetime.now()
        self.access_count += 1


class LRUCache:
    """Least Recently Used cache implementation"""
    
    def __init__(self, max_size_mb: float = 500.0):
        """
        Initialize LRU cache.
        
        Args:
            max_size_mb: Maximum cache size in megabytes
        """
        self.max_size_bytes = int(max_size_mb * 1024 * 1024)
        self.current_size_bytes = 0
        self.cache: OrderedDict[str, CacheEntry] = OrderedDict()
        self.stats = {
            'hits': 0,
            'misses': 0,
            'evictions': 0,
            'compressions': 0
        }
        
        logger.info(f"LRU cache initialized with {max_size_mb:.1f} MB limit")
    
    def get(self, key: str) -> Optional[Any]:
        """
        Get item from cache.
        
        Args:
            key: Cache key
            
        Returns:
            Cached data or None
        """
        if key in self.cache:
            # Move to end (most recently used)
            entry = self.cache.pop(key)
            entry.update_access()
            self.cache[key] = entry
            
            self.stats['hits'] += 1
            
            # Decompress if needed
            if entry.compressed:
                return self._decompress(entry.data)
            return entry.data
        else:
            self.stats['misses'] += 1
            return None
    
    def put(self, 
            key: str,
            data: Any,
            size_bytes: Optional[int] = None,
            priority: float = 1.0) -> bool:
        """
        Put item in cache.
        
        Args:
            key: Cache key
            data: Data to cache
            size_bytes: Size in bytes (calculated if not provided)
            priority: Cache priority
            
        Returns:
            Success status
        """
        # Calculate size if not provided
        if size_bytes is None:
            size_bytes = self._estimate_size(data)
        
        # Check if we need to make room
        if size_bytes > self.max_size_bytes:
            logger.warning(f"Item too large for cache: {size_bytes} bytes")
            return False
        
        # Evict items if necessary
        while self.current_size_bytes + size_bytes > self.max_size_bytes:
            if not self._evict_lru():
                break
        
        # Compress large items
        compressed = False
        if size_bytes > 1024 * 1024:  # > 1MB
            data = self._compress(data)
            compressed = True
            self.stats['compressions'] += 1
        
        # Create entry
        entry = CacheEntry(
            key=key,
            data=data,
            size_bytes=size_bytes,
            created_at=datetime.now(),
            last_accessed=datetime.now(),
            priority=priority,
            compressed=compressed
        )
        
        # Add to cache
        if key in self.cache:
            # Remove old entry
            old_entry = self.cache.pop(key)
            self.current_size_bytes -= old_entry.size_bytes
        
        self.cache[key] = entry
        self.current_size_bytes += size_bytes
        
        return True
    
    def _evict_lru(self) -> bool:
        """Evict least recently used item"""
        if not self.cache:
            return False
        
        # Get oldest item (first in OrderedDict)
        key, entry = next(iter(self.cache.items()))
        
        # Remove from cache
        del self.cache[key]
        self.current_size_bytes -= entry.size_bytes
        self.stats['evictions'] += 1
        
        logger.debug(f"Evicted {key} from cache")
        return True
    
    def _estimate_size(self, data: Any) -> int:
        """Estimate size of data in bytes"""
        try:
            # For numpy arrays
            if hasattr(data, 'nbytes'):
                return data.nbytes
            # For other objects, use pickle size
            return len(pickle.dumps(data))
        except:
            return 1024  # Default 1KB
    
    def _compress(self, data: Any) -> bytes:
        """Compress data using LZ4"""
        serialized = pickle.dumps(data)
        return lz4.frame.compress(serialized)
    
    def _decompress(self, data: bytes) -> Any:
        """Decompress LZ4 data"""
        decompressed = lz4.frame.decompress(data)
        return pickle.loads(decompressed)
    
    def clear(self):
        """Clear all cached items"""
        self.cache.clear()
        self.current_size_bytes = 0
        logger.info("Cache cleared")
    
    def get_stats(self) -> Dict[str, Any]:
        """Get cache statistics"""
        hit_rate = (
            self.stats['hits'] / (self.stats['hits'] + self.stats['misses'])
            if (self.stats['hits'] + self.stats['misses']) > 0
            else 0
        )
        
        return {
            'size_mb': self.current_size_bytes / (1024 * 1024),
            'max_size_mb': self.max_size_bytes / (1024 * 1024),
            'utilization': self.current_size_bytes / self.max_size_bytes,
            'items': len(self.cache),
            'hits': self.stats['hits'],
            'misses': self.stats['misses'],
            'hit_rate': hit_rate,
            'evictions': self.stats['evictions'],
            'compressions': self.stats['compressions']
        }


class PredictiveCache(LRUCache):
    """Cache with predictive prefetching"""
    
    def __init__(self, 
                 max_size_mb: float = 500.0,
                 prefetch_threshold: float = 0.7):
        """
        Initialize predictive cache.
        
        Args:
            max_size_mb: Maximum cache size
            prefetch_threshold: Confidence threshold for prefetching
        """
        super().__init__(max_size_mb)
        self.prefetch_threshold = prefetch_threshold
        self.access_patterns: Dict[str, List[str]] = {}
        self.transition_counts: Dict[Tuple[str, str], int] = {}
        self.prefetch_queue: List[str] = []
    
    def get(self, key: str) -> Optional[Any]:
        """Get with pattern tracking"""
        result = super().get(key)
        
        # Track access pattern
        self._track_access(key)
        
        # Trigger prefetch if needed
        self._maybe_prefetch(key)
        
        return result
    
    def _track_access(self, key: str):
        """Track access patterns for prediction"""
        # Add to recent accesses
        if not hasattr(self, '_recent_accesses'):
            self._recent_accesses = []
        
        self._recent_accesses.append(key)
        if len(self._recent_accesses) > 100:
            self._recent_accesses.pop(0)
        
        # Update transition counts
        if len(self._recent_accesses) >= 2:
            prev_key = self._recent_accesses[-2]
            transition = (prev_key, key)
            self.transition_counts[transition] = self.transition_counts.get(transition, 0) + 1
    
    def _maybe_prefetch(self, current_key: str):
        """Prefetch likely next items"""
        predictions = self._predict_next(current_key)
        
        for next_key, confidence in predictions:
            if confidence >= self.prefetch_threshold:
                if next_key not in self.cache and next_key not in self.prefetch_queue:
                    self.prefetch_queue.append(next_key)
                    logger.debug(f"Queued {next_key} for prefetch (confidence: {confidence:.2f})")
    
    def _predict_next(self, current_key: str) -> List[Tuple[str, float]]:
        """Predict likely next accesses"""
        predictions = []
        
        # Find all transitions from current key
        total_transitions = 0
        next_counts = {}
        
        for (from_key, to_key), count in self.transition_counts.items():
            if from_key == current_key:
                next_counts[to_key] = count
                total_transitions += count
        
        # Calculate confidences
        if total_transitions > 0:
            for next_key, count in next_counts.items():
                confidence = count / total_transitions
                predictions.append((next_key, confidence))
        
        # Sort by confidence
        predictions.sort(key=lambda x: x[1], reverse=True)
        
        return predictions[:5]  # Top 5 predictions
    
    def process_prefetch_queue(self, load_func):
        """Process prefetch queue"""
        while self.prefetch_queue:
            key = self.prefetch_queue.pop(0)
            
            if key not in self.cache:
                # Load data using provided function
                data = load_func(key)
                if data is not None:
                    self.put(key, data, priority=0.8)  # Lower priority for prefetched


class TieredCache:
    """Multi-tier cache system (memory + disk)"""
    
    def __init__(self,
                 memory_size_mb: float = 100.0,
                 disk_size_mb: float = 1000.0,
                 disk_path: str = "/tmp/tile_cache"):
        """
        Initialize tiered cache.
        
        Args:
            memory_size_mb: Memory cache size
            disk_size_mb: Disk cache size
            disk_path: Path for disk cache
        """
        self.memory_cache = LRUCache(memory_size_mb)
        self.disk_cache_path = disk_path
        self.disk_size_mb = disk_size_mb
        self.disk_index: Dict[str, str] = {}  # key -> filename
        
        # Create disk cache directory
        os.makedirs(disk_path, exist_ok=True)
        
        logger.info(f"Tiered cache: {memory_size_mb}MB memory, {disk_size_mb}MB disk")
    
    def get(self, key: str) -> Optional[Any]:
        """Get from memory or disk"""
        # Try memory first
        data = self.memory_cache.get(key)
        if data is not None:
            return data
        
        # Try disk
        if key in self.disk_index:
            data = self._load_from_disk(key)
            if data is not None:
                # Promote to memory cache
                self.memory_cache.put(key, data)
                return data
        
        return None
    
    def put(self, key: str, data: Any, size_bytes: Optional[int] = None) -> bool:
        """Put in appropriate tier"""
        # Try memory first
        if self.memory_cache.put(key, data, size_bytes):
            return True
        
        # Fallback to disk
        return self._save_to_disk(key, data)
    
    def _save_to_disk(self, key: str, data: Any) -> bool:
        """Save data to disk cache"""
        try:
            filename = f"{hashlib.md5(key.encode()).hexdigest()}.cache"
            filepath = os.path.join(self.disk_cache_path, filename)
            
            # Compress and save
            compressed = lz4.frame.compress(pickle.dumps(data))
            
            with open(filepath, 'wb') as f:
                f.write(compressed)
            
            self.disk_index[key] = filename
            return True
            
        except Exception as e:
            logger.error(f"Failed to save to disk: {e}")
            return False
    
    def _load_from_disk(self, key: str) -> Optional[Any]:
        """Load data from disk cache"""
        try:
            filename = self.disk_index[key]
            filepath = os.path.join(self.disk_cache_path, filename)
            
            with open(filepath, 'rb') as f:
                compressed = f.read()
            
            # Decompress and load
            data = pickle.loads(lz4.frame.decompress(compressed))
            return data
            
        except Exception as e:
            logger.error(f"Failed to load from disk: {e}")
            return None
    
    def clear_disk_cache(self):
        """Clear disk cache"""
        for filename in self.disk_index.values():
            filepath = os.path.join(self.disk_cache_path, filename)
            try:
                os.remove(filepath)
            except:
                pass
        
        self.disk_index.clear()
        logger.info("Disk cache cleared")


class CacheWarmer:
    """Preload cache with likely needed data"""
    
    def __init__(self, cache: LRUCache):
        """
        Initialize cache warmer.
        
        Args:
            cache: Cache to warm
        """
        self.cache = cache
        self.warmup_queue: List[Tuple[str, float]] = []  # (key, priority)
    
    def add_to_warmup(self, key: str, priority: float = 1.0):
        """Add item to warmup queue"""
        self.warmup_queue.append((key, priority))
    
    def add_route_tiles(self, tile_indices: List[Any], base_priority: float = 1.0):
        """Add tiles along route to warmup"""
        for i, index in enumerate(tile_indices):
            # Higher priority for earlier tiles
            priority = base_priority * (1.0 - i / len(tile_indices))
            self.add_to_warmup(str(index), priority)
    
    def warm_cache(self, load_func, max_items: int = 50) -> int:
        """
        Warm cache with queued items.
        
        Args:
            load_func: Function to load data
            max_items: Maximum items to load
            
        Returns:
            Number of items loaded
        """
        # Sort by priority
        self.warmup_queue.sort(key=lambda x: x[1], reverse=True)
        
        loaded = 0
        for key, priority in self.warmup_queue[:max_items]:
            if key not in self.cache.cache:
                data = load_func(key)
                if data is not None:
                    if self.cache.put(key, data, priority=priority):
                        loaded += 1
        
        # Clear processed items
        self.warmup_queue = self.warmup_queue[max_items:]
        
        logger.info(f"Cache warmed with {loaded} items")
        return loaded