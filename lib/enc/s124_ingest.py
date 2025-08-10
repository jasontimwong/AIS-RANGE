"""
S-124 Navigation Warnings Ingestion
Converts S-124 warnings to internal feature representations
"""

from dataclasses import dataclass
from typing import List, Optional, Dict, Any
import datetime as dt
import logging
from shapely.geometry import Polygon, shape

logger = logging.getLogger(__name__)


@dataclass
class S124Feature:
    """Internal representation of S-124 warning feature"""
    id: str
    category: str  # "speed_limit" | "prohibited"
    geometry: dict  # GeoJSON-like geometry
    time_start: dt.datetime
    time_end: dt.datetime
    speed_limit_kts: Optional[float] = None
    clause_refs: List[Dict[str, str]] = None
    
    def __post_init__(self):
        """Initialize clause references"""
        if self.clause_refs is None:
            self.clause_refs = []
            
        # Add standard clause references based on category
        if self.category == "speed_limit":
            self.clause_refs.append({
                'standard': 'S-124',
                'clause': 'Speed Restriction',
                'requirement': f'Maximum speed {self.speed_limit_kts} knots',
                'source': self.id
            })
        elif self.category == "prohibited":
            self.clause_refs.append({
                'standard': 'S-124',
                'clause': 'Prohibited Area',
                'requirement': 'Navigation prohibited',
                'source': self.id
            })
    
    def is_active(self, when: dt.datetime) -> bool:
        """Check if warning is active at given time"""
        return self.time_start <= when <= self.time_end
    
    def to_shapely(self) -> Polygon:
        """Convert geometry to Shapely polygon"""
        return shape(self.geometry)


def ingest_warnings(obj: dict) -> List[S124Feature]:
    """
    Convert S-124 JSON to internal feature list.
    
    Args:
        obj: S-124 JSON object with 'warnings' array
        
    Returns:
        List of S124Feature objects
    """
    features = []
    
    if 'warnings' not in obj:
        logger.warning("No 'warnings' field in S-124 data")
        return features
    
    for warning in obj['warnings']:
        try:
            # Parse required fields
            feature_id = warning['id']
            category = warning['category']
            geometry = warning['geometry']
            
            # Parse timestamps
            time_start = dt.datetime.fromisoformat(
                warning['time_start'].replace('Z', '+00:00')
            )
            time_end = dt.datetime.fromisoformat(
                warning['time_end'].replace('Z', '+00:00')
            )
            
            # Create feature
            feature = S124Feature(
                id=feature_id,
                category=category,
                geometry=geometry,
                time_start=time_start,
                time_end=time_end
            )
            
            # Add optional fields
            if category == "speed_limit" and 'speed_limit_kts' in warning:
                feature.speed_limit_kts = float(warning['speed_limit_kts'])
            
            features.append(feature)
            
            logger.info(f"Ingested S-124 warning: {feature_id} ({category})")
            
        except (KeyError, ValueError) as e:
            logger.error(f"Failed to parse S-124 warning: {e}")
            continue
    
    logger.info(f"Ingested {len(features)} S-124 warnings")
    return features


def apply_warnings_to_region(features: List[S124Feature], 
                            region: Any,
                            current_time: dt.datetime) -> int:
    """
    Apply S-124 warnings to feasible region.
    
    Args:
        features: List of S-124 features
        region: FeasibleRegion object to modify
        current_time: Current time for filtering active warnings
        
    Returns:
        Number of warnings applied
    """
    applied = 0
    
    for feature in features:
        # Skip inactive warnings
        if not feature.is_active(current_time):
            continue
        
        poly = feature.to_shapely()
        
        if feature.category == "prohibited":
            # Add to no-go areas
            if hasattr(region, 'add_no_go_area'):
                region.add_no_go_area(poly, source=f"S-124:{feature.id}")
                applied += 1
                logger.info(f"Added prohibited area from S-124:{feature.id}")
                
        elif feature.category == "speed_limit":
            # Add to speed restriction zones
            if hasattr(region, 'add_speed_limit'):
                region.add_speed_limit(
                    poly, 
                    speed_kts=feature.speed_limit_kts,
                    source=f"S-124:{feature.id}"
                )
                applied += 1
                logger.info(f"Added speed limit {feature.speed_limit_kts}kts from S-124:{feature.id}")
    
    return applied


def generate_warning_report(features: List[S124Feature], 
                           current_time: dt.datetime) -> Dict[str, Any]:
    """
    Generate summary report of S-124 warnings.
    
    Args:
        features: List of S-124 features
        current_time: Current time for status
        
    Returns:
        Report dictionary
    """
    active = [f for f in features if f.is_active(current_time)]
    
    report = {
        'total_warnings': len(features),
        'active_warnings': len(active),
        'categories': {},
        'clause_refs': []
    }
    
    # Count by category
    for feature in active:
        cat = feature.category
        report['categories'][cat] = report['categories'].get(cat, 0) + 1
        report['clause_refs'].extend(feature.clause_refs)
    
    return report