#!/usr/bin/env python3
import json

# Define Asia-Pacific bounding box
# Longitude: 60E to 180E
# Latitude: -50S to 60N
MIN_LON = 60
MAX_LON = 180
MIN_LAT = -50
MAX_LAT = 60

def is_in_bounds(coords):
    """Check if any coordinate is within Asia-Pacific bounds"""
    if isinstance(coords[0], (list, tuple)):
        # Recursive check for nested coordinates
        return any(is_in_bounds(c) for c in coords)
    else:
        # Check single coordinate pair
        lon, lat = coords[0], coords[1]
        return MIN_LON <= lon <= MAX_LON and MIN_LAT <= lat <= MAX_LAT

def filter_geometry(geometry):
    """Filter geometry to only include Asia-Pacific region"""
    geom_type = geometry['type']
    
    if geom_type == 'Polygon':
        # Check if polygon is in bounds
        if any(is_in_bounds(ring) for ring in geometry['coordinates']):
            return geometry
        return None
    
    elif geom_type == 'MultiPolygon':
        # Filter polygons that are in bounds
        filtered_coords = []
        for polygon in geometry['coordinates']:
            if any(is_in_bounds(ring) for ring in polygon):
                filtered_coords.append(polygon)
        
        if filtered_coords:
            geometry['coordinates'] = filtered_coords
            return geometry
        return None
    
    return geometry

# Load the simplified world data
with open('world-land-simplified.json', 'r') as f:
    data = json.load(f)

# Filter features for Asia-Pacific region
filtered_features = []
for feature in data['features']:
    if 'geometry' in feature and feature['geometry']:
        filtered_geom = filter_geometry(feature['geometry'])
        if filtered_geom:
            feature['geometry'] = filtered_geom
            filtered_features.append(feature)

# Create new GeoJSON with filtered features
asia_pacific_data = {
    'type': 'FeatureCollection',
    'features': filtered_features
}

# Save the Asia-Pacific data
with open('asia-pacific-land.json', 'w') as f:
    json.dump(asia_pacific_data, f, separators=(',', ':'))

print(f"Original features: {len(data['features'])}")
print(f"Asia-Pacific features: {len(filtered_features)}")
print("Created: asia-pacific-land.json")