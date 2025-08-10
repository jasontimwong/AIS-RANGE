import numpy as np, pathlib as pl, csv
from lib.enc.s102_adapter import load_s102_csv
from lib.plugins.ukc import evaluate_route_ukc

def _load_depth_grid():
    return load_s102_csv("datasets/s102/mock_s102_grid.csv")  # lon, lat, depth(3x3)

def test_ukc_ok_then_violate():
    lon, lat, depth = _load_depth_grid()
    # 取一条过中心的简单航线（3 个点穿过浅点）
    route_pts = [(0.00,0.01),(0.01,0.01),(0.02,0.01)]
    cfg = dict(min_ukc_m=1.0, tide_elevation_m=0.5, wave_heave_m=0.3)

    # 情况 A：吃水 9.5m，中心深 8m，潮+波 0.8m → UKC = 8 - 9.5 + 0.8 = -0.7m（应判定不可行）
    # 为了演示两种情况，我们先用 draft=7.0（可行），再用 11.5（不可行）
    ok = evaluate_route_ukc(route_pts, lon, lat, depth, ship_draft_m=7.0, **cfg)
    assert ok.min_ukc_m >= 1.0 or ok.violations == 0

    bad = evaluate_route_ukc(route_pts, lon, lat, depth, ship_draft_m=11.5, **cfg)
    assert bad.violations > 0
