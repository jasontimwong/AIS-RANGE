"""
Tests for S-104 Water Level/Tide Adapter
"""

import pytest
import numpy as np
import pandas as pd
from datetime import datetime, timedelta
import tempfile
from pathlib import Path
import sys
import os

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from lib.enc.s104_adapter import (
    TideStation,
    S104Adapter,
    create_mock_s104_data
)


class TestTideStation:
    """Test TideStation class"""
    
    def test_station_creation(self):
        """Test creating tide station"""
        ts_data = pd.DataFrame({
            'time': pd.date_range('2025-01-01', periods=5, freq='6h'),
            'water_level': [0.0, 2.5, 0.5, 2.0, 0.2]
        })
        
        station = TideStation(
            station_id="TEST001",
            name="Test Station",
            position=(-122.4, 37.8),
            datum="MSL",
            time_series=ts_data
        )
        
        assert station.station_id == "TEST001"
        assert station.position == (-122.4, 37.8)
        assert len(station.time_series) == 5
    
    def test_water_level_interpolation(self):
        """Test water level interpolation"""
        ts_data = pd.DataFrame({
            'time': pd.date_range('2025-01-01', periods=3, freq='6h'),
            'water_level': [0.0, 3.0, 0.0]
        })
        
        station = TideStation(
            station_id="TEST002",
            name="Test Station",
            position=(0, 0),
            datum="MSL",
            time_series=ts_data
        )
        
        # Test exact time
        level = station.get_water_level(datetime(2025, 1, 1, 6, 0))
        assert level == 3.0
        
        # Test interpolation
        level = station.get_water_level(datetime(2025, 1, 1, 3, 0))
        assert abs(level - 1.5) < 0.01  # Halfway between 0 and 3
        
        # Test extrapolation (before)
        level = station.get_water_level(datetime(2024, 12, 31))
        assert level == 0.0  # First value
        
        # Test extrapolation (after)
        level = station.get_water_level(datetime(2025, 1, 2))
        assert level == 0.0  # Last value


class TestS104Adapter:
    """Test S104Adapter class"""
    
    def test_adapter_initialization(self):
        """Test adapter initialization"""
        adapter = S104Adapter()
        
        assert adapter.stations == {}
        assert adapter.grid_data is None
        assert adapter.grid_times is None
    
    def test_load_station_data(self, tmp_path):
        """Test loading station data from CSV"""
        # Create test CSV
        csv_content = """station_id,name,lon,lat,datum
TEST003,Harbor,-122.4,37.8,MSL
2025-01-01T00:00:00,0.0
2025-01-01T06:00:00,2.5
2025-01-01T12:00:00,0.5"""
        
        csv_file = tmp_path / "test_station.csv"
        csv_file.write_text(csv_content)
        
        adapter = S104Adapter()
        station = adapter.load_station_data(str(csv_file))
        
        assert station.station_id == "TEST003"
        assert station.name == "Harbor"
        assert station.position == (-122.4, 37.8)
        assert len(station.time_series) == 3
        assert "TEST003" in adapter.stations
    
    def test_load_grid_data(self, tmp_path):
        """Test loading gridded water level data"""
        # Create test grid CSV (no header)
        grid_content = """2025-01-01T00:00:00,-123.0,37.0,-122.0,38.0,2,2,0.0,1.0,2.0,3.0
2025-01-01T06:00:00,-123.0,37.0,-122.0,38.0,2,2,1.0,2.0,3.0,4.0"""
        
        grid_file = tmp_path / "test_grid.csv"
        grid_file.write_text(grid_content)
        
        adapter = S104Adapter()
        grid_data, times = adapter.load_grid_data(str(grid_file))
        
        assert grid_data.shape == (2, 2, 2)  # 2 times, 2x2 grid
        assert len(times) == 2
        assert adapter.grid_bounds == (-123.0, 37.0, -122.0, 38.0)
    
    def test_get_water_level_nearest_station(self, tmp_path):
        """Test getting water level from nearest station"""
        # Create test station
        csv_content = """station_id,name,lon,lat,datum
TEST004,Station1,-122.0,37.0,MSL
2025-01-01T00:00:00,1.0
2025-01-01T12:00:00,2.0"""
        
        csv_file = tmp_path / "station.csv"
        csv_file.write_text(csv_content)
        
        adapter = S104Adapter()
        adapter.load_station_data(str(csv_file))
        
        # Query near station
        level = adapter.get_water_level_at_point(
            -122.1, 37.1,
            datetime(2025, 1, 1, 6, 0),
            method='nearest_station'
        )
        
        assert abs(level - 1.5) < 0.1  # Interpolated value
    
    def test_get_water_level_from_grid(self, tmp_path):
        """Test getting water level from grid"""
        # Create simple grid (no header)
        grid_content = """2025-01-01T00:00:00,-123.0,37.0,-122.0,38.0,2,2,0.0,1.0,2.0,3.0
2025-01-01T06:00:00,-123.0,37.0,-122.0,38.0,2,2,4.0,5.0,6.0,7.0"""
        
        grid_file = tmp_path / "grid.csv"
        grid_file.write_text(grid_content)
        
        adapter = S104Adapter()
        adapter.load_grid_data(str(grid_file))
        
        # Query at grid point
        level = adapter.get_water_level_at_point(
            -122.5, 37.5,  # Center of grid
            datetime(2025, 1, 1, 0, 0),
            method='grid'
        )
        
        # Should interpolate between grid points
        assert level >= 0.0 and level <= 3.0
        
        # Query with time interpolation
        level = adapter.get_water_level_at_point(
            -122.5, 37.5,
            datetime(2025, 1, 1, 3, 0),  # Halfway in time
            method='grid'
        )
        
        # Should be between two time steps
        assert level >= 0.0 and level <= 7.0
    
    def test_get_tide_windows(self, tmp_path):
        """Test finding high tide windows"""
        # Create station with periodic tide
        ts_data = pd.DataFrame({
            'time': pd.date_range('2025-01-01', periods=25, freq='1h'),
            'water_level': [1.0 + 1.5 * np.sin(2 * np.pi * i / 12) for i in range(25)]
        })
        
        station = TideStation(
            station_id="TEST005",
            name="Tidal Station",
            position=(0, 0),
            datum="MSL",
            time_series=ts_data
        )
        
        adapter = S104Adapter()
        adapter.stations["TEST005"] = station
        
        # Find windows above 2.0m
        windows = adapter.get_tide_windows(
            position=(0, 0),
            start_time=datetime(2025, 1, 1),
            duration_hours=24,
            threshold=2.0
        )
        
        assert len(windows) >= 1  # Should find at least one high tide window
        
        for start, end in windows:
            assert start < end
            # Check that water level is high during window
            mid_time = start + (end - start) / 2
            level = adapter.get_water_level_at_point(0, 0, mid_time)
            assert level >= 1.5  # Should be near or above threshold
    
    def test_generate_tide_curve(self, tmp_path):
        """Test generating tide curve for visualization"""
        # Create simple station
        ts_data = pd.DataFrame({
            'time': pd.date_range('2025-01-01', periods=5, freq='6h'),
            'water_level': [0.0, 2.0, 0.0, 2.0, 0.0]
        })
        
        station = TideStation(
            station_id="TEST006",
            name="Curve Station",
            position=(0, 0),
            datum="MSL",
            time_series=ts_data
        )
        
        adapter = S104Adapter()
        adapter.stations["TEST006"] = station
        
        # Generate curve
        curve = adapter.generate_tide_curve(
            position=(0, 0),
            start_time=datetime(2025, 1, 1),
            duration_hours=12,
            sample_minutes=60
        )
        
        assert len(curve) == 12  # 12 hours at 60-minute intervals
        assert 'time' in curve.columns
        assert 'water_level' in curve.columns
        
        # Check that values are interpolated
        assert curve['water_level'].min() >= 0.0
        assert curve['water_level'].max() <= 2.0
    
    def test_create_mock_data(self, tmp_path):
        """Test creating mock S-104 data"""
        output_dir = tmp_path / "s104_mock"
        create_mock_s104_data(str(output_dir))
        
        # Check files were created
        assert (output_dir / "station001.csv").exists()
        assert (output_dir / "grid_data.csv").exists()
        
        # Try loading the mock data
        adapter = S104Adapter()
        adapter.load_station_data(str(output_dir / "station001.csv"))
        adapter.load_grid_data(str(output_dir / "grid_data.csv"))
        
        assert "STATION001" in adapter.stations
        assert adapter.grid_data is not None