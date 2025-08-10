# ECDIS Planner

Standards-compliant maritime route planning system implementing IMO MSC.232(82) and IEC 61174:2015 specifications.

## Features

- **S-57 ENC Support**: Parse and process electronic navigational charts
- **Hybrid A* Planning**: Kinematically-feasible path planning with continuous state space
- **Safety Validation**: Comprehensive route validation against safety constraints
- **TSS Compliance**: Traffic Separation Scheme compliance checking
- **RTZ Export/Import**: IEC 61174 Annex S compliant route exchange format
- **REST API**: FastAPI-based service for integration

## Architecture

```
lib/
├── enc/          # S-57 ENC reading and processing
├── region/       # Feasible region and TSS handling
├── planner/      # Hybrid A* path planning
├── checks/       # Route validation and compliance
├── io/           # RTZ format I/O
├── costs/        # Cost field generation
├── traffic/      # CPA/TCPA calculations
├── speed/        # Speed profile generation
└── kinematics/   # Curvature and XTD constraints

service/
└── app.py        # FastAPI REST service

tests/            # Pytest test suites
scripts/          # Scenario runners
scenarios/        # Test scenarios (SF TSS)
```

## Installation

```bash
# Install dependencies
pip install -r requirements.txt

# Install GDAL (platform-specific)
# macOS: brew install gdal
# Ubuntu: apt-get install gdal-bin python3-gdal
```

## Quick Start

### 1. Start the API Service

```bash
cd service
uvicorn app:app --reload
```

### 2. Plan a Route

```bash
curl -X POST http://localhost:8000/plan \
  -H "Content-Type: application/json" \
  -d '{
    "start": {"lat": 37.70, "lon": -123.10},
    "goal": {"lat": 37.80, "lon": -122.55},
    "vessel_draft": 8.0,
    "safety_depth": 15.0
  }'
```

### 3. Validate Route

```bash
curl -X POST http://localhost:8000/validate \
  -H "Content-Type: application/json" \
  -d '{
    "route_id": "route_20240101_120000",
    "checks": ["safety", "tss", "geometry", "speed"]
  }'
```

### 4. Export RTZ

```bash
curl http://localhost:8000/export/rtz?route_id=route_20240101_120000 \
  -o route.rtz
```

## Run San Francisco TSS Scenario

```bash
./scripts/run_scenario_sf.sh
```

This will:
1. Load NOAA ENC data (US5CA12M)
2. Plan route through SF Traffic Separation Scheme
3. Validate against all safety constraints
4. Generate RTZ file and validation report
5. Test RTZ round-trip import/export

## API Documentation

Interactive API docs available at: http://localhost:8000/docs

Key endpoints:
- `POST /plan` - Plan optimal route
- `POST /validate` - Validate route safety
- `GET /export/rtz` - Export route as RTZ
- `POST /import/rtz` - Import RTZ file
- `GET /status` - Service status

## Testing

```bash
# Run all tests
pytest

# Run specific test suite
pytest tests/test_hybrid_astar_grid.py -v

# Run with coverage
pytest --cov=lib --cov-report=html
```

## Standards Compliance

- **IMO MSC.232(82)**: ECDIS performance standards
- **IMO MSC.530(106)/Rev.1**: Revised ECDIS standards
- **IEC 61174:2015 Ed.4**: ECDIS operational requirements
- **IEC 61174 Annex S**: RTZ route exchange format
- **IHO S-57**: ENC data standard
- **IHO S-64/S-164**: Test datasets

## Configuration

See `config/cost_defaults.yaml` for planner configuration:
- Safety parameters (depth, UKC, XTD)
- Cost weights (distance, safety, curvature)
- Vessel characteristics
- Planning constraints

## Performance

- Route planning: < 2 seconds (typical)
- Re-planning: < 0.5 seconds
- Validation: < 100ms
- RTZ export: < 50ms
- Concurrent requests: 50+ QPS

## License

MIT License - See LICENSE file for details

## Citation

```bibtex
@software{ecdis_planner,
  title = {ECDIS Planner: Standards-Compliant Maritime Route Planning},
  year = {2024},
  version = {1.0.0}
}
```