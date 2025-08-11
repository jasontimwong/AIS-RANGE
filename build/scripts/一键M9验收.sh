#!/usr/bin/env bash
set -euo pipefail

echo "========================================"
echo "M9 长航段拼接与瓦片缓存验收"
echo "========================================"

# 运行各组件测试
echo "运行瓦片管理器测试..."
pytest -q tests/tiling/test_tile_manager.py -r a

echo "运行缓存策略测试..."
pytest -q tests/tiling/test_cache_strategy.py -r a

echo "运行动态加载器测试..."
pytest -q tests/tiling/test_dynamic_loader.py -r a

# 生成证据包
echo "生成证据包..."
python - <<'PY'
import json, datetime, pathlib as pl

# 生成证据包
evidence = {
    "validation_time": datetime.datetime.now().isoformat(),
    "milestone": "M9",
    "description": "长航段拼接与瓦片缓存",
    "tasks": {
        "T9.1": {
            "name": "瓦片管理器",
            "status": "completed",
            "files": ["lib/tiling/tile_manager.py"],
            "tests_passed": True,
            "acceptance": "瓦片索引、边界计算、拼接功能完成"
        },
        "T9.2": {
            "name": "缓存策略",
            "status": "completed",
            "files": ["lib/tiling/cache_strategy.py"],
            "tests_passed": True,
            "acceptance": "LRU缓存、预测缓存、分层缓存实现"
        },
        "T9.3": {
            "name": "动态加载器",
            "status": "completed",
            "files": ["lib/tiling/dynamic_loader.py"],
            "tests_passed": True,
            "acceptance": "按需加载、预取、流式加载完成"
        }
    },
    "test_results": {
        "tile_manager": "PASSED",
        "cache_strategy": "PASSED",
        "dynamic_loader": "PASSED"
    },
    "capabilities": {
        "tile_management": "1°x1° tile grid with spatial indexing",
        "cache_strategy": "LRU/predictive/tiered caching up to 500MB",
        "dynamic_loading": "Parallel loading with prefetch",
        "streaming": "Continuous voyage window management"
    },
    "performance": {
        "tile_size": "1 degree",
        "cache_size_mb": 500,
        "prefetch_radius": 2,
        "max_workers": 4
    }
}

# 保存证据包
evidence_dir = pl.Path("artifacts/evidence")
evidence_dir.mkdir(parents=True, exist_ok=True)
evidence_file = evidence_dir / f"M9_evidence_{datetime.datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
with open(evidence_file, "w") as f:
    json.dump(evidence, f, indent=2)

print(f"Evidence pack saved to: {evidence_file}")
PY

echo "========================================"
echo "✅ M9 验收完成"
echo "========================================"