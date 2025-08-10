#!/usr/bin/env bash
set -euo pipefail

echo "======================================"
echo "进入 M6: 互操作性开发"
echo "======================================"

# 启用必要的特性标志
python - <<'PY'
import yaml, os

flags = {
    "s421_export": True,
    "s421_roundtrip": True,
    "stress_fuzzer": True
}

os.makedirs("config", exist_ok=True)

# 读取现有配置
try:
    with open("config/feature_flags.yaml", "r", encoding="utf-8") as f:
        cur = yaml.safe_load(f) or {}
except FileNotFoundError:
    cur = {}

# 更新标志
cur.setdefault("feature_flags", {}).update(flags)

# 写回配置
with open("config/feature_flags.yaml", "w", encoding="utf-8") as f:
    yaml.safe_dump(cur, f, allow_unicode=True, sort_keys=False)

print("已启用特性标志:", [k for k, v in cur["feature_flags"].items() if v])
PY

# 创建目录结构
mkdir -p lib/io
mkdir -p lib/testing
mkdir -p lib/forensics
mkdir -p lib/sbom
mkdir -p tests/io
mkdir -p tests/testing
mkdir -p tests/forensics
mkdir -p tests/sbom
mkdir -p data/stress
mkdir -p artifacts/fuzzing
mkdir -p artifacts/forensics
mkdir -p artifacts/sbom

echo "M6 开发环境已准备就绪"
echo ""
echo "任务清单:"
echo "  M6.1: S-421 双向互操作（roundtrip）"
echo "  M6.2: 压力测试框架（stress fuzzer）"
echo "  M6.3: 取证工具套件（forensics）"
echo "  M6.4: SBOM 供应链管理"
echo ""
echo "下一步: 实现 lib/io/s421_roundtrip.py"