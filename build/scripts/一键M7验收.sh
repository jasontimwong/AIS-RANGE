#!/usr/bin/env bash
set -euo pipefail

echo "======================================"
echo "M7 4D时域规划验收"
echo "======================================"

# 运行各组件测试
echo "运行 S-104 水位/潮汐适配器测试..."
pytest -q tests/enc/test_s104_sampling.py -r a

echo "运行 4D 时域规划器测试..."
pytest -q tests/planner/test_planner_4d_basic.py -r a

echo "运行 ETA 窗口优化器测试..."
pytest -q tests/eta/test_eta_window.py -r a

echo "运行动态 UKC 计算测试..."
pytest -q tests/plugins/test_ukc_dynamic.py -r a

# 生成证据包
echo "生成证据包..."
python - <<'PY'
import json, datetime, pathlib as pl

# 生成证据包
evidence = {
    "validation_time": datetime.datetime.now().isoformat(),
    "milestone": "M7",
    "description": "4D时域规划 + 潮汐/水位联动 + ETA/窗口",
    "tasks": {
        "T7.1": {
            "name": "S-104 水位/潮汐适配",
            "status": "completed",
            "files": ["lib/enc/s104_adapter.py"],
            "tests_passed": True,
            "acceptance": "给定时刻与点位能返回水位；插值/外推策略声明清楚"
        },
        "T7.2": {
            "name": "4D 成本场与搜索",
            "status": "completed",
            "files": ["lib/planner/planner_4d.py"],
            "tests_passed": True,
            "acceptance": "相同空间起终点，因潮窗/流场变化得到不同发航时刻/速度策略"
        },
        "T7.3": {
            "name": "ETA/窗口优化器",
            "status": "completed",
            "files": ["lib/eta/optimizer.py"],
            "tests_passed": True,
            "acceptance": "给定 [E, L] 到达窗口，优化后 ETA ∈ [E, L]"
        },
        "T7.4": {
            "name": "UKC 动态化",
            "status": "completed",
            "files": ["lib/plugins/ukc_dynamic.py"],
            "tests_passed": True,
            "acceptance": "报告包含时间/里程轴下最小 UKC 曲线"
        }
    },
    "test_results": {
        "s104_adapter": "PASSED",
        "planner_4d": "PASSED",
        "eta_optimizer": "PASSED",
        "ukc_dynamic": "PASSED"
    },
    "capabilities": {
        "time_domain": "4D planning with time as dimension",
        "tide_integration": "S-104 water level time series",
        "eta_optimization": "Speed profile for arrival windows",
        "dynamic_ukc": "Time-varying UKC with tide/squat"
    }
}

# 保存证据包
evidence_dir = pl.Path("artifacts/evidence")
evidence_dir.mkdir(parents=True, exist_ok=True)
evidence_file = evidence_dir / f"M7_evidence_{datetime.datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
with open(evidence_file, "w") as f:
    json.dump(evidence, f, indent=2)

print(f"Evidence pack saved to: {evidence_file}")
PY

echo "======================================"
echo "✅ M7 验收完成"
echo "======================================"