"""
Tests for S-421 bidirectional interoperability
"""

import pytest
import json
import tempfile
from pathlib import Path
import sys
import os

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from lib.io.s421_roundtrip import (
    S421Route,
    export_to_s421,
    import_from_s421,
    roundtrip_test,
    batch_convert
)


class TestS421Route:
    """Test S421Route class"""
    
    def test_checksum_calculation(self):
        """Test checksum calculation"""
        route = S421Route(
            route_id="TEST001",
            name="Test Route",
            waypoints=[
                {'position': {'lat': 0, 'lon': 0}},
                {'position': {'lat': 1, 'lon': 1}}
            ]
        )
        
        checksum1 = route.calculate_checksum()
        assert checksum1 is not None
        assert len(checksum1) == 64  # SHA256 hex length
        
        # Same data should give same checksum
        checksum2 = route.calculate_checksum()
        assert checksum1 == checksum2
        
        # Different data should give different checksum
        route.name = "Modified Route"
        checksum3 = route.calculate_checksum()
        assert checksum1 != checksum3
    
    def test_checksum_validation(self):
        """Test checksum validation"""
        route = S421Route(
            route_id="TEST002",
            name="Test Route",
            waypoints=[]
        )
        
        # No checksum should validate
        assert route.validate_checksum() == True
        
        # Correct checksum should validate
        route.checksum = route.calculate_checksum()
        assert route.validate_checksum() == True
        
        # Incorrect checksum should fail
        route.checksum = "invalid_checksum"
        assert route.validate_checksum() == False


class TestExportImport:
    """Test export and import functions"""
    
    def test_export_basic(self, tmp_path):
        """Test basic export to S-421"""
        route_data = {
            'route_id': 'TEST003',
            'name': 'Export Test',
            'waypoints': [
                {'lat': 10.0, 'lon': 20.0, 'speed': 15.0},
                {'lat': 11.0, 'lon': 21.0, 'speed': 12.0}
            ]
        }
        
        output_file = tmp_path / "export_test.json"
        s421_route = export_to_s421(route_data, str(output_file))
        
        assert s421_route.route_id == 'TEST003'
        assert s421_route.name == 'Export Test'
        assert len(s421_route.waypoints) == 2
        assert s421_route.checksum is not None
        assert output_file.exists()
        
        # Verify file content
        with open(output_file, 'r') as f:
            exported_data = json.load(f)
        
        assert exported_data['route_id'] == 'TEST003'
        assert len(exported_data['waypoints']) == 2
    
    def test_import_basic(self, tmp_path):
        """Test basic import from S-421"""
        # Create S-421 file
        s421_data = {
            'route_id': 'TEST004',
            'name': 'Import Test',
            'waypoints': [
                {
                    'position': {'lat': 30.0, 'lon': 40.0},
                    'speed': 10.0,
                    'turn_radius': 0.5
                }
            ],
            'checksum': 'dummy_checksum'
        }
        
        input_file = tmp_path / "import_test.json"
        with open(input_file, 'w') as f:
            json.dump(s421_data, f)
        
        # Import without checksum validation
        internal_route = import_from_s421(str(input_file), validate_checksum=False)
        
        assert internal_route['route_id'] == 'TEST004'
        assert internal_route['name'] == 'Import Test'
        assert len(internal_route['waypoints']) == 1
        assert internal_route['waypoints'][0]['lat'] == 30.0
        assert internal_route['waypoints'][0]['lon'] == 40.0
    
    def test_export_with_schedule(self, tmp_path):
        """Test export with schedule information"""
        route_data = {
            'route_id': 'TEST005',
            'name': 'Scheduled Route',
            'waypoints': [
                {'lat': 0, 'lon': 0}
            ],
            'schedule': {
                'departure_time': '2025-01-01T10:00:00Z',
                'arrival_time': '2025-01-01T18:00:00Z',
                'time_zone': 'UTC'
            }
        }
        
        output_file = tmp_path / "schedule_test.json"
        s421_route = export_to_s421(route_data, str(output_file))
        
        assert s421_route.schedule is not None
        assert s421_route.schedule['departure_time'] == '2025-01-01T10:00:00Z'


class TestRoundtrip:
    """Test roundtrip conversion"""
    
    def test_simple_roundtrip(self, tmp_path):
        """Test simple roundtrip conversion"""
        original_route = {
            'route_id': 'RT001',
            'name': 'Roundtrip Test',
            'waypoints': [
                {
                    'lat': 50.0,
                    'lon': -10.0,
                    'speed': 15.0,
                    'turn_radius': 0.5,
                    'xtd_port': 0.1,
                    'xtd_starboard': 0.1
                },
                {
                    'lat': 51.0,
                    'lon': -9.0,
                    'speed': 12.0,
                    'turn_radius': 0.3,
                    'xtd_port': 0.2,
                    'xtd_starboard': 0.2
                }
            ]
        }
        
        success, comparison = roundtrip_test(original_route, str(tmp_path))
        
        assert success == True
        assert comparison['waypoint_count_match'] == True
        assert len(comparison['position_differences']) == 0
        assert len(comparison['attribute_differences']) == 0
    
    def test_roundtrip_with_optional_fields(self, tmp_path):
        """Test roundtrip with optional fields"""
        original_route = {
            'route_id': 'RT002',
            'name': 'Complex Roundtrip',
            'waypoints': [
                {
                    'lat': 60.0,
                    'lon': 10.0,
                    'speed': 20.0,
                    'turn_radius': 1.0,
                    'xtd_port': 0.5,
                    'xtd_starboard': 0.5,
                    'eta': '2025-01-01T12:00:00Z',
                    'heading': 45.0
                }
            ]
        }
        
        success, comparison = roundtrip_test(original_route, str(tmp_path))
        
        assert success == True
        assert comparison['waypoint_count_match'] == True


class TestBatchConvert:
    """Test batch conversion"""
    
    def test_batch_convert_to_s421(self, tmp_path):
        """Test batch conversion to S-421"""
        input_dir = tmp_path / "input"
        output_dir = tmp_path / "output"
        input_dir.mkdir()
        
        # Create test files
        for i in range(3):
            route_data = {
                'route_id': f'BATCH{i:03d}',
                'name': f'Batch Route {i}',
                'waypoints': [
                    {'lat': float(i), 'lon': float(i*10)}
                ]
            }
            
            with open(input_dir / f"route_{i}.json", 'w') as f:
                json.dump(route_data, f)
        
        # Batch convert
        report = batch_convert(str(input_dir), str(output_dir), "to_s421")
        
        assert report['total_files'] == 3
        assert report['successful'] == 3
        assert report['failed'] == 0
        
        # Check output files
        output_files = list(output_dir.glob("*.json"))
        assert len(output_files) == 3
    
    def test_batch_convert_from_s421(self, tmp_path):
        """Test batch conversion from S-421"""
        input_dir = tmp_path / "input"
        output_dir = tmp_path / "output"
        input_dir.mkdir()
        
        # Create S-421 files
        for i in range(2):
            s421_data = {
                'route_id': f'S421_{i:03d}',
                'name': f'S421 Route {i}',
                'waypoints': [
                    {
                        'position': {'lat': float(i), 'lon': float(i*10)},
                        'speed': 10.0
                    }
                ]
            }
            
            with open(input_dir / f"s421_{i}.json", 'w') as f:
                json.dump(s421_data, f)
        
        # Batch convert
        report = batch_convert(str(input_dir), str(output_dir), "from_s421")
        
        assert report['total_files'] == 2
        assert report['successful'] == 2
        assert report['failed'] == 0