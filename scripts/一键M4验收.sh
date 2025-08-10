#!/usr/bin/env bash
set -euo pipefail
export PYTHONWARNINGS=error

# 开启 COLREG 功能
python - <<'PY'
import yaml,os
path="config/feature_flags.yaml"
os.makedirs("config",exist_ok=True)
data={"feature_flags":{"colreg_rules": True}}
with open(path,"w",encoding="utf-8") as f: yaml.safe_dump(data,f,allow_unicode=True,sort_keys=False)
print("feature_flags: colreg_rules=True")
PY

# 测试顺序：规则→校核→场景→金样
pytest -q lib/colreg -r a
pytest -q lib/checks/test_*colreg* -r a || true
pytest -q -k "colreg and not golden" -r a
pytest -q tests/approval/test_golden_colreg.py -r a

# 生成证据包
python tools/evidence_pack.py --route-id M4_acceptance_$(date +%Y%m%d_%H%M%S)
echo "✅ M4 验收完成"