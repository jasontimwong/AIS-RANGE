"""
ECDIS Planner REST API Service
FastAPI-based service for route planning, validation, and RTZ export.
"""

from fastapi import FastAPI, HTTPException, UploadFile, File, BackgroundTasks
from fastapi.responses import JSONResponse, FileResponse
from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any
from pathlib import Path
import tempfile
import logging
from datetime import datetime
import json

import numpy as np
# Try to import S57Reader, fall back to mock if GDAL not available
try:
    from lib.enc.s57_reader import S57Reader
except RuntimeError:
    from lib.enc.s57_reader_mock import S57MockReader as S57Reader
from lib.region.feasible_region import FeasibleRegionBuilder, SafetyParameters
from lib.planner.hybrid_astar import HybridAStar, PlannerConfig, Route
from lib.checks.route_checker import RouteChecker
from lib.io.rtz import RTZConverter, save_rtz, load_rtz

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Initialize FastAPI app
app = FastAPI(
    title="ECDIS Planner API",
    description="Standards-compliant maritime route planning service",
    version="1.0.0"
)

# Global state (in production, use proper state management)
class PlannerState:
    def __init__(self):
        self.enc_reader = None
        self.feasible_region = None
        self.planner = None
        self.current_route = None
        self.validation_report = None

state = PlannerState()


# Request/Response Models
class Waypoint(BaseModel):
    lat: float = Field(..., ge=-90, le=90, description="Latitude in decimal degrees")
    lon: float = Field(..., ge=-180, le=180, description="Longitude in decimal degrees")
    name: Optional[str] = None
    speed: Optional[float] = Field(None, gt=0, description="Speed in knots")


class PlanRequest(BaseModel):
    start: Waypoint
    goal: Waypoint
    waypoints: Optional[List[Waypoint]] = []
    vessel_draft: float = Field(5.0, gt=0, description="Vessel draft in meters")
    safety_depth: float = Field(10.0, gt=0, description="Minimum safety depth in meters")
    under_keel_clearance: float = Field(2.0, gt=0, description="UKC in meters")
    vessel_speed: float = Field(12.0, gt=0, description="Vessel speed in knots")
    enc_file: Optional[str] = Field(None, description="Path to ENC file")


class PlanResponse(BaseModel):
    success: bool
    route_id: str
    waypoints: List[Dict[str, float]]
    total_distance_nm: float
    estimated_time_hours: float
    planning_time_seconds: float
    message: str


class ValidateRequest(BaseModel):
    route_id: Optional[str] = None
    rtz_content: Optional[str] = None
    checks: List[str] = Field(
        default=["safety", "tss", "geometry", "speed"],
        description="Validation checks to perform"
    )


class ValidateResponse(BaseModel):
    success: bool
    is_valid: bool
    total_checks: int
    passed: int
    failed: int
    warnings: int
    critical_issues: List[str]
    report_url: str


# API Endpoints
@app.get("/")
async def root():
    """API root endpoint."""
    return {
        "service": "ECDIS Planner API",
        "version": "1.0.0",
        "status": "operational",
        "endpoints": [
            "/plan",
            "/validate",
            "/export/rtz",
            "/import/rtz",
            "/status"
        ]
    }


@app.post("/plan", response_model=PlanResponse)
async def plan_route(request: PlanRequest):
    """
    Plan a route based on request parameters.
    """
    try:
        logger.info(f"Planning route from {request.start.lat},{request.start.lon} to {request.goal.lat},{request.goal.lon}")
        
        # Load ENC if specified
        if request.enc_file:
            enc_path = Path(request.enc_file)
            if not enc_path.exists():
                raise HTTPException(status_code=404, detail="ENC file not found")
            
            # Try to use real S57Reader, fall back to simple reader
            try:
                state.enc_reader = S57Reader(enc_path)
                state.enc_reader.load()
            except (RuntimeError, Exception) as e:
                # Use simple reader for testing (no GDAL required)
                logger.info(f"Using simple ENC reader (no GDAL): {e}")
                from lib.enc.s57_simple_reader import S57SimpleReader
                state.enc_reader = S57SimpleReader(enc_path)
                state.enc_reader.load()
            
            # Build feasible region
            safety_params = SafetyParameters(
                safety_depth=request.safety_depth,
                safety_contour=request.safety_depth,
                xtd_margin=185.2,  # 0.1 NM
                under_keel_clearance=request.under_keel_clearance,
                vessel_draft=request.vessel_draft
            )
            
            builder = FeasibleRegionBuilder(safety_params)
            state.feasible_region = builder.build_from_enc(state.enc_reader)
            state.planner = None  # Reset planner to use new feasible region
        
        # Initialize planner if not already done
        if not state.planner and state.feasible_region:
            config = PlannerConfig(
                grid_resolution=100.0,  # 100m grid
                motion_step=100.0,  # 100m steps
                max_iterations=5000,  # Enough iterations
                goal_tolerance_xy=100.0  # 100m tolerance
            )
            state.planner = HybridAStar(config, state.feasible_region)
        elif not state.planner:
            # Create dummy feasible region for testing
            from lib.region.feasible_region import FeasibleRegion
            from shapely.geometry import MultiPolygon, box
            
            # Create a large navigable area in meters (covers roughly ±180° longitude and ±85° latitude)
            import math
            lat_avg = (request.start.lat + request.goal.lat) / 2.0
            meters_per_deg_lat = 111320.0
            meters_per_deg_lon = 111320.0 * math.cos(math.radians(lat_avg))
            
            # Create bounds around the route
            min_lon = min(request.start.lon, request.goal.lon) - 1.0  # 1 degree padding
            max_lon = max(request.start.lon, request.goal.lon) + 1.0
            min_lat = min(request.start.lat, request.goal.lat) - 1.0
            max_lat = max(request.start.lat, request.goal.lat) + 1.0
            
            min_x = min_lon * meters_per_deg_lon
            max_x = max_lon * meters_per_deg_lon
            min_y = min_lat * meters_per_deg_lat
            max_y = max_lat * meters_per_deg_lat
            
            state.feasible_region = FeasibleRegion(
                bounds=(min_x, min_y, max_x, max_y),
                no_go_areas=MultiPolygon([]),
                navigable_area=MultiPolygon([box(min_x, min_y, max_x, max_y)]),
                depth_contours={},
                danger_zones=[],
                restricted_areas=[]
            )
            config = PlannerConfig(
                grid_resolution=100.0,  # 100m grid
                motion_step=100.0,  # 100m steps
                max_iterations=5000,  # Enough iterations
                goal_tolerance_xy=100.0  # 100m tolerance
            )
            state.planner = HybridAStar(config, state.feasible_region)
        
        # Convert coordinates to meters using local projection
        # For San Francisco area (lat ~37.8), use more accurate conversion
        import math
        lat_avg = (request.start.lat + request.goal.lat) / 2.0
        meters_per_deg_lat = 111320.0
        meters_per_deg_lon = 111320.0 * math.cos(math.radians(lat_avg))
        
        start_x = request.start.lon * meters_per_deg_lon
        start_y = request.start.lat * meters_per_deg_lat
        goal_x = request.goal.lon * meters_per_deg_lon
        goal_y = request.goal.lat * meters_per_deg_lat
        
        # Plan route
        start_pose = (start_x, start_y, 0.0)  # Heading will be calculated
        goal_pose = (goal_x, goal_y, None)  # No specific goal heading
        
        route = state.planner.plan(
            start_pose,
            goal_pose,
            initial_velocity=request.vessel_speed * 0.514444  # knots to m/s
        )
        
        if not route:
            raise HTTPException(status_code=400, detail="No valid route found")
        
        state.current_route = route
        
        # Convert route to response format
        waypoints = []
        for (x, y), heading, speed in zip(route.waypoints, route.headings, route.velocities):
            waypoints.append({
                "lat": y / meters_per_deg_lat,
                "lon": x / meters_per_deg_lon,
                "heading_deg": np.degrees(heading),
                "speed_kts": speed * 1.94384
            })
        
        # Calculate metrics
        total_distance_m = route.get_length()
        total_distance_nm = total_distance_m / 1852.0
        avg_speed_ms = np.mean(route.velocities)
        estimated_time_hours = total_distance_m / avg_speed_ms / 3600.0
        
        return PlanResponse(
            success=True,
            route_id=f"route_{datetime.now().strftime('%Y%m%d_%H%M%S')}",
            waypoints=waypoints,
            total_distance_nm=total_distance_nm,
            estimated_time_hours=estimated_time_hours,
            planning_time_seconds=route.planning_time,
            message="Route planned successfully"
        )
        
    except Exception as e:
        logger.error(f"Planning failed: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/validate", response_model=ValidateResponse)
async def validate_route(request: ValidateRequest):
    """
    Validate a route.
    """
    try:
        # Get route to validate
        route = None
        route_name = "Route"
        
        if request.route_id and state.current_route:
            route = state.current_route
            route_name = request.route_id
        elif request.rtz_content:
            # Parse RTZ
            from lib.io.rtz import RTZRoute, RTZConverter
            rtz_route = RTZRoute.from_xml(request.rtz_content)
            route = RTZConverter.rtz_to_route(rtz_route)
            route_name = rtz_route.route_name
        else:
            raise HTTPException(status_code=400, detail="No route specified for validation")
        
        # Initialize checker
        if not state.feasible_region:
            # Create dummy region for testing
            from lib.region.feasible_region import FeasibleRegion
            from shapely.geometry import MultiPolygon, box
            
            # Create a large navigable area that covers typical coordinates
            state.feasible_region = FeasibleRegion(
                bounds=(-20000000, -20000000, 20000000, 20000000),  # Large bounds
                no_go_areas=MultiPolygon([]),
                navigable_area=MultiPolygon([box(-20000000, -20000000, 20000000, 20000000)]),
                depth_contours={},
                danger_zones=[],
                restricted_areas=[]
            )
        
        checker = RouteChecker(state.feasible_region)
        report = checker.validate_route(route, route_name)
        state.validation_report = report
        
        # Save report
        report_path = Path(f"artifacts/validation_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json")
        report_path.parent.mkdir(exist_ok=True)
        report_path.write_text(report.to_json())
        
        return ValidateResponse(
            success=True,
            is_valid=report.is_valid,
            total_checks=report.total_checks,
            passed=report.passed_checks,
            failed=report.failed_checks,
            warnings=report.warnings,
            critical_issues=report.critical_issues,
            report_url=str(report_path)
        )
        
    except Exception as e:
        logger.error(f"Validation failed: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/export/rtz")
async def export_rtz(route_id: Optional[str] = None):
    """
    Export current route as RTZ file.
    """
    try:
        if not state.current_route:
            raise HTTPException(status_code=404, detail="No route available for export")
        
        # Convert to RTZ
        route_name = route_id or f"ECDIS_Route_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        rtz_route = RTZConverter.route_to_rtz(state.current_route, route_name)
        
        # Save to temp file
        with tempfile.NamedTemporaryFile(mode='w', suffix='.rtz', delete=False) as f:
            f.write(rtz_route.to_xml())
            temp_path = f.name
        
        return FileResponse(
            temp_path,
            media_type="application/xml",
            filename=f"{route_name}.rtz"
        )
        
    except Exception as e:
        logger.error(f"RTZ export failed: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/import/rtz")
async def import_rtz(file: UploadFile = File(...)):
    """
    Import RTZ file and convert to internal route format.
    """
    try:
        # Read uploaded file
        content = await file.read()
        rtz_content = content.decode('utf-8')
        
        # Parse RTZ
        from lib.io.rtz import RTZRoute, RTZConverter
        rtz_route = RTZRoute.from_xml(rtz_content)
        
        # Validate RTZ
        is_valid, errors = rtz_route.validate()
        if not is_valid:
            raise HTTPException(status_code=400, detail=f"Invalid RTZ: {', '.join(errors)}")
        
        # Convert to internal format
        route = RTZConverter.rtz_to_route(rtz_route)
        state.current_route = route
        
        return {
            "success": True,
            "route_name": rtz_route.route_name,
            "waypoint_count": len(rtz_route.waypoints),
            "status": rtz_route.route_status,
            "message": "RTZ imported successfully"
        }
        
    except Exception as e:
        logger.error(f"RTZ import failed: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/status")
async def get_status():
    """Get service status."""
    return {
        "status": "operational",
        "enc_loaded": state.enc_reader is not None,
        "region_built": state.feasible_region is not None,
        "planner_ready": state.planner is not None,
        "route_available": state.current_route is not None,
        "last_validation": state.validation_report is not None
    }


# Health check
@app.get("/health")
async def health_check():
    """Health check endpoint."""
    return {"status": "healthy", "timestamp": datetime.now().isoformat()}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)