# Maritime Route Cost Calculation System - Technical Documentation

## Executive Summary

The Maritime Route Cost Calculation System provides real-time economic and environmental impact assessment for route planning and dynamic avoidance maneuvers. It calculates fuel consumption, operational costs, and CO₂ emissions using both simplified linear models and advanced power-based models, enabling data-driven decision making for vessel operations.

## Table of Contents

1. [System Architecture](#system-architecture)
2. [Calculation Models](#calculation-models)
3. [API Endpoints](#api-endpoints)
4. [Frontend Components](#frontend-components)
5. [Implementation Details](#implementation-details)
6. [Usage Examples](#usage-examples)
7. [Configuration Parameters](#configuration-parameters)

---

## System Architecture

### Component Overview

```
┌─────────────────────────────────────────────────────────────┐
│                      Frontend (React/TypeScript)             │
├─────────────────────────────────────────────────────────────┤
│  EvaluationPanel.tsx    │  AdvancedAvoidanceEvaluationPanel │
│  (Basic Assessment)     │  (Segment-level Analysis)         │
└─────────────────┬───────────────────┬──────────────────────┘
                  │                   │
                  ▼                   ▼
┌─────────────────────────────────────────────────────────────┐
│                    Backend API (FastAPI)                     │
├─────────────────────────────────────────────────────────────┤
│  /api/eval/params       │  /api/eval/fuel                   │
│  (Get Parameters)       │  (Calculate Fuel Impact)          │
└─────────────────┬───────────────────┬──────────────────────┘
                  │                   │
                  ▼                   ▼
┌─────────────────────────────────────────────────────────────┐
│               Core Calculation Engine                        │
├─────────────────────────────────────────────────────────────┤
│  Linear Model           │  Power Model (Admiralty Formula)  │
│  (Simple, Fast)         │  (Accurate, Physics-based)       │
└─────────────────────────────────────────────────────────────┘
```

## Calculation Models

### 1. Linear Model (Simple)

The linear model provides quick estimations based on direct proportional relationships:

#### Distance Calculation
```javascript
distance_nm = haversine(lat1, lon1, lat2, lon2) / 1852.0
```

Where haversine implements the great circle distance formula:
```javascript
function haversine(lat1, lon1, lat2, lon2) {
    const R = 6371000; // Earth radius in meters
    const dLat = toRadians(lat2 - lat1);
    const dLon = toRadians(lon2 - lon1);
    const a = sin(dLat/2)² + cos(lat1) * cos(lat2) * sin(dLon/2)²;
    const c = 2 * atan2(√a, √(1-a));
    return R * c; // Distance in meters
}
```

#### Fuel Consumption
```
fuel_consumption (tons) = distance_nm × fuel_per_nm_ton
```

Default: `fuel_per_nm_ton = 0.15` (typical for container vessels at cruise speed)

#### Time Impact
```
time_hours = distance_nm / vessel_speed_kn
```

Default: `vessel_speed_kn = 18.0` knots

#### Cost Calculation
```
fuel_cost_usd = fuel_consumption × fuel_price_usd_per_ton
```

Default: `fuel_price_usd_per_ton = 650` USD/ton (VLSFO price)

#### CO₂ Emissions
```
co2_emissions_tons = fuel_consumption × co2_per_ton_fuel
```

Default: `co2_per_ton_fuel = 3.114` (standard emission factor for marine fuel)

### 2. Power Model (Admiralty Formula)

The power model uses naval architecture principles for accurate fuel consumption:

#### Admiralty Coefficient Method
```
Power_required = (Displacement^(2/3) × Speed³) / Admiralty_Coefficient
```

Where:
- **Displacement**: Vessel displacement in tons (e.g., 45,000 tons for container ship)
- **Speed**: Vessel speed in knots
- **Admiralty Coefficient**: Vessel efficiency factor (typically 400-600)

#### Fuel Consumption Rate
```
fuel_rate_kg_hour = Power_kW × SFOC / 1000
```

Where:
- **SFOC** (Specific Fuel Oil Consumption): 170 g/kWh for modern engines
- **Power_kW**: Required power in kilowatts

#### Weather and Sea State Corrections

**Wave Resistance Addition:**
```
additional_power = base_power × (1 + 0.05 × wave_height_m)
```

**Wind Resistance:**
```
wind_force = 0.5 × air_density × wind_speed² × frontal_area × drag_coefficient
additional_power_wind = wind_force × vessel_speed / efficiency
```

**Current Effect:**
```
effective_speed = vessel_speed ± current_speed × cos(current_angle)
```

### 3. Segment-Level Analysis

For dynamic route adjustments, the system performs segment-level comparisons:

#### Segment Identification
1. Find nearest points on original route to dynamic route start/end
2. Extract corresponding segment from original route
3. Compare segment lengths

```javascript
function findNearestSegment(originalRoute, dynamicRoute) {
    const startIdx = findNearestPoint(originalRoute, dynamicRoute[0]);
    const endIdx = findNearestPoint(originalRoute, dynamicRoute[length-1]);
    return originalRoute.slice(min(startIdx, endIdx), max(startIdx, endIdx));
}
```

#### Delta Calculations
```
Δdistance = dynamic_segment_distance - original_segment_distance
Δtime = Δdistance / vessel_speed
Δfuel = Δdistance × fuel_per_nm
Δcost = Δfuel × fuel_price
ΔCO₂ = Δfuel × co2_factor
```

## API Endpoints

### GET /api/eval/params

Returns vessel and economic parameters for calculations.

**Response:**
```json
{
    "vessel_speed_kn": 18.0,
    "fuel_per_nm_ton": 0.15,
    "fuel_price_usd_per_ton": 650,
    "co2_per_ton_fuel": 3.114,
    "vessel_displacement_ton": 45000,
    "admiralty_coefficient": 500,
    "sfoc_g_kwh": 170
}
```

### POST /api/eval/fuel

Calculates fuel consumption and environmental impact.

**Request:**
```json
{
    "original_route": [{"lat": 22.5, "lon": 114.1}, ...],
    "dynamic_route": [{"lat": 22.5, "lon": 114.1}, ...],
    "model": "power",  // or "linear"
    "vessel_speed_kn": 18.0,
    "weather_conditions": {
        "wave_height_m": 2.5,
        "wind_speed_mps": 10,
        "wind_direction_deg": 45,
        "current_speed_kn": 2,
        "current_direction_deg": 90
    }
}
```

**Response:**
```json
{
    "success": true,
    "original_distance_nm": 1432.5,
    "dynamic_distance_nm": 1445.2,
    "delta_distance_nm": 12.7,
    "delta_time_hours": 0.71,
    "delta_fuel_ton": 1.91,
    "delta_cost_usd": 1241.5,
    "delta_co2_ton": 5.95,
    "confidence": 0.95,
    "model_used": "power"
}
```

## Frontend Components

### EvaluationPanel.tsx

Basic evaluation panel for quick assessments:

```typescript
interface Metrics {
    originalNm: number;      // Original route distance
    dynamicNm: number;       // Dynamic route distance
    deltaNm: number;         // Distance increase
    deltaHours: number;      // Time delay
    deltaFuelTon: number;    // Extra fuel consumption
    deltaFuelCostUSD: number;// Additional cost
    deltaCO2Ton: number;     // Extra emissions
}
```

### AdvancedAvoidanceEvaluationPanel.tsx

Advanced panel with segment-level analysis and power model support:

```typescript
interface AdvancedMetrics {
    segment: {
        startIndex: number;
        endIndex: number;
    };
    delta_distance_nm: number;
    delta_time_hours: number;
    delta_fuel_ton: number;
    delta_cost_usd: number;
    delta_co2_ton: number;
    original_distance_nm: number;
    dynamic_distance_nm: number;
}
```

## Implementation Details

### Distance Calculation Precision

The system uses the WGS84 ellipsoid model for accurate distance calculations:

```python
def calculate_distance_nm(lat1, lon1, lat2, lon2):
    """Calculate distance using Vincenty's formula for ellipsoidal earth"""
    from geopy.distance import distance
    
    point1 = (lat1, lon1)
    point2 = (lat2, lon2)
    
    # Returns distance in nautical miles
    return distance(point1, point2).nm
```

### Fuel Consumption Factors

Fuel consumption varies with:

1. **Speed (Cubic Relationship)**
   - Doubling speed increases fuel consumption by ~8x
   - Optimal speed typically 60-70% of maximum

2. **Vessel Loading**
   - Full load: +10-15% fuel consumption
   - Ballast: -5-10% fuel consumption

3. **Hull Fouling**
   - Clean hull: Baseline
   - 6 months fouling: +10-15%
   - 2 years fouling: +40%

4. **Weather Impact**
   - Calm seas: Baseline
   - Moderate seas (3-4m waves): +15-25%
   - Rough seas (5-6m waves): +30-50%

### Environmental Calculations

#### CO₂ Emissions
```
CO₂ (tons) = Fuel (tons) × 3.114
```

#### SOx Emissions (for VLSFO 0.5% sulfur)
```
SOx (kg) = Fuel (tons) × 10
```

#### NOx Emissions (Tier II engines)
```
NOx (kg) = Fuel (tons) × 50
```

## Usage Examples

### Example 1: Basic Route Comparison

```javascript
// Calculate impact of 10nm detour
const originalDistance = 1000; // nm
const dynamicDistance = 1010; // nm
const deltaDistance = 10; // nm

const metrics = {
    deltaTime: 10 / 18,        // 0.56 hours
    deltaFuel: 10 * 0.15,      // 1.5 tons
    deltaCost: 1.5 * 650,      // $975
    deltaCO2: 1.5 * 3.114      // 4.67 tons CO₂
};
```

### Example 2: Avoidance Maneuver Assessment

```python
# Python backend calculation
def assess_avoidance_impact(original_route, avoidance_route):
    # Extract affected segment
    segment_start = find_deviation_point(original_route, avoidance_route)
    segment_end = find_convergence_point(original_route, avoidance_route)
    
    # Calculate distances
    original_distance = calculate_segment_distance(
        original_route[segment_start:segment_end]
    )
    avoidance_distance = calculate_route_distance(avoidance_route)
    
    # Economic impact
    delta_nm = avoidance_distance - original_distance
    delta_fuel = delta_nm * FUEL_PER_NM
    delta_cost = delta_fuel * FUEL_PRICE
    delta_co2 = delta_fuel * CO2_FACTOR
    
    return {
        'distance_penalty_nm': delta_nm,
        'time_penalty_hours': delta_nm / VESSEL_SPEED,
        'fuel_penalty_tons': delta_fuel,
        'cost_penalty_usd': delta_cost,
        'co2_penalty_tons': delta_co2,
        'segment_affected': f"WP{segment_start} to WP{segment_end}"
    }
```

## Configuration Parameters

### Default Vessel Parameters

```yaml
vessel:
  type: "Container Ship"
  length_m: 289
  beam_m: 32.2
  draft_m: 12.5
  displacement_ton: 45000
  speed_service_kn: 18.0
  speed_max_kn: 24.0
  
engine:
  type: "MAN B&W 7S80ME-C"
  power_mcr_kw: 27060
  sfoc_g_kwh: 170
  fuel_type: "VLSFO"
  
economics:
  fuel_price_usd_ton: 650
  charter_rate_usd_day: 25000
  port_charge_usd: 50000
  
emissions:
  co2_factor: 3.114
  sox_factor: 0.01  # for 0.5% sulfur
  nox_factor: 0.05  # kg/ton fuel
```

### Adjustment Factors

```yaml
corrections:
  weather:
    calm: 1.0
    moderate: 1.15
    rough: 1.35
    severe: 1.60
    
  loading:
    ballast: 0.92
    partial: 0.96
    full: 1.05
    
  hull_condition:
    clean: 1.0
    light_fouling: 1.08
    moderate_fouling: 1.18
    heavy_fouling: 1.35
```

## Best Practices

1. **Model Selection**
   - Use linear model for quick estimates (<1% of route length changes)
   - Use power model for significant deviations (>5% change)
   - Always use power model for weather routing

2. **Segment Analysis**
   - Compare only affected segments, not entire routes
   - Account for convergence/divergence points accurately
   - Consider cumulative effects of multiple avoidance maneuvers

3. **Validation**
   - Cross-check calculations with historical fuel consumption data
   - Validate against noon reports for similar voyages
   - Consider seasonal variations in fuel consumption

4. **Reporting**
   - Always include confidence intervals
   - Document assumptions clearly
   - Provide both optimistic and pessimistic scenarios

## Conclusion

The Maritime Route Cost Calculation System provides comprehensive economic and environmental impact assessment for route planning decisions. By combining simplified linear models for quick estimates with sophisticated power-based calculations for detailed analysis, the system enables operators to make informed decisions balancing safety, economics, and environmental responsibility.

For technical support or feature requests, please contact the development team or refer to the main technical documentation.