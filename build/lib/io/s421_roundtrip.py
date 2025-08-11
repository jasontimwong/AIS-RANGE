"""
S-421 Bidirectional Interoperability
Roundtrip conversion between internal and S-421 formats
"""

from dataclasses import dataclass, asdict
from typing import List, Dict, Any, Optional, Tuple
import json
import datetime as dt
import logging
import hashlib
from pathlib import Path

logger = logging.getLogger(__name__)


@dataclass
class S421Route:
    """S-421 Route representation"""
    route_id: str
    name: str
    waypoints: List[Dict[str, Any]]
    schedule: Optional[Dict[str, Any]] = None
    metadata: Optional[Dict[str, Any]] = None
    checksum: Optional[str] = None
    
    def calculate_checksum(self) -> str:
        """Calculate SHA256 checksum for route integrity"""
        data = {
            'route_id': self.route_id,
            'name': self.name,
            'waypoints': self.waypoints,
            'schedule': self.schedule
        }
        json_str = json.dumps(data, sort_keys=True)
        return hashlib.sha256(json_str.encode()).hexdigest()
    
    def validate_checksum(self) -> bool:
        """Validate route integrity via checksum"""
        if not self.checksum:
            return True  # No checksum to validate
        return self.checksum == self.calculate_checksum()


def export_to_s421(route_data: Dict[str, Any], 
                   output_path: str,
                   include_metadata: bool = True) -> S421Route:
    """
    Export internal route to S-421 format.
    
    Args:
        route_data: Internal route dictionary
        output_path: Output file path
        include_metadata: Whether to include metadata
        
    Returns:
        S421Route object
    """
    # Convert waypoints to S-421 format
    s421_waypoints = []
    for wp in route_data.get('waypoints', []):
        s421_wp = {
            'position': {
                'lat': wp['lat'],
                'lon': wp['lon']
            },
            'turn_radius': wp.get('turn_radius', 0.5),
            'speed': wp.get('speed', 10.0),
            'leg_info': {
                'xtd_port': wp.get('xtd_port', 0.1),
                'xtd_starboard': wp.get('xtd_starboard', 0.1)
            }
        }
        
        # Add optional fields
        if 'eta' in wp:
            s421_wp['eta'] = wp['eta']
        if 'heading' in wp:
            s421_wp['heading'] = wp['heading']
            
        s421_waypoints.append(s421_wp)
    
    # Create S-421 route
    s421_route = S421Route(
        route_id=route_data.get('route_id', f"ROUTE_{dt.datetime.now().strftime('%Y%m%d%H%M%S')}"),
        name=route_data.get('name', 'Unnamed Route'),
        waypoints=s421_waypoints
    )
    
    # Add schedule if present
    if 'schedule' in route_data:
        s421_route.schedule = {
            'departure_time': route_data['schedule'].get('departure_time'),
            'arrival_time': route_data['schedule'].get('arrival_time'),
            'time_zone': route_data['schedule'].get('time_zone', 'UTC')
        }
    
    # Add metadata
    if include_metadata:
        s421_route.metadata = {
            'created': dt.datetime.now().isoformat(),
            'version': '1.0.0',
            'generator': 'ECDIS Route Planner',
            'standards': ['S-421', 'RTZ 1.0']
        }
    
    # Calculate checksum
    s421_route.checksum = s421_route.calculate_checksum()
    
    # Save to file
    output_dict = asdict(s421_route)
    with open(output_path, 'w') as f:
        json.dump(output_dict, f, indent=2, default=str)
    
    logger.info(f"Exported route to S-421: {output_path} (checksum: {s421_route.checksum[:8]}...)")
    
    return s421_route


def import_from_s421(input_path: str, 
                     validate_checksum: bool = True) -> Dict[str, Any]:
    """
    Import S-421 route to internal format.
    
    Args:
        input_path: Input file path
        validate_checksum: Whether to validate checksum
        
    Returns:
        Internal route dictionary
    """
    with open(input_path, 'r') as f:
        s421_data = json.load(f)
    
    # Create S421Route object
    s421_route = S421Route(
        route_id=s421_data['route_id'],
        name=s421_data['name'],
        waypoints=s421_data['waypoints'],
        schedule=s421_data.get('schedule'),
        metadata=s421_data.get('metadata'),
        checksum=s421_data.get('checksum')
    )
    
    # Validate checksum if requested
    if validate_checksum and s421_route.checksum:
        if not s421_route.validate_checksum():
            raise ValueError(f"Checksum validation failed for route {s421_route.route_id}")
        logger.info(f"Checksum validated for route {s421_route.route_id}")
    
    # Convert to internal format
    internal_waypoints = []
    for wp in s421_route.waypoints:
        internal_wp = {
            'lat': wp['position']['lat'],
            'lon': wp['position']['lon'],
            'turn_radius': wp.get('turn_radius', 0.5),
            'speed': wp.get('speed', 10.0),
            'xtd_port': wp.get('leg_info', {}).get('xtd_port', 0.1),
            'xtd_starboard': wp.get('leg_info', {}).get('xtd_starboard', 0.1)
        }
        
        # Add optional fields
        if 'eta' in wp:
            internal_wp['eta'] = wp['eta']
        if 'heading' in wp:
            internal_wp['heading'] = wp['heading']
            
        internal_waypoints.append(internal_wp)
    
    # Build internal route
    internal_route = {
        'route_id': s421_route.route_id,
        'name': s421_route.name,
        'waypoints': internal_waypoints
    }
    
    # Add schedule if present
    if s421_route.schedule:
        internal_route['schedule'] = s421_route.schedule
    
    # Add metadata for tracking
    internal_route['import_metadata'] = {
        'source': 'S-421',
        'imported_at': dt.datetime.now().isoformat(),
        'original_checksum': s421_route.checksum
    }
    
    logger.info(f"Imported S-421 route: {s421_route.route_id} ({len(internal_waypoints)} waypoints)")
    
    return internal_route


def roundtrip_test(route_data: Dict[str, Any], 
                   temp_dir: str = "/tmp") -> Tuple[bool, Dict[str, Any]]:
    """
    Test roundtrip conversion fidelity.
    
    Args:
        route_data: Original route data
        temp_dir: Temporary directory for files
        
    Returns:
        (success, comparison_report)
    """
    temp_path = Path(temp_dir) / f"roundtrip_{dt.datetime.now().strftime('%Y%m%d%H%M%S')}.json"
    
    # Export to S-421
    s421_route = export_to_s421(route_data, str(temp_path))
    
    # Import back
    imported_route = import_from_s421(str(temp_path))
    
    # Compare waypoints
    original_waypoints = route_data['waypoints']
    imported_waypoints = imported_route['waypoints']
    
    comparison = {
        'waypoint_count_match': len(original_waypoints) == len(imported_waypoints),
        'position_differences': [],
        'attribute_differences': [],
        'checksum_valid': True
    }
    
    # Check each waypoint
    for i, (orig, imp) in enumerate(zip(original_waypoints, imported_waypoints)):
        # Position difference
        lat_diff = abs(orig['lat'] - imp['lat'])
        lon_diff = abs(orig['lon'] - imp['lon'])
        
        if lat_diff > 1e-6 or lon_diff > 1e-6:
            comparison['position_differences'].append({
                'waypoint': i,
                'lat_diff': lat_diff,
                'lon_diff': lon_diff
            })
        
        # Attribute differences
        for key in ['speed', 'turn_radius', 'xtd_port', 'xtd_starboard']:
            if key in orig:
                orig_val = orig.get(key)
                imp_val = imp.get(key)
                if orig_val != imp_val:
                    comparison['attribute_differences'].append({
                        'waypoint': i,
                        'attribute': key,
                        'original': orig_val,
                        'imported': imp_val
                    })
    
    # Overall success
    success = (
        comparison['waypoint_count_match'] and
        len(comparison['position_differences']) == 0 and
        len(comparison['attribute_differences']) == 0
    )
    
    # Clean up temp file
    temp_path.unlink(missing_ok=True)
    
    logger.info(f"Roundtrip test: {'PASSED' if success else 'FAILED'}")
    
    return success, comparison


def batch_convert(input_dir: str, 
                  output_dir: str,
                  direction: str = "to_s421") -> Dict[str, Any]:
    """
    Batch convert multiple route files.
    
    Args:
        input_dir: Input directory
        output_dir: Output directory  
        direction: "to_s421" or "from_s421"
        
    Returns:
        Conversion report
    """
    input_path = Path(input_dir)
    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)
    
    report = {
        'total_files': 0,
        'successful': 0,
        'failed': 0,
        'errors': []
    }
    
    # Process each file
    pattern = "*.json"
    for file_path in input_path.glob(pattern):
        report['total_files'] += 1
        
        try:
            if direction == "to_s421":
                # Load internal format
                with open(file_path, 'r') as f:
                    route_data = json.load(f)
                
                # Export to S-421
                output_file = output_path / f"{file_path.stem}_s421.json"
                export_to_s421(route_data, str(output_file))
                
            elif direction == "from_s421":
                # Import from S-421
                internal_route = import_from_s421(str(file_path))
                
                # Save internal format
                output_file = output_path / f"{file_path.stem}_internal.json"
                with open(output_file, 'w') as f:
                    json.dump(internal_route, f, indent=2, default=str)
            
            else:
                raise ValueError(f"Invalid direction: {direction}")
            
            report['successful'] += 1
            logger.info(f"Converted: {file_path.name}")
            
        except Exception as e:
            report['failed'] += 1
            report['errors'].append({
                'file': file_path.name,
                'error': str(e)
            })
            logger.error(f"Failed to convert {file_path.name}: {e}")
    
    return report