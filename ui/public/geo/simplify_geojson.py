#!/usr/bin/env python3
import json
import math

def simplify_coords(coords, tolerance=0.01):
    """Douglas-Peucker algorithm for simplifying coordinates"""
    if len(coords) <= 2:
        return coords
    
    # Find the point with the maximum distance
    dmax = 0
    index = 0
    end = len(coords) - 1
    
    for i in range(1, end):
        d = perpendicular_distance(coords[i], coords[0], coords[end])
        if d > dmax:
            index = i
            dmax = d
    
    # If max distance is greater than tolerance, recursively simplify
    if dmax > tolerance:
        # Recursive call
        rec_results1 = simplify_coords(coords[:index+1], tolerance)
        rec_results2 = simplify_coords(coords[index:], tolerance)
        
        # Build the result list
        result = rec_results1[:-1] + rec_results2
    else:
        result = [coords[0], coords[end]]
    
    return result

def perpendicular_distance(point, line_start, line_end):
    """Calculate perpendicular distance from point to line"""
    x0, y0 = point
    x1, y1 = line_start
    x2, y2 = line_end
    
    numerator = abs((y2-y1)*x0 - (x2-x1)*y0 + x2*y1 - y2*x1)
    denominator = math.sqrt((y2-y1)**2 + (x2-x1)**2)
    
    if denominator == 0:
        return math.sqrt((x0-x1)**2 + (y0-y1)**2)
    
    return numerator / denominator

def round_coords(coords, precision=4):
    """Round coordinates to specified decimal places"""
    if isinstance(coords[0], (list, tuple)):
        return [round_coords(c, precision) for c in coords]
    else:
        return [round(c, precision) for c in coords]

def process_geometry(geometry, tolerance=0.01, precision=4):
    """Process geometry by simplifying and rounding coordinates"""
    geom_type = geometry['type']
    
    if geom_type == 'Polygon':
        coords = geometry['coordinates']
        new_coords = []
        for ring in coords:
            simplified = simplify_coords(ring, tolerance)
            rounded = round_coords(simplified, precision)
            if len(rounded) >= 4:  # Valid polygon needs at least 4 points
                new_coords.append(rounded)
        geometry['coordinates'] = new_coords
    
    elif geom_type == 'MultiPolygon':
        coords = geometry['coordinates']
        new_coords = []
        for polygon in coords:
            new_polygon = []
            for ring in polygon:
                simplified = simplify_coords(ring, tolerance)
                rounded = round_coords(simplified, precision)
                if len(rounded) >= 4:
                    new_polygon.append(rounded)
            if new_polygon:
                new_coords.append(new_polygon)
        geometry['coordinates'] = new_coords
    
    return geometry

# Load the GeoJSON file
with open('ne_50m_land.json', 'r') as f:
    data = json.load(f)

# Process each feature
for feature in data['features']:
    if 'geometry' in feature and feature['geometry']:
        feature['geometry'] = process_geometry(
            feature['geometry'], 
            tolerance=0.005,  # Adjust for desired simplification
            precision=3       # 3 decimal places is enough for most uses
        )

# Save the simplified GeoJSON
with open('world-land-simplified.json', 'w') as f:
    json.dump(data, f, separators=(',', ':'))

print(f"Original file: ne_50m_land.json")
print(f"Simplified file: world-land-simplified.json")
print(f"Features: {len(data['features'])}")