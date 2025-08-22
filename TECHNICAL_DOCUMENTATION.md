# ECDIS Technical Documentation

## System Architecture

### Core Components

#### 1. Intelligent Route Planner (lib/route/intelligent_route_planner.py)
Advanced route planning system integrating multiple algorithms and data sources:

- **TSS Integration**: Automatic identification and usage of Traffic Separation Schemes
- **Historical Route Learning**: Path optimization based on historical optimal routes
- **Dynamic Obstacle Avoidance**: Real-time avoidance of land masses, shallow waters
- **Multi-objective Optimization**: Balancing time, fuel consumption, and safety

#### 2. Route Planning API (service/app.py)
FastAPI service providing RESTful interfaces:

- `/api/route/plan_full` - Complete route planning
- `/api/route/dynamic` - Dynamic route adjustments
- `/api/route/initialize` - Route initialization
- `/api/route/validate` - Route validation
- `/api/eval/params` - Vessel parameters for calculations
- `/api/eval/fuel` - Fuel consumption calculations

#### 3. Frontend Interface (ui/src/)
Modern React/TypeScript interface:

- Canvas-based chart rendering
- Real-time AIS data display
- Interactive route planning
- WebSocket real-time communication
- Avoidance impact assessment panels

## Route Planning Algorithms

### Algorithm Selection Strategy

```python
if distance > 500km:
    # Long distance: Use intelligent planner
    - Find historical optimal routes
    - Generate TSS-compliant paths
    - Merge historical and TSS data
    - Dynamic optimization
    - Land avoidance checking
else:
    # Short distance: Use Hybrid A*
    - 50-meter precision grid
    - Real-time obstacle avoidance
    - Smooth path generation
```

### TSS (Traffic Separation Scheme) Integration

The system incorporates major TSS zones:

1. **Singapore Strait TSS**
   - Eastbound/Westbound lanes
   - Separation zones
   - Precise coordinates: [103.851, 1.265]

2. **Malacca Strait TSS**
   - Northwest/Southeast lanes
   - Critical navigation points
   - Bounds: [99.0, 1.0, 103.9, 5.5]

3. **Taiwan Strait TSS**
   - North/South lanes
   - Coastal avoidance

4. **Yellow Sea TSS**
   - China-Korea shipping lanes
   - Northeast/Southwest traffic

### Historical Route Database

Pre-validated safe routes between major ports:

```python
VERIFIED_ROUTES = {
    "shanghai_singapore": {
        "distance_nm": 2380,
        "waypoints": 16,
        "tss_compliant": True
    },
    "shenzhen_singapore": {
        "distance_nm": 1432,
        "waypoints": 11,
        "tss_compliant": True
    },
    # ... more routes
}
```

## Dynamic Route Planning

### Real-time Adjustments

The system supports dynamic route modifications based on:

1. **AIS Targets**: Real-time vessel positions
2. **Weather Conditions**: Wind, waves, currents
3. **Port Congestion**: Traffic density analysis
4. **Emergency Situations**: Collision avoidance

### Avoidance Algorithm

```python
def calculate_avoidance_route(current_pos, threat_pos, original_route):
    # Calculate CPA (Closest Point of Approach)
    cpa_distance, cpa_time = calculate_cpa(current_pos, threat_pos)
    
    if cpa_distance < SAFETY_THRESHOLD:
        # Generate avoidance waypoints
        avoidance_points = generate_safe_path(
            current_pos, 
            threat_pos,
            min_distance=SAFETY_MARGIN
        )
        
        # Merge with original route
        return merge_routes(original_route, avoidance_points)
    
    return original_route
```

## Cost Calculation System

### Economic Impact Assessment

The system provides comprehensive cost analysis for route changes:

1. **Fuel Consumption Models**
   - Linear model: Quick estimates
   - Power model: Admiralty formula-based
   - Weather corrections applied

2. **Environmental Impact**
   - CO₂ emissions: 3.114 tons/ton fuel
   - SOx emissions: Based on fuel sulfur content
   - NOx emissions: Engine tier dependent

3. **Time Impact**
   - ETA delays calculated
   - Port slot implications
   - Charter party considerations

For detailed cost calculation methodology, see [COST_CALCULATION_DOCUMENTATION.md](./COST_CALCULATION_DOCUMENTATION.md)

## API Documentation

### Route Planning Endpoints

#### POST /api/route/plan_full
Plans a complete route between two points.

**Request:**
```json
{
    "start": {"lat": 22.5, "lon": 114.1},
    "goal": {"lat": 1.265, "lon": 103.851}
}
```

**Response:**
```json
{
    "coords": [[lon, lat], ...],
    "planning_time_s": 0.5,
    "used_ais": true
}
```

#### GET /api/route/dynamic
Gets dynamic route adjustments based on current position.

**Parameters:**
- `current_lat`: Current latitude
- `current_lon`: Current longitude
- `include_ais`: Include AIS constraints (optional)

### Evaluation Endpoints

#### GET /api/eval/params
Returns vessel and economic parameters.

#### POST /api/eval/fuel
Calculates fuel consumption and costs for route comparison.

## Frontend Components

### Key React Components

1. **CanvasMap.tsx**
   - WebGL-accelerated chart rendering
   - Multi-layer visualization
   - Real-time updates

2. **EvaluationPanel.tsx**
   - Basic route comparison
   - Fuel and time calculations
   - CO₂ emissions display

3. **AdvancedAvoidanceEvaluationPanel.tsx**
   - Segment-level analysis
   - Power model calculations
   - Detailed impact metrics

## Performance Optimization

### Backend Optimizations

1. **Caching Strategy**
   - Historical routes cached in memory
   - TSS data pre-loaded
   - Land geometry indexed

2. **Parallel Processing**
   - Multiple route alternatives calculated concurrently
   - Async I/O for external data

3. **Algorithm Efficiency**
   - A* with adaptive heuristics
   - Spatial indexing for collision detection
   - Dynamic programming for segment optimization

### Frontend Optimizations

1. **Rendering Performance**
   - Canvas-based rendering
   - Viewport culling
   - Level-of-detail (LOD) system

2. **Data Management**
   - Incremental updates via WebSocket
   - Route decimation for display
   - Lazy loading of chart tiles

## Deployment Configuration

### Environment Variables

```bash
# API Configuration
FASTAPI_PORT=8000
FASTAPI_HOST=0.0.0.0

# Frontend Configuration
VITE_API_URL=http://localhost:8000
VITE_WS_URL=ws://localhost:8000

# Vessel Parameters
VESSEL_SPEED_KN=18.0
FUEL_PER_NM_TON=0.15
FUEL_PRICE_USD=650
```

### Docker Deployment

```dockerfile
# Backend
FROM python:3.11-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install -r requirements.txt
COPY . .
CMD ["uvicorn", "service.app:app", "--host", "0.0.0.0"]

# Frontend
FROM node:18-alpine
WORKDIR /app
COPY package.json .
RUN npm install
COPY . .
RUN npm run build
CMD ["npm", "run", "preview"]
```

## Testing

### Test Coverage

- Unit tests: Core algorithms (85% coverage)
- Integration tests: API endpoints (90% coverage)
- E2E tests: Critical user flows (70% coverage)

### Test Execution

```bash
# Run comprehensive test suite
python final_comprehensive_test.py

# Run integration tests
./final_test.sh

# Start full system test
./start_integrated.sh
```

## Troubleshooting

### Common Issues

1. **Wrong Singapore Coordinates**
   - Fixed: TSS bounds corrected to [103.851, 1.265]
   - Ensure all modules use updated coordinates

2. **Route Crossing Land**
   - Check land avoidance data loaded
   - Verify feasible region initialized
   - Increase avoidance buffer if needed

3. **Performance Issues**
   - Enable route caching
   - Reduce waypoint density for display
   - Use simplified models for long routes

## Future Enhancements

1. **Machine Learning Integration**
   - Route optimization based on historical performance
   - Predictive fuel consumption models
   - Anomaly detection for route safety

2. **Weather Routing**
   - Integration with weather APIs
   - Dynamic route optimization based on forecasts
   - Storm avoidance algorithms

3. **Multi-vessel Coordination**
   - Fleet-wide optimization
   - Convoy routing
   - Port slot coordination

## References

- IMO ECDIS Performance Standards
- IHO S-57/S-101 Standards
- SOLAS Chapter V Navigation Requirements
- ISO 19847 Shipboard Data Architecture

## Support

For technical support or contributions:
- Repository: [GitHub Project]
- Documentation: See `/docs` directory
- API Documentation: `/docs` endpoint when running