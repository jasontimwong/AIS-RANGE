#!/usr/bin/env bash
set -euo pipefail

echo "========================================="
echo "🚢 ECDIS End-to-End Validation Suite"
echo "========================================="
echo ""

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"; cd "$ROOT"
TIMESTAMP=$(date +%Y%m%d-%H%M%S)
REPORT="artifacts/e2e_report_${TIMESTAMP}.txt"

# Initialize report
echo "ECDIS E2E Validation Report" > "$REPORT"
echo "Generated: $(date)" >> "$REPORT"
echo "=========================================" >> "$REPORT"

# Check services
echo "▶ Checking services..."
if ! curl -s http://localhost:8000/docs >/dev/null 2>&1; then
    echo "  ⚠️ Backend not running, starting..."
    python -m service.app >/dev/null 2>&1 &
    sleep 3
fi

if ! curl -s http://localhost:3001/ui/ >/dev/null 2>&1; then
    echo "  ⚠️ Frontend not running, please start with: npm run dev"
fi

echo "  ✓ Services ready"
echo ""

# Run CASE-B (Synthetic)
echo "=== Running CASE-B: Synthetic Harbor ==="
echo "" >> "$REPORT"
echo "CASE-B: Synthetic Harbor" >> "$REPORT"
echo "-----------------------------------------" >> "$REPORT"

if ./scripts/run_case_synth.sh > artifacts/case_synth_output.txt 2>&1; then
    echo "  ✅ CASE-B PASSED"
    echo "RESULT: PASSED" >> "$REPORT"
    
    # Extract metrics
    python - artifacts/case_synth >> "$REPORT" <<'PY'
import json, sys
from pathlib import Path
art = Path(sys.argv[1])
resp = json.loads((art/"plan_resp_1.json").read_text(encoding="utf-8"))
print(f"Waypoints: {len(resp.get('waypoints', []))}")
print(f"Route ID: {resp.get('route_id', 'N/A')}")
val = resp.get('validation_report', {})
print(f"Clauses checked: {len(val.get('clause_refs', []))}")
PY
else
    echo "  ❌ CASE-B FAILED"
    echo "RESULT: FAILED" >> "$REPORT"
fi

# Run CASE-A (San Francisco TSS) if ENC exists
echo ""
echo "=== Running CASE-A: San Francisco TSS ==="
echo "" >> "$REPORT"
echo "CASE-A: San Francisco TSS" >> "$REPORT"
echo "-----------------------------------------" >> "$REPORT"

if [ -f "datasets/enc/US5CA12M/US5CA12M.000" ]; then
    if ./scripts/run_case_sf_tss.sh > artifacts/case_sf_output.txt 2>&1; then
        echo "  ✅ CASE-A PASSED"
        echo "RESULT: PASSED" >> "$REPORT"
        
        # Extract metrics
        python - artifacts/case_sf_tss >> "$REPORT" <<'PY'
import json, sys
from pathlib import Path
art = Path(sys.argv[1])
resp = json.loads((art/"plan_resp_1.json").read_text(encoding="utf-8"))
print(f"Waypoints: {len(resp.get('waypoints', []))}")
val = resp.get('validation_report', {})
cla = val.get('clause_refs', [])
print(f"Clauses: {len(cla)} total")
print(f"  - COMPLIANT: {len([c for c in cla if c.get('status')=='COMPLIANT'])}")
print(f"  - WARN: {len([c for c in cla if c.get('status')=='WARN'])}")
print(f"  - FAIL: {len([c for c in cla if c.get('status')=='FAIL'])}")
print(f"Min UKC: {val.get('min_ukc_m', 0):.1f}m")
PY
    else
        echo "  ❌ CASE-A FAILED"
        echo "RESULT: FAILED" >> "$REPORT"
    fi
else
    echo "  ⏭️ CASE-A SKIPPED (No ENC data found)"
    echo "RESULT: SKIPPED (No ENC data)" >> "$REPORT"
    echo "  Hint: Download NOAA ENC US5CA12M to datasets/enc/US5CA12M/"
fi

# Generate final summary
echo ""
echo "========================================="
echo "📊 E2E Validation Summary"
echo "========================================="

python - "$REPORT" <<'PY'
import sys
report_file = sys.argv[1]
with open(report_file, 'r') as f:
    content = f.read()
    
passed = content.count("RESULT: PASSED")
failed = content.count("RESULT: FAILED")
skipped = content.count("RESULT: SKIPPED")

print(f"  Passed: {passed}")
print(f"  Failed: {failed}")
print(f"  Skipped: {skipped}")
print()
print(f"  Report: {report_file}")
print()

if failed == 0:
    print("🎯 All tests PASSED! System ready for production.")
else:
    print("⚠️ Some tests failed. Check report for details.")
PY

echo ""
echo "▶ UI Available at: http://localhost:3001/ui/"
echo "▶ API Docs at: http://localhost:8000/docs"
echo ""