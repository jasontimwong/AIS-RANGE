"""
RTZ (Route Exchange Format) I/O Module
Implements IEC 61174:2015 Ed.4 Annex S compliant RTZ import/export.
Handles route data exchange with ECDIS systems.
"""

from typing import List, Dict, Optional, Any, Tuple
from dataclasses import dataclass, field
from datetime import datetime
import xml.etree.ElementTree as ET
from xml.dom import minidom
import json
import logging
from pathlib import Path
import uuid

logger = logging.getLogger(__name__)

# RTZ XML namespace
RTZ_NAMESPACE = "http://www.cirm.org/RTZ/1/2"
RTZ_NS = {"rtz": RTZ_NAMESPACE}


@dataclass
class RTZWaypoint:
    """Represents a waypoint in RTZ format."""
    id: str
    name: str
    lat: float  # Latitude in decimal degrees
    lon: float  # Longitude in decimal degrees
    radius: Optional[float] = None  # Turn radius in NM
    leg_info: Optional[Dict[str, Any]] = field(default_factory=dict)
    extensions: Optional[Dict[str, Any]] = field(default_factory=dict)
    
    # Speed and time parameters
    speed: Optional[float] = None  # Speed in knots
    speed_min: Optional[float] = None  # Minimum speed
    speed_max: Optional[float] = None  # Maximum speed
    eta: Optional[datetime] = None  # Estimated time of arrival
    etd: Optional[datetime] = None  # Estimated time of departure
    
    # Geometry parameters
    port_xte: Optional[float] = None  # Port side XTE limit (NM)
    starboard_xte: Optional[float] = None  # Starboard side XTE limit (NM)
    turn_radius: Optional[float] = None  # Turn radius (NM)
    
    def to_xml_element(self) -> ET.Element:
        """Convert waypoint to XML element."""
        wp_elem = ET.Element("waypoint")
        
        # Required attributes
        wp_elem.set("id", str(self.id))
        wp_elem.set("name", self.name)
        
        # Position
        position = ET.SubElement(wp_elem, "position")
        position.set("lat", f"{self.lat:.6f}")
        position.set("lon", f"{self.lon:.6f}")
        
        # Optional leg information
        if self.speed or self.port_xte or self.starboard_xte:
            leg = ET.SubElement(wp_elem, "leg")
            if self.speed:
                leg.set("speed", f"{self.speed:.1f}")
            if self.speed_min:
                leg.set("speedMin", f"{self.speed_min:.1f}")
            if self.speed_max:
                leg.set("speedMax", f"{self.speed_max:.1f}")
            if self.port_xte:
                leg.set("portsideXTE", f"{self.port_xte:.2f}")
            if self.starboard_xte:
                leg.set("starboardXTE", f"{self.starboard_xte:.2f}")
            if self.turn_radius:
                leg.set("turnRadius", f"{self.turn_radius:.2f}")
        
        # Extensions
        if self.extensions:
            ext_elem = ET.SubElement(wp_elem, "extensions")
            for key, value in self.extensions.items():
                ext_child = ET.SubElement(ext_elem, key)
                ext_child.text = str(value)
        
        return wp_elem
    
    @classmethod
    def from_xml_element(cls, elem: ET.Element) -> 'RTZWaypoint':
        """Create waypoint from XML element."""
        # Get basic attributes
        wp_id = elem.get("id", "")
        name = elem.get("name", "")
        
        # Get position
        pos_elem = elem.find(".//position")
        lat = float(pos_elem.get("lat", 0))
        lon = float(pos_elem.get("lon", 0))
        
        wp = cls(id=wp_id, name=name, lat=lat, lon=lon)
        
        # Get leg information if present
        leg_elem = elem.find(".//leg")
        if leg_elem is not None:
            if leg_elem.get("speed"):
                wp.speed = float(leg_elem.get("speed"))
            if leg_elem.get("speedMin"):
                wp.speed_min = float(leg_elem.get("speedMin"))
            if leg_elem.get("speedMax"):
                wp.speed_max = float(leg_elem.get("speedMax"))
            if leg_elem.get("portsideXTE"):
                wp.port_xte = float(leg_elem.get("portsideXTE"))
            if leg_elem.get("starboardXTE"):
                wp.starboard_xte = float(leg_elem.get("starboardXTE"))
            if leg_elem.get("turnRadius"):
                wp.turn_radius = float(leg_elem.get("turnRadius"))
        
        # Get extensions
        ext_elem = elem.find(".//extensions")
        if ext_elem is not None:
            wp.extensions = {}
            for child in ext_elem:
                wp.extensions[child.tag] = child.text
        
        return wp


@dataclass
class RTZRoute:
    """Represents a complete RTZ route."""
    route_name: str
    waypoints: List[RTZWaypoint]
    route_info: Dict[str, Any] = field(default_factory=dict)
    
    # Metadata
    version: str = "1.2"
    xmlns: str = RTZ_NAMESPACE
    route_status: str = "PlannedForVoyage"  # or "Optimized", "Executed", etc.
    valid_from: Optional[datetime] = None
    valid_to: Optional[datetime] = None
    
    def to_xml(self) -> str:
        """Convert route to RTZ XML string."""
        # Create root element
        root = ET.Element("route")
        root.set("version", self.version)
        root.set("xmlns", self.xmlns)
        
        # Route info
        route_info = ET.SubElement(root, "routeInfo")
        route_info.set("routeName", self.route_name)
        if self.route_status:
            route_info.set("routeStatus", self.route_status)
        if self.valid_from:
            route_info.set("validFrom", self.valid_from.isoformat())
        if self.valid_to:
            route_info.set("validTo", self.valid_to.isoformat())
        
        # Add additional route info
        for key, value in self.route_info.items():
            elem = ET.SubElement(route_info, key)
            elem.text = str(value)
        
        # Waypoints
        waypoints_elem = ET.SubElement(root, "waypoints")
        for wp in self.waypoints:
            waypoints_elem.append(wp.to_xml_element())
        
        # Convert to pretty-printed string
        xml_str = ET.tostring(root, encoding='unicode')
        dom = minidom.parseString(xml_str)
        return dom.toprettyxml(indent="  ")
    
    @classmethod
    def from_xml(cls, xml_content: str) -> 'RTZRoute':
        """Parse RTZ route from XML string."""
        root = ET.fromstring(xml_content)
        
        # Get route info
        route_info_elem = root.find(".//routeInfo")
        route_name = route_info_elem.get("routeName", "Unnamed Route")
        route_status = route_info_elem.get("routeStatus", "PlannedForVoyage")
        
        # Parse waypoints
        waypoints = []
        waypoints_elem = root.find(".//waypoints")
        if waypoints_elem is not None:
            for wp_elem in waypoints_elem.findall("waypoint"):
                waypoints.append(RTZWaypoint.from_xml_element(wp_elem))
        
        route = cls(
            route_name=route_name,
            waypoints=waypoints,
            route_status=route_status
        )
        
        # Parse dates if present
        if route_info_elem.get("validFrom"):
            route.valid_from = datetime.fromisoformat(route_info_elem.get("validFrom"))
        if route_info_elem.get("validTo"):
            route.valid_to = datetime.fromisoformat(route_info_elem.get("validTo"))
        
        return route
    
    def validate(self) -> Tuple[bool, List[str]]:
        """
        Validate RTZ route against IEC 61174 requirements.
        
        Returns:
            Tuple of (is_valid, list_of_errors)
        """
        errors = []
        
        # Check minimum waypoints
        if len(self.waypoints) < 2:
            errors.append("Route must have at least 2 waypoints")
        
        # Check waypoint IDs are unique
        wp_ids = [wp.id for wp in self.waypoints]
        if len(wp_ids) != len(set(wp_ids)):
            errors.append("Waypoint IDs must be unique")
        
        # Validate each waypoint
        for i, wp in enumerate(self.waypoints):
            # Check latitude bounds
            if not -90 <= wp.lat <= 90:
                errors.append(f"Waypoint {i+1}: Invalid latitude {wp.lat}")
            
            # Check longitude bounds
            if not -180 <= wp.lon <= 180:
                errors.append(f"Waypoint {i+1}: Invalid longitude {wp.lon}")
            
            # Check speed if specified
            if wp.speed and wp.speed <= 0:
                errors.append(f"Waypoint {i+1}: Speed must be positive")
            
            # Check XTE values if specified
            if wp.port_xte and wp.port_xte < 0:
                errors.append(f"Waypoint {i+1}: Port XTE must be non-negative")
            if wp.starboard_xte and wp.starboard_xte < 0:
                errors.append(f"Waypoint {i+1}: Starboard XTE must be non-negative")
        
        return len(errors) == 0, errors


class RTZConverter:
    """Converts between internal Route format and RTZ."""
    
    @staticmethod
    def route_to_rtz(route: 'Route', 
                     route_name: str = "ECDIS Planned Route",
                     vessel_speed: float = 12.0) -> RTZRoute:
        """
        Convert internal Route to RTZ format.
        
        Args:
            route: Internal route object
            route_name: Name for the RTZ route
            vessel_speed: Default vessel speed in knots
            
        Returns:
            RTZRoute object
        """
        from lib.planner.hybrid_astar import Route
        
        waypoints = []
        
        for i, (wp_pos, heading, velocity) in enumerate(zip(
            route.waypoints, 
            route.headings,
            route.velocities
        )):
            # Convert from Web Mercator to WGS84
            # TODO: Implement proper coordinate transformation
            # For now, assume waypoints are already in WGS84-compatible format
            
            # Create RTZ waypoint
            rtz_wp = RTZWaypoint(
                id=str(i + 1),
                name=f"WP{i + 1:03d}",
                lat=wp_pos[1] / 111000.0,  # Rough conversion, needs proper transform
                lon=wp_pos[0] / 111000.0,  # Rough conversion, needs proper transform
                speed=velocity * 1.94384,  # m/s to knots
                port_xte=0.1,  # Default 0.1 NM
                starboard_xte=0.1  # Default 0.1 NM
            )
            
            waypoints.append(rtz_wp)
        
        return RTZRoute(
            route_name=route_name,
            waypoints=waypoints,
            route_status="PlannedForVoyage",
            valid_from=datetime.now()
        )
    
    @staticmethod
    def rtz_to_route(rtz_route: RTZRoute) -> 'Route':
        """
        Convert RTZ route to internal Route format.
        
        Args:
            rtz_route: RTZ route object
            
        Returns:
            Internal Route object
        """
        from lib.planner.hybrid_astar import Route
        
        waypoints = []
        headings = []
        velocities = []
        
        for i, rtz_wp in enumerate(rtz_route.waypoints):
            # Convert from WGS84 to Web Mercator
            # TODO: Implement proper coordinate transformation
            x = rtz_wp.lon * 111000.0  # Rough conversion
            y = rtz_wp.lat * 111000.0  # Rough conversion
            
            waypoints.append((x, y))
            
            # Calculate heading to next waypoint
            if i < len(rtz_route.waypoints) - 1:
                next_wp = rtz_route.waypoints[i + 1]
                dx = (next_wp.lon - rtz_wp.lon) * 111000.0
                dy = (next_wp.lat - rtz_wp.lat) * 111000.0
                heading = np.arctan2(dy, dx)
            else:
                # Use previous heading for last waypoint
                heading = headings[-1] if headings else 0.0
            
            headings.append(heading)
            
            # Convert speed from knots to m/s
            speed_ms = rtz_wp.speed / 1.94384 if rtz_wp.speed else 10.0
            velocities.append(speed_ms)
        
        return Route(
            waypoints=waypoints,
            headings=headings,
            velocities=velocities
        )


def save_rtz(route: RTZRoute, filepath: Path) -> None:
    """Save RTZ route to file."""
    xml_content = route.to_xml()
    filepath.write_text(xml_content, encoding='utf-8')
    logger.info(f"RTZ route saved to {filepath}")


def load_rtz(filepath: Path) -> RTZRoute:
    """Load RTZ route from file."""
    xml_content = filepath.read_text(encoding='utf-8')
    route = RTZRoute.from_xml(xml_content)
    logger.info(f"RTZ route loaded from {filepath}")
    return route