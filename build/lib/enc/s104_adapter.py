"""
S-104 Water Level/Tide Adapter
Provides time-series water level data for 4D planning and dynamic UKC
"""

import numpy as np
import pandas as pd
from dataclasses import dataclass
from typing import List, Tuple, Optional, Dict, Any
from datetime import datetime, timedelta
import logging
from pathlib import Path
import json

logger = logging.getLogger(__name__)


@dataclass
class TideStation:
    """Tide station with time-series water level data"""
    station_id: str
    name: str
    position: Tuple[float, float]  # (lon, lat)
    datum: str  # Reference datum (e.g., 'MSL', 'LAT')
    time_series: pd.DataFrame  # Columns: 'time', 'water_level'
    
    def get_water_level(self, query_time: datetime) -> float:
        """
        Get water level at specific time with interpolation.
        
        Args:
            query_time: Time to query
            
        Returns:
            Interpolated water level in meters
        """
        if self.time_series.empty:
            return 0.0
        
        # Convert to timestamp for interpolation
        ts = pd.Timestamp(query_time)
        
        # Check if within data range
        if ts < self.time_series['time'].min():
            # Extrapolate backward (use first value)
            logger.warning(f"Query time {query_time} before data range, using first value")
            return float(self.time_series.iloc[0]['water_level'])
        elif ts > self.time_series['time'].max():
            # Extrapolate forward (use last value)
            logger.warning(f"Query time {query_time} after data range, using last value")
            return float(self.time_series.iloc[-1]['water_level'])
        
        # Interpolate
        # Create temporary series for interpolation
        temp_df = self.time_series.copy()
        temp_df = temp_df.set_index('time')
        
        # Add query time and interpolate
        new_row = pd.DataFrame({'water_level': [np.nan]}, index=[ts])
        temp_df = pd.concat([temp_df, new_row]).sort_index()
        temp_df = temp_df.interpolate(method='linear')
        
        # Get the single value at the timestamp
        value = temp_df.loc[ts, 'water_level']
        # Handle both Series and scalar
        if hasattr(value, 'iloc'):
            return float(value.iloc[0])
        return float(value)


class S104Adapter:
    """S-104 Water Level Information adapter"""
    
    def __init__(self):
        """Initialize S-104 adapter"""
        self.stations: Dict[str, TideStation] = {}
        self.grid_data: Optional[np.ndarray] = None
        self.grid_times: Optional[List[datetime]] = None
        self.grid_bounds: Optional[Tuple[float, float, float, float]] = None
        
    def load_station_data(self, filepath: str) -> TideStation:
        """
        Load tide station data from CSV.
        
        Format:
        station_id,name,lon,lat,datum
        time1,water_level1
        time2,water_level2
        ...
        
        Args:
            filepath: Path to station data file
            
        Returns:
            TideStation object
        """
        df = pd.read_csv(filepath)
        
        # Extract metadata from first row
        meta = df.iloc[0]
        station = TideStation(
            station_id=str(meta.get('station_id', 'UNKNOWN')),
            name=str(meta.get('name', 'Unnamed')),
            position=(float(meta.get('lon', 0)), float(meta.get('lat', 0))),
            datum=str(meta.get('datum', 'MSL')),
            time_series=pd.DataFrame()
        )
        
        # Parse time series data
        if len(df) > 1:
            # Assume rest of file is time,water_level
            ts_data = []
            for idx in range(1, len(df)):
                row = df.iloc[idx]
                if pd.notna(row.iloc[0]) and pd.notna(row.iloc[1]):
                    try:
                        time = pd.to_datetime(row.iloc[0])
                        water_level = float(row.iloc[1])
                        ts_data.append({'time': time, 'water_level': water_level})
                    except (ValueError, TypeError) as e:
                        logger.warning(f"Skipping invalid row {idx}: {e}")
            
            station.time_series = pd.DataFrame(ts_data)
        
        self.stations[station.station_id] = station
        logger.info(f"Loaded tide station {station.station_id} with {len(station.time_series)} records")
        
        return station
    
    def load_grid_data(self, filepath: str) -> Tuple[np.ndarray, List[datetime]]:
        """
        Load gridded water level data (time-varying grid).
        
        Format: HDF5 or NetCDF with dimensions [time, lat, lon]
        For testing, we'll use a simplified CSV format
        
        Args:
            filepath: Path to grid data file
            
        Returns:
            (grid_data, time_list)
        """
        # Simplified CSV format for testing
        # time,min_lon,min_lat,max_lon,max_lat,nx,ny
        # 2025-01-01T00:00:00,data...
        
        with open(filepath, 'r') as f:
            lines = f.readlines()
        
        # Parse header - skip first line if it's column names
        if 'min_lon' in lines[0]:
            lines = lines[1:]  # Skip header row
        
        header = lines[0].strip().split(',')
        min_lon = float(header[1])
        min_lat = float(header[2])
        max_lon = float(header[3])
        max_lat = float(header[4])
        nx = int(header[5])
        ny = int(header[6])
        
        self.grid_bounds = (min_lon, min_lat, max_lon, max_lat)
        
        # Parse time series grids
        grids = []
        times = []
        
        for line in lines:
            parts = line.strip().split(',')
            if len(parts) < 7:  # Need at least time + 6 header values
                continue
                
            time = pd.to_datetime(parts[0])
            times.append(time.to_pydatetime())
            
            # Parse grid values (starting from index 7)
            values = [float(v) for v in parts[7:7+nx*ny]]
            grid = np.array(values).reshape((ny, nx))
            grids.append(grid)
        
        self.grid_data = np.array(grids)  # Shape: (n_times, ny, nx)
        self.grid_times = times
        
        logger.info(f"Loaded grid data: {len(times)} time steps, grid size {ny}x{nx}")
        
        return self.grid_data, self.grid_times
    
    def get_water_level_at_point(self, 
                                 lon: float, 
                                 lat: float, 
                                 query_time: datetime,
                                 method: str = 'nearest_station') -> float:
        """
        Get water level at specific location and time.
        
        Args:
            lon: Longitude
            lat: Latitude
            query_time: Query time
            method: 'nearest_station', 'grid', or 'interpolate'
            
        Returns:
            Water level in meters relative to datum
        """
        if method == 'nearest_station':
            return self._get_from_nearest_station(lon, lat, query_time)
        elif method == 'grid':
            return self._get_from_grid(lon, lat, query_time)
        elif method == 'interpolate':
            return self._get_interpolated(lon, lat, query_time)
        else:
            raise ValueError(f"Unknown method: {method}")
    
    def _get_from_nearest_station(self, lon: float, lat: float, query_time: datetime) -> float:
        """Get water level from nearest tide station"""
        if not self.stations:
            return 0.0
        
        # Find nearest station
        min_dist = float('inf')
        nearest = None
        
        for station in self.stations.values():
            slon, slat = station.position
            dist = np.sqrt((lon - slon)**2 + (lat - slat)**2)
            if dist < min_dist:
                min_dist = dist
                nearest = station
        
        if nearest:
            return nearest.get_water_level(query_time)
        
        return 0.0
    
    def _get_from_grid(self, lon: float, lat: float, query_time: datetime) -> float:
        """Get water level from gridded data"""
        if self.grid_data is None or self.grid_times is None:
            return 0.0
        
        # Find time indices for interpolation
        time_idx = self._find_time_indices(query_time)
        
        if time_idx is None:
            return 0.0
        
        t1_idx, t2_idx, t_weight = time_idx
        
        # Find spatial indices
        min_lon, min_lat, max_lon, max_lat = self.grid_bounds
        ny, nx = self.grid_data.shape[1:3]
        
        # Normalize to grid coordinates
        x = (lon - min_lon) / (max_lon - min_lon) * (nx - 1)
        y = (lat - min_lat) / (max_lat - min_lat) * (ny - 1)
        
        # Bilinear interpolation in space, linear in time
        if 0 <= x < nx and 0 <= y < ny:
            # Get values at two time steps
            val1 = self._bilinear_interpolate(self.grid_data[t1_idx], x, y)
            val2 = self._bilinear_interpolate(self.grid_data[t2_idx], x, y)
            
            # Linear interpolation in time
            return val1 * (1 - t_weight) + val2 * t_weight
        
        return 0.0
    
    def _find_time_indices(self, query_time: datetime) -> Optional[Tuple[int, int, float]]:
        """Find time indices and weight for interpolation"""
        if not self.grid_times:
            return None
        
        # Convert to timestamp for comparison
        qt = pd.Timestamp(query_time)
        times = [pd.Timestamp(t) for t in self.grid_times]
        
        # Check bounds
        if qt <= times[0]:
            return 0, 0, 0.0
        if qt >= times[-1]:
            return len(times)-1, len(times)-1, 0.0
        
        # Find bracketing indices
        for i in range(len(times) - 1):
            if times[i] <= qt <= times[i+1]:
                # Calculate weight
                dt_total = (times[i+1] - times[i]).total_seconds()
                dt_query = (qt - times[i]).total_seconds()
                weight = dt_query / dt_total if dt_total > 0 else 0.0
                return i, i+1, weight
        
        return None
    
    def _bilinear_interpolate(self, grid: np.ndarray, x: float, y: float) -> float:
        """Bilinear interpolation on 2D grid"""
        x1 = int(np.floor(x))
        x2 = min(x1 + 1, grid.shape[1] - 1)
        y1 = int(np.floor(y))
        y2 = min(y1 + 1, grid.shape[0] - 1)
        
        # Weights
        wx = x - x1
        wy = y - y1
        
        # Interpolate
        val = (grid[y1, x1] * (1-wx) * (1-wy) +
               grid[y1, x2] * wx * (1-wy) +
               grid[y2, x1] * (1-wx) * wy +
               grid[y2, x2] * wx * wy)
        
        return float(val)
    
    def _get_interpolated(self, lon: float, lat: float, query_time: datetime) -> float:
        """Get water level using spatial interpolation of stations"""
        if not self.stations:
            return self._get_from_grid(lon, lat, query_time)
        
        # Inverse distance weighting from multiple stations
        weights = []
        values = []
        
        for station in self.stations.values():
            slon, slat = station.position
            dist = np.sqrt((lon - slon)**2 + (lat - slat)**2)
            
            if dist < 1e-6:  # At station location
                return station.get_water_level(query_time)
            
            weight = 1.0 / dist
            weights.append(weight)
            values.append(station.get_water_level(query_time))
        
        if weights:
            total_weight = sum(weights)
            weighted_value = sum(w * v for w, v in zip(weights, values))
            return weighted_value / total_weight
        
        return 0.0
    
    def get_tide_windows(self, 
                        position: Tuple[float, float],
                        start_time: datetime,
                        duration_hours: float = 24,
                        threshold: float = 0.0) -> List[Tuple[datetime, datetime]]:
        """
        Find high tide windows above threshold.
        
        Args:
            position: (lon, lat) position
            start_time: Start of search period
            duration_hours: Duration to search
            threshold: Water level threshold (m)
            
        Returns:
            List of (start, end) time windows
        """
        lon, lat = position
        windows = []
        
        # Sample at 10-minute intervals
        sample_interval = timedelta(minutes=10)
        n_samples = int(duration_hours * 60 / 10)
        
        in_window = False
        window_start = None
        
        for i in range(n_samples):
            sample_time = start_time + i * sample_interval
            water_level = self.get_water_level_at_point(lon, lat, sample_time)
            
            if water_level >= threshold:
                if not in_window:
                    # Start new window
                    window_start = sample_time
                    in_window = True
            else:
                if in_window:
                    # End window
                    windows.append((window_start, sample_time))
                    in_window = False
        
        # Close last window if still open
        if in_window:
            windows.append((window_start, start_time + timedelta(hours=duration_hours)))
        
        return windows
    
    def generate_tide_curve(self,
                           position: Tuple[float, float],
                           start_time: datetime,
                           duration_hours: float = 24,
                           sample_minutes: float = 10) -> pd.DataFrame:
        """
        Generate tide curve for visualization.
        
        Args:
            position: (lon, lat) position
            start_time: Start time
            duration_hours: Duration
            sample_minutes: Sampling interval
            
        Returns:
            DataFrame with columns: time, water_level
        """
        lon, lat = position
        samples = []
        
        n_samples = int(duration_hours * 60 / sample_minutes)
        
        for i in range(n_samples):
            sample_time = start_time + timedelta(minutes=i * sample_minutes)
            water_level = self.get_water_level_at_point(lon, lat, sample_time)
            samples.append({
                'time': sample_time,
                'water_level': water_level
            })
        
        return pd.DataFrame(samples)


def create_mock_s104_data(output_dir: str = "datasets/s104"):
    """Create mock S-104 data for testing"""
    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)
    
    # Create mock tide station data
    station_data = """station_id,name,lon,lat,datum
STATION001,Test Harbor,-122.4,37.8,MSL
2025-01-01T00:00:00,0.0
2025-01-01T06:00:00,2.5
2025-01-01T12:00:00,0.5
2025-01-01T18:00:00,2.0
2025-01-02T00:00:00,0.2"""
    
    with open(output_path / "station001.csv", 'w') as f:
        f.write(station_data)
    
    # Create mock grid data (no header row)
    grid_data = """2025-01-01T00:00:00,-123.0,37.0,-122.0,38.0,3,3,0.0,0.5,1.0,0.5,1.0,1.5,1.0,1.5,2.0
2025-01-01T06:00:00,-123.0,37.0,-122.0,38.0,3,3,2.0,2.5,3.0,2.5,3.0,3.5,3.0,3.5,4.0
2025-01-01T12:00:00,-123.0,37.0,-122.0,38.0,3,3,0.5,1.0,1.5,1.0,1.5,2.0,1.5,2.0,2.5"""
    
    with open(output_path / "grid_data.csv", 'w') as f:
        f.write(grid_data)
    
    logger.info(f"Created mock S-104 data in {output_dir}")


if __name__ == "__main__":
    # Create test data
    create_mock_s104_data()