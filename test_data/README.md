# 测试数据目录

本目录包含用于演示和测试动态路径规划功能的数据文件。

## 目录结构

```
test_data/
├── routes/           # 测试航线数据
│   ├── baseline/     # 基准航线（无威胁）
│   └── dynamic/      # 动态规划结果
├── ais/             # AIS目标数据
│   ├── static/      # 静态AIS场景
│   └── dynamic/     # 动态AIS序列
└── scenarios/       # 完整测试场景
    ├── simple/      # 简单避碰场景
    ├── complex/     # 复杂多船场景
    └── extreme/     # 极限测试场景
```

## 数据格式

### 航线数据 (routes/*.json)
```json
{
  "route_id": "test_route_001",
  "timestamp": "2025-08-14T15:00:00Z",
  "waypoints": [
    {"lat": 31.23, "lon": 121.508, "name": "Start"},
    {"lat": 31.00, "lon": 122.00, "name": "End"}
  ],
  "metadata": {
    "distance_nm": 45.2,
    "motion_step_m": 50,
    "planning_time_s": 0.194
  }
}
```

### AIS数据 (ais/*.json)
```json
{
  "scenario_id": "collision_risk_001",
  "timestamp": "2025-08-14T15:00:00Z",
  "targets": [
    {
      "mmsi": "TEST001",
      "position": [31.18, 121.65],
      "sog": 15.0,
      "cog": 270.0,
      "risk_level": "HIGH"
    }
  ]
}
```

## 使用方法

1. **加载测试场景**:
   ```python
   from test_data.loader import load_scenario
   scenario = load_scenario('complex/multi_vessel_crossing')
   ```

2. **运行动态规划**:
   ```python
   dynamic_route = planner.plan_with_scenario(scenario)
   ```

3. **对比结果**:
   ```python
   from test_data.analyzer import compare_routes
   comparison = compare_routes(baseline_route, dynamic_route)
   ```