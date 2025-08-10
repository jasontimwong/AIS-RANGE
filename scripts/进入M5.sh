#!/usr/bin/env bash
set -euo pipefail
ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

# 1) 打回退点
TAG="v1.3.0-pre-M5-$(date +%Y%m%d_%H%M)"
git add -A && git commit -m "chore: freeze pre-M5 entrypoint" || true
git tag -a "$TAG" -m "Pre M5 entrypoint (freeze v1 API)"
echo "已打 tag: $TAG"

# 2) 冻结 v1 API（仅打印指纹，确保 schema 未改）
python - <<'PY'
import hashlib
for p in ["schemas/plan_request.v1.json","schemas/validation_report.v1.json"]:
    try:
        h=hashlib.sha256(open(p,'rb').read()).hexdigest()[:16]
        print(f"{p} sha256[:16]={h}")
    except FileNotFoundError:
        print(f"{p} not found (will create)")
PY

# 3) 开启 M5 相关特性开关（其余保持关闭）
python - <<'PY'
import yaml,os
flags={
 "s101_adapter": True,
 "s164_ci": True,
 "s421_export": False,
 "s421_roundtrip": False,
 "incr_replan": True,
 "s102_adapter": True,    # 高分辨率水深
 "s111_currents": True,   # 表层流
 "s124_warnings": True,   # 航行警告
 "ukc_plugin": True,      # UKC 插件
 "stress_fuzzer": False
}
os.makedirs("config",exist_ok=True)
with open("config/feature_flags.yaml","w",encoding="utf-8") as f:
    yaml.safe_dump({"feature_flags":flags},f,allow_unicode=True,sort_keys=False)
print("feature_flags:",flags)
PY

# 4) 准备数据目录（占位）
mkdir -p datasets/{s102,s111,s124}
echo "- 请将 S-102/S-111/S-124 子集放入 datasets 对应目录（CI/离线均可）"

# 5) 快速冒烟（可忽略失败；M5 完成后用验收脚本收尾）
pytest -q -k "s102 or s111 or s124 or ukc" -r a || true
echo "✅ 进入 M5：骨架就绪。按任务清单逐项实现。"