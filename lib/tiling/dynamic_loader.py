"""
Dynamic Tile Loader
Handles on-demand loading and prefetching
"""

import asyncio
import threading
from concurrent.futures import ThreadPoolExecutor, Future
from dataclasses import dataclass
from typing import Dict, List, Tuple, Optional, Any, Callable, Set
from datetime import datetime
import logging
import numpy as np
from queue import PriorityQueue

from lib.tiling.tile_manager import TileManager, TileIndex, Tile
from lib.tiling.cache_strategy import LRUCache, PredictiveCache, CacheWarmer

logger = logging.getLogger(__name__)


@dataclass
class LoadRequest:
    """Request to load a tile"""
    tile_index: TileIndex
    priority: float
    callback: Optional[Callable] = None
    timestamp: datetime = None
    
    def __post_init__(self):
        if self.timestamp is None:
            self.timestamp = datetime.now()
    
    def __lt__(self, other):
        # Higher priority = load first
        return self.priority > other.priority


class DynamicLoader:
    """Dynamic tile loader with prefetching"""
    
    def __init__(self,
                 tile_manager: TileManager,
                 cache: Optional[LRUCache] = None,
                 max_workers: int = 4,
                 prefetch_radius: int = 2):
        """
        Initialize dynamic loader.
        
        Args:
            tile_manager: Tile manager instance
            cache: Cache instance (creates new if None)
            max_workers: Maximum parallel load workers
            prefetch_radius: Radius for prefetching tiles
        """
        self.tile_manager = tile_manager
        self.cache = cache or PredictiveCache(500.0)
        self.max_workers = max_workers
        self.prefetch_radius = prefetch_radius
        
        # Loading infrastructure
        self.executor = ThreadPoolExecutor(max_workers=max_workers)
        self.load_queue: PriorityQueue = PriorityQueue()
        self.loading: Set[TileIndex] = set()
        self.futures: Dict[TileIndex, Future] = {}
        
        # Statistics
        self.stats = {
            'tiles_requested': 0,
            'tiles_loaded': 0,
            'tiles_prefetched': 0,
            'cache_hits': 0,
            'load_time_ms': []
        }
        
        # Start background loader
        self.running = True
        self.loader_thread = threading.Thread(target=self._loader_loop, daemon=True)
        self.loader_thread.start()
        
        logger.info(f"DynamicLoader initialized with {max_workers} workers")
    
    def get_tile(self,
                lon: float,
                lat: float,
                wait: bool = True) -> Optional[Tile]:
        """
        Get tile for geographic point.
        
        Args:
            lon: Longitude
            lat: Latitude
            wait: Whether to wait for loading
            
        Returns:
            Tile or None
        """
        index = self.tile_manager.get_tile_index(lon, lat)
        return self.get_tile_by_index(index, wait)
    
    def get_tile_by_index(self,
                          index: TileIndex,
                          wait: bool = True) -> Optional[Tile]:
        """
        Get tile by index.
        
        Args:
            index: Tile index
            wait: Whether to wait for loading
            
        Returns:
            Tile or None
        """
        self.stats['tiles_requested'] += 1
        
        # Check cache first
        cache_key = index.to_string()
        cached_data = self.cache.get(cache_key)
        if cached_data is not None:
            self.stats['cache_hits'] += 1
            # Reconstruct tile from cached data
            tile = self.tile_manager.get_or_create_tile(index)
            tile.data = cached_data
            tile.loaded_at = datetime.now()
            return tile
        
        # Get or create tile
        tile = self.tile_manager.get_or_create_tile(index)
        
        # Check if already loaded
        if tile.is_loaded():
            return tile
        
        # Check if loading
        if index in self.loading:
            if wait and index in self.futures:
                # Wait for loading to complete
                future = self.futures[index]
                try:
                    future.result(timeout=10.0)
                    return tile
                except:
                    logger.error(f"Failed to load tile {index.to_string()}")
                    return None
            else:
                return None
        
        # Queue for loading
        self._queue_load(index, priority=1.0)
        
        # Trigger prefetch
        self._prefetch_nearby(index)
        
        if wait:
            # Wait for loading
            return self._wait_for_tile(index)
        
        return None
    
    def get_tiles_for_route(self,
                           route: List[Tuple[float, float]],
                           buffer_nm: float = 5.0) -> List[Tile]:
        """
        Get all tiles for a route.
        
        Args:
            route: List of (lon, lat) waypoints
            buffer_nm: Buffer distance
            
        Returns:
            List of loaded tiles
        """
        # Get required tile indices
        indices = self.tile_manager.get_tiles_for_route(route, buffer_nm)
        
        # Queue all for loading with priority based on position
        for i, index in enumerate(indices):
            priority = 1.0 - (i / len(indices))  # Higher priority for earlier tiles
            self._queue_load(index, priority)
        
        # Wait for all to load
        tiles = []
        for index in indices:
            tile = self.get_tile_by_index(index, wait=True)
            if tile:
                tiles.append(tile)
        
        return tiles
    
    def _queue_load(self, index: TileIndex, priority: float = 1.0):
        """Queue tile for loading"""
        if index not in self.loading:
            request = LoadRequest(index, priority)
            self.load_queue.put(request)
            self.loading.add(index)
    
    def _loader_loop(self):
        """Background loader thread"""
        while self.running:
            try:
                # Get next load request
                request = self.load_queue.get(timeout=1.0)
                
                # Submit to executor
                future = self.executor.submit(self._load_tile, request)
                self.futures[request.tile_index] = future
                
            except:
                continue
    
    def _load_tile(self, request: LoadRequest) -> bool:
        """Load a single tile"""
        start_time = datetime.now()
        
        try:
            # Get tile
            tile = self.tile_manager.get_or_create_tile(request.tile_index)
            
            # Load data
            success = self.tile_manager.load_tile_data(tile)
            
            if success and tile.data is not None:
                # Add to cache
                cache_key = request.tile_index.to_string()
                self.cache.put(cache_key, tile.data, tile.size_bytes, request.priority)
                
                self.stats['tiles_loaded'] += 1
                
                # Calculate load time
                load_time_ms = (datetime.now() - start_time).total_seconds() * 1000
                self.stats['load_time_ms'].append(load_time_ms)
                
                logger.debug(f"Loaded tile {request.tile_index.to_string()} in {load_time_ms:.1f}ms")
            
            return success
            
        except Exception as e:
            logger.error(f"Failed to load tile {request.tile_index.to_string()}: {e}")
            return False
        
        finally:
            # Remove from loading set
            self.loading.discard(request.tile_index)
            # Remove future
            self.futures.pop(request.tile_index, None)
    
    def _wait_for_tile(self, index: TileIndex, timeout: float = 10.0) -> Optional[Tile]:
        """Wait for tile to load"""
        if index in self.futures:
            future = self.futures[index]
            try:
                future.result(timeout=timeout)
                tile = self.tile_manager.tiles.get(index)
                if tile and tile.is_loaded():
                    return tile
            except:
                pass
        
        return None
    
    def _prefetch_nearby(self, center: TileIndex):
        """Prefetch nearby tiles"""
        # Get nearby indices
        nearby = []
        for dx in range(-self.prefetch_radius, self.prefetch_radius + 1):
            for dy in range(-self.prefetch_radius, self.prefetch_radius + 1):
                if dx == 0 and dy == 0:
                    continue  # Skip center
                
                nearby_index = TileIndex(
                    center.x + dx,
                    center.y + dy,
                    center.zoom
                )
                
                # Calculate priority based on distance
                distance = abs(dx) + abs(dy)
                priority = 0.5 / distance  # Lower priority for prefetch
                
                nearby.append((nearby_index, priority))
        
        # Queue for loading
        for index, priority in nearby:
            # Check if not already loaded or loading
            if index not in self.tile_manager.tiles or not self.tile_manager.tiles[index].is_loaded():
                if index not in self.loading:
                    self._queue_load(index, priority)
                    self.stats['tiles_prefetched'] += 1
    
    def preload_area(self,
                    min_lon: float,
                    max_lon: float,
                    min_lat: float,
                    max_lat: float) -> int:
        """
        Preload all tiles in an area.
        
        Args:
            min_lon: Minimum longitude
            max_lon: Maximum longitude
            min_lat: Minimum latitude
            max_lat: Maximum latitude
            
        Returns:
            Number of tiles queued
        """
        indices = self.tile_manager.get_tiles_for_bounds(
            min_lon, max_lon, min_lat, max_lat
        )
        
        queued = 0
        for index in indices:
            if index not in self.loading:
                self._queue_load(index, priority=0.3)  # Low priority for preload
                queued += 1
        
        logger.info(f"Queued {queued} tiles for preloading")
        return queued
    
    def get_statistics(self) -> Dict[str, Any]:
        """Get loader statistics"""
        avg_load_time = (
            np.mean(self.stats['load_time_ms'])
            if self.stats['load_time_ms']
            else 0
        )
        
        cache_hit_rate = (
            self.stats['cache_hits'] / self.stats['tiles_requested']
            if self.stats['tiles_requested'] > 0
            else 0
        )
        
        return {
            'tiles_requested': self.stats['tiles_requested'],
            'tiles_loaded': self.stats['tiles_loaded'],
            'tiles_prefetched': self.stats['tiles_prefetched'],
            'cache_hits': self.stats['cache_hits'],
            'cache_hit_rate': cache_hit_rate,
            'avg_load_time_ms': avg_load_time,
            'queue_size': self.load_queue.qsize(),
            'loading_count': len(self.loading),
            'cache_stats': self.cache.get_stats()
        }
    
    def shutdown(self):
        """Shutdown loader"""
        self.running = False
        self.executor.shutdown(wait=True)
        logger.info("DynamicLoader shutdown")


class StreamingLoader:
    """Streaming loader for continuous voyage"""
    
    def __init__(self,
                 dynamic_loader: DynamicLoader,
                 look_ahead_nm: float = 20.0,
                 look_behind_nm: float = 10.0):
        """
        Initialize streaming loader.
        
        Args:
            dynamic_loader: Dynamic loader instance
            look_ahead_nm: Distance to look ahead
            look_behind_nm: Distance to keep behind
        """
        self.loader = dynamic_loader
        self.look_ahead_nm = look_ahead_nm
        self.look_behind_nm = look_behind_nm
        
        self.current_position: Optional[Tuple[float, float]] = None
        self.loaded_window: Set[TileIndex] = set()
        
    def update_position(self, lon: float, lat: float, heading: float = 0.0):
        """
        Update vessel position and load tiles.
        
        Args:
            lon: Current longitude
            lat: Current latitude
            heading: Current heading (degrees)
        """
        self.current_position = (lon, lat)
        
        # Calculate window bounds
        # Simple rectangular window (can be improved with heading)
        look_ahead_deg = self.look_ahead_nm / 60.0
        look_behind_deg = self.look_behind_nm / 60.0
        
        # Adjust for heading (simplified)
        if 0 <= heading < 90:
            min_lon = lon - look_behind_deg
            max_lon = lon + look_ahead_deg
            min_lat = lat - look_behind_deg
            max_lat = lat + look_ahead_deg
        elif 90 <= heading < 180:
            min_lon = lon - look_behind_deg
            max_lon = lon + look_ahead_deg
            min_lat = lat - look_ahead_deg
            max_lat = lat + look_behind_deg
        elif 180 <= heading < 270:
            min_lon = lon - look_ahead_deg
            max_lon = lon + look_behind_deg
            min_lat = lat - look_ahead_deg
            max_lat = lat + look_behind_deg
        else:
            min_lon = lon - look_ahead_deg
            max_lon = lon + look_behind_deg
            min_lat = lat - look_behind_deg
            max_lat = lat + look_ahead_deg
        
        # Get required tiles
        required_indices = set(
            self.loader.tile_manager.get_tiles_for_bounds(
                min_lon, max_lon, min_lat, max_lat
            )
        )
        
        # Load new tiles
        new_tiles = required_indices - self.loaded_window
        for index in new_tiles:
            # Higher priority for tiles ahead
            tile_center = self.loader.tile_manager.get_tile_bounds(index)
            tile_lon = (tile_center.min_lon + tile_center.max_lon) / 2
            tile_lat = (tile_center.min_lat + tile_center.max_lat) / 2
            
            # Simple distance-based priority
            distance = np.sqrt((tile_lon - lon)**2 + (tile_lat - lat)**2)
            priority = 1.0 / (1.0 + distance)
            
            self.loader._queue_load(index, priority)
        
        # Unload tiles outside window
        to_unload = self.loaded_window - required_indices
        for index in to_unload:
            self.loader.tile_manager.unload_tile(index)
        
        # Update loaded window
        self.loaded_window = required_indices
        
        logger.debug(f"Streaming window: {len(new_tiles)} new, {len(to_unload)} unloaded")
    
    def get_current_tiles(self) -> List[Tile]:
        """Get all tiles in current window"""
        tiles = []
        for index in self.loaded_window:
            if index in self.loader.tile_manager.tiles:
                tile = self.loader.tile_manager.tiles[index]
                if tile.is_loaded():
                    tiles.append(tile)
        return tiles