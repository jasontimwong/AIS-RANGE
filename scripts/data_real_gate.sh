#!/usr/bin/env bash
# 数据真实性门禁脚本
# 用于验证旗舰CASE（旧金山TSS）使用真实数据
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

SCN="${1:-scenarios/case_sf_tss.yaml}"
OUT="artifacts/data_gate"
mkdir -p "$OUT"

echo "========================================="
echo "    数据真实性门禁 Data-Real Gate"
echo "========================================="
echo ""
echo "场景文件: $SCN"
echo "输出目录: $OUT"
echo ""

echo "== 步骤1: 解析场景与特性开关 =="
python3 - "$SCN" > "$OUT/data_provenance.yaml" <<'PY'
import sys, yaml, os, hashlib, json
from pathlib import Path

scn_path = sys.argv[1]
scn = yaml.safe_load(open(scn_path, encoding="utf-8"))

# 加载特性标志
flags = {}
try:
    flags = yaml.safe_load(open("config/feature_flags.yaml", encoding="utf-8")) or {}
except Exception:
    flags = {}

def file_hash(path): 
    """计算文件SHA256哈希（前16位）"""
    try:
        return hashlib.sha256(open(path, 'rb').read()).hexdigest()[:16]
    except:
        return None

def file_size(path):
    """获取文件大小"""
    try:
        return os.path.getsize(path)
    except:
        return 0

# 提取配置数据
enc = scn.get("enc", {})
data = scn.get("data", {})
plan = scn.get("plan", {})

# 船舶模型参数
ship = {
    "length_m": scn.get("ownship", {}).get("length_m") or plan.get("ship_length_m"),
    "beam_m": scn.get("ownship", {}).get("beam_m") or plan.get("ship_beam_m"),
    "draft_m": scn.get("ownship", {}).get("draft_m") or plan.get("draft_m"),
    "min_turn_radius_nm": plan.get("min_turn_radius_nm")
}

# 构建数据谱系
provenance = {
    "scenario_id": scn.get("meta", {}).get("id", "UNKNOWN"),
    "scenario_name": scn.get("meta", {}).get("name", "Unknown Scenario"),
    "feature_flags": flags.get("feature_flags", {}),
    "required_real": ["ENC", "TSS", "VESSEL", "RTZ"],
    "datasets": [
        {
            "type": "ENC_S57",
            "path": enc.get("s57_path"),
            "hash": file_hash(enc.get("s57_path", "")),
            "size": file_size(enc.get("s57_path", ""))
        },
        {
            "type": "ENC_S101", 
            "path": enc.get("s101_path"),
            "hash": file_hash(enc.get("s101_path", "")),
            "size": file_size(enc.get("s101_path", ""))
        },
        {
            "type": "S102",
            "path": data.get("s102"),
            "hash": file_hash(data.get("s102", "")),
            "size": file_size(data.get("s102", ""))
        },
        {
            "type": "S111",
            "path": data.get("s111"),
            "hash": file_hash(data.get("s111", "")),
            "size": file_size(data.get("s111", ""))
        },
        {
            "type": "S124",
            "path": data.get("s124"),
            "hash": file_hash(data.get("s124", "")),
            "size": file_size(data.get("s124", ""))
        },
        {
            "type": "S104",
            "path": data.get("s104"),
            "hash": file_hash(data.get("s104", "")),
            "size": file_size(data.get("s104", ""))
        },
        {
            "type": "RTZ_SCHEMA",
            "path": "schemas/rtz_schema.json",
            "hash": file_hash("schemas/rtz_schema.json"),
            "size": file_size("schemas/rtz_schema.json")
        }
    ],
    "ship_model": ship,
    "plan_request_path": "artifacts/case_sf_tss/plan_request.json",
    "plan_response_path": "artifacts/case_sf_tss/plan_resp_1.json",
    "evidence_pack_path": "artifacts/case_sf_tss/evidence_pack"
}

# 输出YAML格式
print(yaml.safe_dump(provenance, allow_unicode=True, sort_keys=False))
PY

echo ""
echo "== 步骤2: 运行数据真实性校验器 =="
python3 tools/data_real_gate.py --provenance "$OUT/data_provenance.yaml" --out "$OUT/REPORT.md"

echo ""
echo "== 步骤3: 显示报告 =="
cat "$OUT/REPORT.md"

echo ""
echo "========================================="

# 清理之前的FAIL文件
rm -f "$OUT/FAIL"

# 检查是否通过
if [[ -f "$OUT/FAIL" ]]; then
    echo "❌ 数据真实性门禁未通过"
    echo ""
    echo "请检查以下必须项："
    echo "1. ENC数据: 需要真实的S-57或S-101海图数据（>500KB，非mock）"
    echo "2. TSS要素: 需要从ENC中解析出TSS分道通航制要素"
    echo "3. 船舶参数: 需要完整的船舶尺度、吃水、转弯半径"
    echo "4. RTZ格式: 需要Schema文件和往返一致性验证"
    echo ""
    echo "详细报告: $OUT/REPORT.md"
    echo "JSON报告: $OUT/REPORT.json"
    exit 2
else
    echo "✅ 数据真实性门禁通过"
    echo ""
    echo "详细报告: $OUT/REPORT.md"
    echo "JSON报告: $OUT/REPORT.json"
    exit 0
fi