"""
Fuel/Energy estimation helpers for avoidance evaluation (incremental module).

Models:
- Simple linear model (A): fuel_per_nm_ton * distance_nm
- Power model (B): Power ~ k * v^3; fuel_flow_ton_per_h = P(kW) * SFOC(g/kWh) / 1e6

Notes:
- Keep parameters configurable via service layer (read from config/env).
- Avoid heavy CFD; aim for fast, stable estimates for UI evaluation.
"""

from typing import List, Tuple, Dict, Optional
import math

LatLon = Tuple[float, float]


def to_radians(deg: float) -> float:
    return deg * math.pi / 180.0


def haversine_nm(a: LatLon, b: LatLon) -> float:
    lat1, lon1 = a
    lat2, lon2 = b
    Rm = 6371000.0
    dlat = to_radians(lat2 - lat1)
    dlon = to_radians(lon2 - lon1)
    la1 = to_radians(lat1)
    la2 = to_radians(lat2)
    h = math.sin(dlat / 2) ** 2 + math.cos(la1) * math.cos(la2) * math.sin(dlon / 2) ** 2
    c = 2 * math.atan2(math.sqrt(h), math.sqrt(1.0 - h))
    return (Rm * c) / 1852.0


def polyline_length_nm(points: List[LatLon]) -> float:
    if not points or len(points) < 2:
        return 0.0
    s = 0.0
    for i in range(len(points) - 1):
        s += haversine_nm(points[i], points[i + 1])
    return s


def time_hours(distance_nm: float, speed_kn: float) -> float:
    if speed_kn <= 0:
        return 0.0
    return distance_nm / speed_kn


def fuel_linear_ton(distance_nm: float, fuel_per_nm_ton: float) -> float:
    return max(0.0, distance_nm) * max(0.0, fuel_per_nm_ton)


def fuel_power_model_ton(
    distance_nm: float,
    speed_kn: float,
    k_power_v3: float = 1.0,
    sfoc_g_per_kwh: float = 180.0,
    hotel_load_ton_per_h: float = 0.0,
) -> float:
    """
    Very simplified propulsion model:
    - Effective power P(kW) ≈ k * v^3 (v in knots; k includes unit accommodations)
    - Fuel flow (ton/h) ≈ P(kW) * SFOC(g/kWh) / 1e6
    - Fuel total (ton) = fuel_flow * time_hours

    Units are collapsed into k; calibrate k via config to match vessel scale.
    """
    v = max(0.0, speed_kn)
    t_h = time_hours(distance_nm, v)
    P_kw = max(0.0, k_power_v3) * (v ** 3)
    fuel_ton_per_h = P_kw * max(0.0, sfoc_g_per_kwh) / 1_000_000.0
    return fuel_ton_per_h * t_h + max(0.0, hotel_load_ton_per_h) * t_h


def evaluate_delta(
    original_route: List[LatLon],
    dynamic_route: List[LatLon],
    *,
    model: str = "power",  # "simple" | "power"
    vessel_speed_kn: float = 15.0,
    vessel_speed_kn_original: Optional[float] = None,
    vessel_speed_kn_dynamic: Optional[float] = None,
    fuel_per_nm_ton: float = 0.072,
    fuel_price_usd_per_ton: float = 650.0,
    co2_per_ton_fuel: float = 3.114,
    k_power_v3: float = 1.0,
    sfoc_g_per_kwh: float = 180.0,
    # Maneuver penalties (ton of fuel per unit)
    beta_turn_ton_per_deg: float = 0.00005,
    beta_turn_count_ton: float = 0.005,
    shallow_factor_dynamic: float = 1.0,
) -> Dict:
    """
    Evaluate delta metrics between original and dynamic segments.
    Both routes should represent the replaced segment (caller decides slicing).
    """
    orig_nm = polyline_length_nm(original_route)
    dyn_nm = polyline_length_nm(dynamic_route)

    v_orig = vessel_speed_kn_original if vessel_speed_kn_original and vessel_speed_kn_original > 0 else vessel_speed_kn
    v_dyn = vessel_speed_kn_dynamic if vessel_speed_kn_dynamic and vessel_speed_kn_dynamic > 0 else vessel_speed_kn
    t_orig_h = time_hours(orig_nm, v_orig)
    t_dyn_h = time_hours(dyn_nm, v_dyn)

    if model == "simple":
        f_orig_t = fuel_linear_ton(orig_nm, fuel_per_nm_ton)
        f_dyn_t = fuel_linear_ton(dyn_nm, fuel_per_nm_ton)
    else:
        hotel = float(0.0)
        f_orig_t = fuel_power_model_ton(orig_nm, v_orig, k_power_v3, sfoc_g_per_kwh, hotel)
        f_dyn_t = fuel_power_model_ton(dyn_nm, v_dyn, k_power_v3, sfoc_g_per_kwh, hotel)

    # Maneuvering penalty: turning increases resistance and engine operation inefficiencies
    def heading_deg(p: LatLon, q: LatLon) -> float:
        lat1, lon1 = map(to_radians, (p[0], p[1]))
        lat2, lon2 = map(to_radians, (q[0], q[1]))
        dlon = lon2 - lon1
        y = math.sin(dlon) * math.cos(lat2)
        x = math.cos(lat1) * math.sin(lat2) - math.sin(lat1) * math.cos(lat2) * math.cos(dlon)
        brg = math.degrees(math.atan2(y, x))
        return (brg + 360.0) % 360.0

    def turn_stats(route: List[LatLon]) -> Tuple[float, int]:
        if len(route) < 3:
            return 0.0, 0
        heads = [heading_deg(route[i], route[i+1]) for i in range(len(route)-1)]
        total_turn = 0.0
        count = 0
        for i in range(len(heads)-1):
            d = abs(heads[i+1] - heads[i])
            if d > 180.0:
                d = 360.0 - d
            if d > 1e-3:
                total_turn += d
                count += 1
        return total_turn, count

    orig_turn_deg, orig_turns = turn_stats(original_route)
    dyn_turn_deg, dyn_turns = turn_stats(dynamic_route)
    maneuver_penalty_orig = orig_turn_deg * beta_turn_ton_per_deg + orig_turns * beta_turn_count_ton
    maneuver_penalty_dyn = dyn_turn_deg * beta_turn_ton_per_deg + dyn_turns * beta_turn_count_ton
    f_orig_t += maneuver_penalty_orig
    f_dyn_t += maneuver_penalty_dyn
    # Shallow water factor on dynamic segment (if enabled)
    f_dyn_t *= max(0.0, shallow_factor_dynamic)

    delta_nm = dyn_nm - orig_nm
    delta_h = t_dyn_h - t_orig_h
    delta_fuel_t = f_dyn_t - f_orig_t
    delta_cost_usd = delta_fuel_t * fuel_price_usd_per_ton
    delta_co2_t = delta_fuel_t * co2_per_ton_fuel

    return {
        "original_distance_nm": orig_nm,
        "dynamic_distance_nm": dyn_nm,
        "delta_distance_nm": delta_nm,
        "original_time_hours": t_orig_h,
        "dynamic_time_hours": t_dyn_h,
        "delta_time_hours": delta_h,
        "original_fuel_ton": f_orig_t,
        "dynamic_fuel_ton": f_dyn_t,
        "delta_fuel_ton": delta_fuel_t,
        "delta_cost_usd": delta_cost_usd,
        "delta_co2_ton": delta_co2_t,
        "model": model,
        "params_used": {
            "vessel_speed_kn": vessel_speed_kn,
            "vessel_speed_kn_original": v_orig,
            "vessel_speed_kn_dynamic": v_dyn,
            "fuel_per_nm_ton": fuel_per_nm_ton,
            "fuel_price_usd_per_ton": fuel_price_usd_per_ton,
            "co2_per_ton_fuel": co2_per_ton_fuel,
            "k_power_v3": k_power_v3,
            "sfoc_g_per_kwh": sfoc_g_per_kwh,
            "beta_turn_ton_per_deg": beta_turn_ton_per_deg,
            "beta_turn_count_ton": beta_turn_count_ton,
            "shallow_factor_dynamic": shallow_factor_dynamic,
        },
    }


