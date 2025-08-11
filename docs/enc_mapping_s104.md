# S-104 Water Level Information Mapping

## Overview
S-104 provides time-varying water level information including tides, storm surges, and other water level variations. This adapter enables 4D (space-time) route planning with dynamic UKC calculations.

## Data Model

### Tide Stations
Point-based time series data from tide gauges:
- **Position**: Geographic coordinates (lon, lat)
- **Datum**: Reference level (MSL, LAT, etc.)
- **Time Series**: Water level measurements over time
- **Interpolation**: Linear interpolation between measurements

### Gridded Data
Spatially continuous water level fields:
- **Grid**: Regular lat/lon grid
- **Time Steps**: Discrete time snapshots
- **Interpolation**: Bilinear in space, linear in time

## API Usage

### Basic Water Level Query
```python
from lib.enc.s104_adapter import S104Adapter

adapter = S104Adapter()
adapter.load_station_data("datasets/s104/station001.csv")

# Get water level at specific time and location
water_level = adapter.get_water_level_at_point(
    lon=-122.4,
    lat=37.8, 
    query_time=datetime(2025, 1, 1, 6, 0),
    method='nearest_station'
)
```

### Tide Window Analysis
```python
# Find favorable tide windows
windows = adapter.get_tide_windows(
    position=(-122.4, 37.8),
    start_time=datetime(2025, 1, 1),
    duration_hours=24,
    threshold=2.0  # Minimum water level needed
)

for start, end in windows:
    print(f"High tide window: {start} to {end}")
```

### Tide Curve Generation
```python
# Generate tide curve for visualization
curve = adapter.generate_tide_curve(
    position=(-122.4, 37.8),
    start_time=datetime(2025, 1, 1),
    duration_hours=24,
    sample_minutes=10
)

# Plot tide curve
import matplotlib.pyplot as plt
plt.plot(curve['time'], curve['water_level'])
plt.xlabel('Time')
plt.ylabel('Water Level (m)')
plt.title('Tide Curve')
```

## Integration with UKC

The S-104 adapter provides real-time water level corrections for UKC calculations:

```python
# Dynamic UKC with tide correction
ukc = depth - draft + water_level - wave_heave

# Where water_level comes from S-104:
water_level = adapter.get_water_level_at_point(lon, lat, time)
```

## Data Formats

### Station CSV Format
```csv
station_id,name,lon,lat,datum
STATION001,Harbor,-122.4,37.8,MSL
2025-01-01T00:00:00,0.0
2025-01-01T06:00:00,2.5
2025-01-01T12:00:00,0.5
```

### Grid CSV Format (Simplified)
```csv
time,min_lon,min_lat,max_lon,max_lat,nx,ny
2025-01-01T00:00:00,-123.0,37.0,-122.0,38.0,3,3,<grid_values>
```

## Methods

### Interpolation Methods
1. **nearest_station**: Use nearest tide gauge data
2. **grid**: Use gridded water level field
3. **interpolate**: Inverse distance weighting from multiple stations

### Extrapolation Policy
- **Before data range**: Use first available value
- **After data range**: Use last available value
- **Spatial**: Nearest neighbor or IDW

## Performance Considerations

- Station queries: O(1) for single station, O(n) for nearest search
- Grid queries: O(1) with bilinear interpolation
- Tide window search: O(n) where n = duration / sample_interval
- Memory: Proportional to grid size × time steps

## Standards Compliance

- **S-104 v1.0**: IHO Water Level Information Product Specification
- **Datum**: Supports multiple vertical datums (MSL, LAT, HAT, etc.)
- **Time**: ISO 8601 format with timezone support

## Error Handling

- Missing data: Returns 0.0 or datum level
- Out of bounds: Extrapolates using nearest values
- Invalid times: Logs warning and uses boundary values