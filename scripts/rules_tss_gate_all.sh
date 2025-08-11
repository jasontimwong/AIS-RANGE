#!/usr/bin/env bash
# 规则补全与ENC/TSS门禁一键执行脚本
# Rules Completion and ENC/TSS Gate All-in-One Script

set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

SCN="${1:-scenarios/case_sf_tss.yaml}"             # 旗舰CASE
ART="artifacts/rules_tss_gate"
mkdir -p "$ART"

echo "========================================="
echo "    规则补全与ENC/TSS门禁验证"
echo "    Rules & ENC/TSS Gate Validation"
echo "========================================="
echo ""

echo "== 步骤 1/4: 生成/合并规则清单 =="
python3 tools/rules_gap_report.py --init

echo ""
echo "== 步骤 2/4: 规则覆盖度检查 + 生成补全模板 =="
python3 tools/rules_gap_report.py \
  --manifest docs/compliance/required_rules.yaml \
  --plan-resp artifacts/case_sf_tss/plan_resp_tss_compliant.json \
  --out "$ART/RULES_REPORT.md"

echo ""
echo "规则覆盖度报告:"
cat "$ART/RULES_REPORT.md" | head -30

echo ""
echo "== 步骤 3/4: ENC/TSS 合规几何验证 =="
python3 tools/tss_geovalidate.py \
  --scenario "$SCN" \
  --plan-resp artifacts/case_sf_tss/plan_resp_tss_compliant.json \
  --out "$ART/TSS_REPORT.md"

echo ""
echo "TSS验证报告:"
cat "$ART/TSS_REPORT.md" | head -30

echo ""
echo "== 步骤 4/4: 汇总门禁结论 =="

# 检查是否有失败标记
FAIL_COUNT=0
if [[ -f "$ART/FAIL" ]]; then
  echo "发现失败标记文件: $ART/FAIL"
  FAIL_COUNT=$((FAIL_COUNT + 1))
fi

if [[ $FAIL_COUNT -gt 0 ]]; then
  echo ""
  echo "❌ 门禁未通过"
  echo ""
  echo "失败原因:"
  [[ -f "$ART/FAIL" ]] && echo "- $(cat "$ART/FAIL")"
  echo ""
  echo "详细报告:"
  echo "- 规则报告: $ART/RULES_REPORT.md"
  echo "- TSS报告: $ART/TSS_REPORT.md"
  exit 2
else
  echo ""
  echo "✅ 门禁通过"
  echo ""
  echo "验证结果:"
  echo "- 规则覆盖: 完整"
  echo "- TSS合规: 通过"
  echo ""
  echo "详细报告:"
  echo "- 规则报告: $ART/RULES_REPORT.md"
  echo "- TSS报告: $ART/TSS_REPORT.md"
fi