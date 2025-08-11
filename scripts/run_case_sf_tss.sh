#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"; cd "$ROOT"
SCN="scenarios/case_sf_tss.yaml"
ART="artifacts/case_sf_tss"; mkdir -p "$ART"

echo "=== 🚢 CASE-A: San Francisco TSS End-to-End Validation ==="

# 0. 服务连通性检查
if ! curl -s http://localhost:8000/docs >/dev/null; then
  echo "⚠️ FastAPI 未运行，尝试本地启动（如已在其他端口运行请手动调整）"
  python -m service.app >/dev/null 2>&1 &
  sleep 2
fi

# 1. 读取场景，构造 PlanRequest
echo "▶ 步骤1: 构建规划请求"
python - "$SCN" > "$ART/plan_request.json" <<'PY'
import sys, yaml, json
scn = yaml.safe_load(open(sys.argv[1], encoding="utf-8"))
req = scn["plan"]
req.update({
  "obstacles": {"from_enc": True},
  "tss_policy": scn["plan"].get("tss_policy", {"enforce_lane": True, "forbid_sep_zone": True}),
  "speed_policy": scn["plan"].get("speed_policy", {"default_kts": 12, "respect_restrictions": True}),
  "ukc": scn["plan"].get("ukc", {"min_ukc_m": 1.0}),
  "seed": scn.get("seed",42)
})
print(json.dumps(req, ensure_ascii=False))
PY

# 2. 开启相关特性开关（其他保持已有配置）
echo "▶ 步骤2: 配置特性开关"
python - <<'PY'
import yaml,os
p="config/feature_flags.yaml"; os.makedirs("config",exist_ok=True)
cur=yaml.safe_load(open(p,encoding="utf-8")) if os.path.exists(p) else {}
ff=cur.get("feature_flags",{})
ff.update({
  "s101_adapter": bool(False),     # 若你有 S-101，可改 True
  "s102_adapter": True,
  "s111_currents": True,
  "s124_warnings": True,
  "ukc_plugin": True,
  "colreg_rules": True,
  "incr_replan": True
})
cur["feature_flags"]=ff
yaml.safe_dump(cur, open(p,"w",encoding="utf-8"), allow_unicode=True, sort_keys=False)
print("✓ Feature flags configured")
PY

# 3. 调用 /plan（记录时间、输出）—— 第一次
echo "▶ 步骤3: 执行路线规划（第1次）"
T1=$(date +%s%3N)
curl -s -X POST http://localhost:8000/plan \
  -H "content-type: application/json" \
  --data @"$ART/plan_request.json" > "$ART/plan_resp_1.json"
T2=$(date +%s%3N); DUR1=$((T2-T1))
echo "  规划用时：${DUR1} ms"

# 4. 确定性校验：相同输入再来一次
echo "▶ 步骤4: 执行路线规划（第2次 - 确定性校验）"
T3=$(date +%s%3N)
curl -s -X POST http://localhost:8000/plan \
  -H "content-type: application/json" \
  --data @"$ART/plan_request.json" > "$ART/plan_resp_2.json"
T4=$(date +%s%3N); DUR2=$((T4-T3))
echo "  第二次用时：${DUR2} ms"

# 5. 解析与验收门槛（无 FAIL、UKC、TSS、性能）
echo "▶ 步骤5: 验证确定性与合规性"
python - "$ART" <<'PY'
import json,sys,hashlib
from pathlib import Path
art=Path(sys.argv[1])
j1=json.loads((art/"plan_resp_1.json").read_text(encoding="utf-8"))
j2=json.loads((art/"plan_resp_2.json").read_text(encoding="utf-8"))

def h(s): return hashlib.sha256(json.dumps(s,sort_keys=True).encode()).hexdigest()[:16]
r1=j1.get("route",{})
r2=j2.get("route",{})
h1,h2=h(r1),h(r2)
print(f"  Route hash 1: {h1}")
print(f"  Route hash 2: {h2}")
assert h1==h2, "❌ 确定性失败：两次路线哈希不同"
print("  ✅ 确定性验证通过")

rep=j1.get("validation_report",{})
cla=rep.get("clause_refs",[])
fails=[c for c in cla if str(c.get("status")).upper()=="FAIL"]
if fails:
    print(f"  ❌ 合规失败：存在 FAIL 条款")
    for f in fails[:3]:
        print(f"    - {f}")
    exit(1)
print("  ✅ 合规验证通过（无FAIL条款）")

mukc=rep.get("min_ukc_m", 0.0)
assert mukc>=1.0, f"❌ UKC 过低：min_ukc_m={mukc}"
print(f"  ✅ UKC验证通过: {mukc:.1f}m ≥ 1.0m")

# 显示条款统计
compliant = len([c for c in cla if str(c.get("status")).upper()=="COMPLIANT"])
warn = len([c for c in cla if str(c.get("status")).upper()=="WARN"])
print(f"  条款统计: {compliant} COMPLIANT, {warn} WARN, {len(fails)} FAIL")
PY

# 6. RTZ 导出→导入往返一致
echo "▶ 步骤6: RTZ格式往返一致性测试"
curl -s -X POST http://localhost:8000/export/rtz \
  -H "content-type: application/json" \
  --data @"$ART/plan_resp_1.json" > "$ART/route.rtz"
echo "  ✓ RTZ导出完成"

curl -s -X POST http://localhost:8000/import/rtz \
  -H "content-type: application/xml" \
  --data-binary @"$ART/route.rtz" > "$ART/rtz_roundtrip.json"
echo "  ✓ RTZ导入完成"

python - "$ART" <<'PY'
import json,sys,hashlib
from pathlib import Path
art=Path(sys.argv[1])
orig=json.loads((art/"plan_resp_1.json").read_text(encoding="utf-8")).get("route",{})
back=json.loads((art/"rtz_roundtrip.json").read_text(encoding="utf-8")).get("route",{})
h=lambda x: hashlib.sha256(json.dumps(x,sort_keys=True).encode()).hexdigest()[:16]
h1, h2 = h(orig), h(back)
if h1 != h2:
    print(f"  ❌ RTZ 往返不一致: {h1} != {h2}")
    exit(1)
print("  ✅ RTZ往返一致性验证通过")
PY

# 7. 性能阈值（规划 < 2s）
echo "▶ 步骤7: 性能验证"
if [ "${DUR1}" -gt 2000 ]; then 
    echo "  ❌ 性能不达标：${DUR1} ms > 2000ms"
    exit 2
fi
echo "  ✅ 性能验证通过：${DUR1} ms < 2000ms"

# 8. 生成证据包（包含报告/参数/日志/金样等）
echo "▶ 步骤8: 生成证据包"
python - "$ART" <<'PY'
import json, sys, os
from pathlib import Path
from datetime import datetime
art = Path(sys.argv[1])
evidence_dir = art / "evidence_pack"
evidence_dir.mkdir(exist_ok=True)

# 复制关键文件
files_to_copy = [
    "plan_request.json",
    "plan_resp_1.json", 
    "plan_resp_2.json",
    "route.rtz",
    "rtz_roundtrip.json"
]
for f in files_to_copy:
    src = art / f
    if src.exists():
        dst = evidence_dir / f
        dst.write_bytes(src.read_bytes())

# 生成摘要报告
resp = json.loads((art/"plan_resp_1.json").read_text(encoding="utf-8"))
report = resp.get("validation_report", {})
summary = {
    "case_id": "CASE_SF_TSS",
    "timestamp": datetime.now().isoformat(),
    "route_hash": hashlib.sha256(json.dumps(resp.get("route",{}),sort_keys=True).encode()).hexdigest()[:16],
    "clause_summary": {
        "total": len(report.get("clause_refs", [])),
        "compliant": len([c for c in report.get("clause_refs",[]) if str(c.get("status")).upper()=="COMPLIANT"]),
        "warn": len([c for c in report.get("clause_refs",[]) if str(c.get("status")).upper()=="WARN"]),
        "fail": len([c for c in report.get("clause_refs",[]) if str(c.get("status")).upper()=="FAIL"])
    },
    "min_ukc_m": report.get("min_ukc_m", 0),
    "performance_ms": int(os.environ.get("DUR1", 0)) if "DUR1" in os.environ else None
}
(evidence_dir / "summary.json").write_text(json.dumps(summary, indent=2, ensure_ascii=False))
print(f"  ✓ 证据包已生成: {evidence_dir}")

import hashlib
PY

echo ""
echo "=== 🎯 CASE_SF_TSS 全链路验证通过 ==="
echo "证据包位置: artifacts/case_sf_tss/evidence_pack/"
echo "现在可打开 UI 查看可视化: http://localhost:3001/ui/"
echo ""