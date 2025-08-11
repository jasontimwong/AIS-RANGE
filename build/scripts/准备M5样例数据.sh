#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

mkdir -p datasets/{s102,s111,s124} \
         tests/fixtures/{s102,s111,s124} \
         tests/{enc,env,plugins} \
         config/plugins docs/{enc,env,ukc} schemas

#############################################
# S-102: 高分辨率水深（CSV 栅格最小样例）
#############################################
cat > datasets/s102/mock_s102_grid.csv <<'CSV'
# lon,lat,depth_m
0.00,0.00,15
0.01,0.00,15
0.02,0.00,15
0.00,0.01,15
0.01,0.01,8
0.02,0.01,15
0.00,0.02,15
0.01,0.02,15
0.02,0.02,15
CSV

# 期望 no-go 掩码（安全深度=10m 时，仅中心点为 no-go）
cat > tests/fixtures/s102/expected_mask.csv <<'CSV'
# rows top->bottom; 1=no-go,0=go
0,0,0
0,1,0
0,0,0
CSV

cat > tests/enc/test_s102_depth_consistency.py <<'PY'
import csv, numpy as np, pathlib as pl
from lib.enc.s102_adapter import load_s102_csv, to_no_go_mask

def test_s102_no_go_mask_matches_expected(tmp_path):
    grid_p = pl.Path("datasets/s102/mock_s102_grid.csv")
    lon, lat, depth = load_s102_csv(str(grid_p))  # depth shape: (3,3)
    assert depth.shape == (3,3)

    mask = to_no_go_mask(depth, safety_depth_m=10.0)  # True=no-go
    # 读取期望 mask
    rows = []
    with open("tests/fixtures/s102/expected_mask.csv","r",encoding="utf-8") as f:
        for line in f:
            if line.strip().startswith("#") or not line.strip():
                continue
            rows.append([int(x) for x in line.strip().split(",")])
    expected = np.array(rows, dtype=bool)
    assert mask.shape == expected.shape
    assert np.array_equal(mask, expected), f"no-go mask mismatch:\n{mask}\nvs\n{expected}"
PY

cat > docs/enc_mapping_s102.md <<'MD'
# S-102 适配映射（最小子集）
- 输入：`datasets/s102/mock_s102_grid.csv`（lon, lat, depth_m）
- 输出：内部深度栅格（行优先，lat 从大到小或文档声明一致）
- 规则：
  - 安全等深线阈值 `safety_depth_m` → `to_no_go_mask(depth)`
  - 与 S-57 DEPARE/等深线的一致性，以面积差 ≤ 2% 为合格（报告差异热图）
MD

#############################################
# S-111: 表层流（CSV 时序最小样例）
#############################################
cat > datasets/s111/mock_currents.csv <<'CSV'
# time_iso,lon,lat,u_ms,v_ms
2025-08-10T00:00:00Z,0.01,0.01,1.0,0.0
2025-08-10T01:00:00Z,0.01,0.01,1.0,0.0
2025-08-10T02:00:00Z,0.01,0.01,1.0,0.0
CSV

cat > tests/env/test_s111_integration.py <<'PY'
import math, datetime as dt, pathlib as pl
from lib.env.s111_currents import load_s111_csv, sample_current, effective_speed_ms, travel_time_s

def test_s111_effect_on_speed_and_time():
    cur = load_s111_csv("datasets/s111/mock_currents.csv")
    t = dt.datetime.fromisoformat("2025-08-10T01:00:00+00:00")
    u, v = sample_current(cur, lon=0.01, lat=0.01, when=t)
    assert abs(u-1.0)<1e-6 and abs(v-0.0)<1e-6

    base_speed = 3.0  # m/s 船体在水中的航速
    heading = 0.0     # 朝正东
    eff = effective_speed_ms(base_speed, u, v, heading)
    assert eff > base_speed  # 顺流地速应更大

    L = 1000.0  # m
    t_no_current = travel_time_s(L, base_speed, 0.0, 0.0, heading)
    t_with_current = travel_time_s(L, base_speed, u, v, heading)
    assert t_with_current < t_no_current
PY

cat > docs/env_s111_model.md <<'MD'
# S-111 表层流集成（最小模型）
- CSV 列：`time_iso, lon, lat, u_ms, v_ms`
- 采样：最近邻（或双线性）+ 最近时刻
- 影响：
  - 代价场：逆流代价↑，顺流代价↓
  - 速度廓线：`v_ground = v_ship_body + current_projection`
MD

#############################################
# S-124: 航行警告（JSON 最小样例）
#############################################
cat > datasets/s124/mock_warnings.json <<'JSON'
{
  "warnings": [
    {
      "id": "S124-001",
      "category": "speed_limit",
      "speed_limit_kts": 10,
      "geometry": {
        "type": "Polygon",
        "coordinates": [[[0.005,0.005],[0.015,0.005],[0.015,0.015],[0.005,0.015],[0.005,0.005]]]
      },
      "time_start": "2025-08-01T00:00:00Z",
      "time_end":   "2025-12-31T23:59:59Z"
    },
    {
      "id": "S124-002",
      "category": "prohibited",
      "geometry": {
        "type": "Polygon",
        "coordinates": [[[-0.005,-0.005],[0.0,-0.005],[0.0,0.0],[-0.005,0.0],[-0.005,-0.005]]]
      },
      "time_start": "2025-08-01T00:00:00Z",
      "time_end":   "2025-09-01T00:00:00Z"
    }
  ]
}
JSON

cat > schemas/s124_warning.v1.json <<'JSON'
{
  "$schema":"https://json-schema.org/draft/2020-12/schema",
  "title":"S-124 mock warnings",
  "type":"object",
  "properties":{
    "warnings":{
      "type":"array",
      "items":{
        "type":"object",
        "required":["id","category","geometry","time_start","time_end"],
        "properties":{
          "id":{"type":"string"},
          "category":{"enum":["speed_limit","prohibited"]},
          "speed_limit_kts":{"type":"number"},
          "geometry":{
            "type":"object",
            "properties":{
              "type":{"const":"Polygon"},
              "coordinates":{"type":"array"}
            },
            "required":["type","coordinates"]
          },
          "time_start":{"type":"string","format":"date-time"},
          "time_end":{"type":"string","format":"date-time"}
        }
      }
    }
  },
  "required":["warnings"]
}
JSON

cat > tests/enc/test_s124_ingest_checks.py <<'PY'
import json, pathlib as pl
from lib.enc.s124_ingest import ingest_warnings

def test_s124_ingest_minimal():
    data = json.loads(pl.Path("datasets/s124/mock_warnings.json").read_text(encoding="utf-8"))
    feats = ingest_warnings(data)
    cats = {f.category for f in feats}
    assert {"speed_limit","prohibited"} <= cats
    speed_zones = [f for f in feats if f.category=="speed_limit"]
    assert speed_zones and hasattr(speed_zones[0], "speed_limit_kts")
    # 所有要素具备 geometry
    assert all(getattr(f,"geometry",None) is not None for f in feats)
PY

cat > docs/s124_mapping.md <<'MD'
# S-124 航行警告映射（最小子集）
- 支持分类：`speed_limit`（限速）、`prohibited`（禁航区）
- 几何：Polygon（GeoJSON）
- 行为：限速 → 速度代价/硬约束；禁航区 → no-go 面
- 报告：clause_refs 标注来源（S-124 mock）与生效时间窗
MD

#############################################
# UKC 插件：配置与测试
#############################################
cat > config/plugins/ukc.yaml <<'YAML'
min_ukc_m: 1.0
default_draft_m: 9.5
tide_elevation_m: 0.5
wave_heave_m: 0.3
YAML

cat > tests/plugins/test_ukc_min_clearance.py <<'PY'
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
PY

cat > docs/ukc/model.md <<'MD'
# UKC（Under Keel Clearance）最小模型
- UKC 定义：`UKC = depth - draft + tide - wave_heave`
- 约束：`UKC >= min_ukc_m`
- 集成：对路线离散采样（含中心浅点），输出最小 UKC 与违例计数
MD

echo "✅ 样例与测试模板已生成。"