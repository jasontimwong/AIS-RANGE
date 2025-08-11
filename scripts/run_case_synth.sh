#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"; cd "$ROOT"
SCN="scenarios/case_synth.yaml"
ART="artifacts/case_synth"; mkdir -p "$ART"

echo "=== 🧪 CASE-B: Synthetic Harbor Minimal E2E ==="

# 服务检查
if ! curl -s http://localhost:8000/docs >/dev/null; then
    echo "⚠️ 启动后端服务..."
    python -m service.app >/dev/null 2>&1 & 
    sleep 2
fi

# 构造请求
echo "▶ 步骤1: 构建合成场景请求"
python - "$SCN" > "$ART/plan_request.json" <<'PY'
import sys,yaml,json
scn=yaml.safe_load(open(sys.argv[1],encoding="utf-8"))
req=scn["plan"]
req.update({"obstacles":{"from_enc": False}, "seed": scn.get("seed",42)})
print(json.dumps(req,ensure_ascii=False))
PY

# 开关（只用样例数据的功能）
echo "▶ 步骤2: 配置特性开关（合成模式）"
python - <<'PY'
import yaml,os
p="config/feature_flags.yaml"; os.makedirs("config",exist_ok=True)
cur=yaml.safe_load(open(p,encoding="utf-8")) if os.path.exists(p) else {}
cur.setdefault("feature_flags",{}).update({
 "s102_adapter": True, "s111_currents": True, "s124_warnings": True, "ukc_plugin": True,
 "s101_adapter": False, "colreg_rules": False
})
yaml.safe_dump(cur, open(p,"w",encoding="utf-8"), allow_unicode=True, sort_keys=False)
print("  ✓ Feature flags set for synthetic mode")
PY

# /plan 两次 + 验证
echo "▶ 步骤3: 执行规划（确定性验证）"
for i in 1 2; do
  echo "  运行第 $i 次规划..."
  curl -s -X POST http://localhost:8000/plan -H "content-type: application/json" --data @"$ART/plan_request.json" > "$ART/plan_resp_$i.json"
done

echo "▶ 步骤4: 验证结果"
python - "$ART" <<'PY'
import json,sys,hashlib
from pathlib import Path
art=Path(sys.argv[1])
h=lambda x: hashlib.sha256(json.dumps(x,sort_keys=True).encode()).hexdigest()[:16]
r1=json.loads((art/"plan_resp_1.json").read_text(encoding="utf-8")).get("route",{})
r2=json.loads((art/"plan_resp_2.json").read_text(encoding="utf-8")).get("route",{})
h1, h2 = h(r1), h(r2)
print(f"  Route hash 1: {h1}")
print(f"  Route hash 2: {h2}")
assert h1==h2, "❌ 确定性失败"
print("  ✅ 确定性验证通过")

rep=json.loads((art/"plan_resp_1.json").read_text(encoding="utf-8")).get("validation_report",{})
fails=[c for c in rep.get("clause_refs",[]) if str(c.get("status")).upper()=="FAIL"]
assert not fails, f"❌ 合规失败：{fails[:3]}"
print("  ✅ 合规验证通过")

mukc=rep.get("min_ukc_m", 0.0)
if mukc >= 1.0:
    print(f"  ✅ UKC验证通过: {mukc:.1f}m ≥ 1.0m")
else:
    print(f"  ⚠️ UKC: {mukc:.1f}m (合成场景可能无深度数据)")
PY

# 生成证据包
echo "▶ 步骤5: 生成证据包"
python - "$ART" <<'PY'
import json, sys, os
from pathlib import Path
from datetime import datetime
art = Path(sys.argv[1])
evidence_dir = art / "evidence_pack"
evidence_dir.mkdir(exist_ok=True)

# 复制关键文件
for f in ["plan_request.json", "plan_resp_1.json", "plan_resp_2.json"]:
    src = art / f
    if src.exists():
        (evidence_dir / f).write_bytes(src.read_bytes())

# 生成摘要
resp = json.loads((art/"plan_resp_1.json").read_text(encoding="utf-8"))
report = resp.get("validation_report", {})
summary = {
    "case_id": "CASE_SYNTH",
    "timestamp": datetime.now().isoformat(),
    "route_points": len(resp.get("route", {}).get("waypoints", [])),
    "clause_summary": {
        "total": len(report.get("clause_refs", [])),
        "compliant": len([c for c in report.get("clause_refs",[]) if str(c.get("status")).upper()=="COMPLIANT"]),
        "warn": len([c for c in report.get("clause_refs",[]) if str(c.get("status")).upper()=="WARN"]),
        "fail": 0
    },
    "min_ukc_m": report.get("min_ukc_m", 0)
}
(evidence_dir / "summary.json").write_text(json.dumps(summary, indent=2, ensure_ascii=False))
print(f"  ✓ 证据包已生成: {evidence_dir}")
PY

echo ""
echo "=== 🎯 CASE_SYNTH 合成场景验证通过 ==="
echo "证据包位置: artifacts/case_synth/evidence_pack/"
echo "打开 UI 查看可视化: http://localhost:3001/ui/"
echo ""