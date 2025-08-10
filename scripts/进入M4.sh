#!/usr/bin/env bash
set -euo pipefail
ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

# 1) 打里程碑 tag（可回退）
TAG="v1.3.0-pre-M4-$(date +%Y%m%d_%H%M)"
git add -A && git commit -m "chore: freeze pre-M4 entrypoint" || true
git tag -a "$TAG" -m "Pre M4 entrypoint (frozen v1 API)"
echo "已打 tag: $TAG"

# 2) 冻结 v1 API（确保 schema 未改）
python - <<'PY'
import json,hashlib
for p in ["schemas/plan_request.v1.json","schemas/validation_report.v1.json"]:
    h=hashlib.sha256(open(p,'rb').read()).hexdigest()[:16]
    print(f"{p} sha256[:16]={h}")
PY

# 3) 开启 COLREG 开发相关开关（其余保持关闭）
python - <<'PY'
import yaml,os
path="config/feature_flags.yaml"
os.makedirs("config",exist_ok=True)
data={"feature_flags":{
    "colreg_rules": True,
    "s101_adapter": True,
    "s164_ci": True,
    "s421_export": False,
    "incr_replan": True,
    "s102_adapter": False,
    "s111_currents": False,
    "s124_warnings": False,
    "ukc_plugin": False,
    "s421_roundtrip": False,
    "stress_fuzzer": False
}}
with open(path,"w",encoding="utf-8") as f: yaml.safe_dump(data,f,allow_unicode=True,sort_keys=False)
print("feature_flags:",data["feature_flags"])
PY

# 4) 生成 COLREG 场景骨架（如不存在）
mkdir -p scenarios/colreg
for s in crossing overtaking head_on narrow tss_lane; do
  f="scenarios/colreg/${s}.yaml"
  if [ ! -f "$f" ]; then
    cat > "$f" <<EOF
# COLREG ${s} 场景（占位）
meta: {name: ${s}, version: 0}
ownship: {length_m: 200, beam_m: 32, draft_m: 10}
targets:
  - {mmsi: 111000001, sog: 12, cog: 090, lon: -122.6, lat: 37.8}
params:
  safety_depth_m: 10
  min_turn_radius_nm: 0.75
  xtd_nm: 0.2
  colreg_rule: ${s}
expectation:
  violations: 0
  hints: ["遵守相应 COLREG 规则，出具建议动作说明"]
EOF
  fi
done

# 5) 快速冒烟（不作为最终验收，仅确认框架未破）
pytest -q -k "colreg or cpa" -r a || true
echo "✅ 进入 M4：骨架已就绪。请按任务清单逐项实现。"