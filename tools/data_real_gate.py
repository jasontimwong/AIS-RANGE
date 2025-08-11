#!/usr/bin/env python3
"""
数据真实性门禁校验器
Data Real Gate Validator

验证旗舰CASE（旧金山TSS）使用真实数据
按IMO/IHO标准要求检查必须项
"""

import argparse
import json
import yaml
import os
import re
import sys
import hashlib
from pathlib import Path
from typing import Dict, List, Any, Optional

# 状态图标
OK = "✅"
FAIL = "❌"
WARN = "⚠️"
INFO = "ℹ️"


def is_mock_path(path: Optional[str]) -> bool:
    """检查路径是否包含mock/synthetic/sample等标识"""
    if not path:
        return True
    mock_patterns = r"(mock|synthetic|sample|fixture|test|demo|example)"
    return bool(re.search(mock_patterns, str(path), re.IGNORECASE))


def is_file_real(path: Optional[str], min_size: int = 500_000) -> bool:
    """
    检查文件是否为真实数据
    - 文件存在
    - 非mock路径
    - 大小超过阈值
    """
    if not path or not os.path.isfile(path):
        return False
    if is_mock_path(path):
        return False
    return os.path.getsize(path) >= min_size


def load_json_safe(path: str) -> Dict:
    """安全加载JSON文件"""
    try:
        return json.loads(Path(path).read_text(encoding="utf-8"))
    except Exception as e:
        print(f"Warning: Failed to load JSON from {path}: {e}", file=sys.stderr)
        return {}


def compute_hash(data: Any) -> Optional[str]:
    """计算数据的哈希值（前16位）"""
    if not data:
        return None
    try:
        json_str = json.dumps(data, sort_keys=True)
        return hashlib.sha256(json_str.encode()).hexdigest()[:16]
    except:
        return None


def check_enc_data(datasets: Dict[str, Dict], must_pass: bool) -> Dict:
    """
    检查ENC数据真实性
    S-57或S-101必须有一个真实存在
    """
    s57 = datasets.get("ENC_S57", {})
    s101 = datasets.get("ENC_S101", {})
    
    s57_real = is_file_real(s57.get("path"), min_size=500_000)
    s101_real = is_file_real(s101.get("path"), min_size=500_000)
    enc_ok = s57_real or s101_real
    
    details = []
    if s57_real:
        details.append(f"S-57: {Path(s57['path']).name} ({s57.get('size', 0)/1024/1024:.1f}MB)")
    if s101_real:
        details.append(f"S-101: {Path(s101['path']).name} ({s101.get('size', 0)/1024/1024:.1f}MB)")
    
    if not enc_ok:
        details.append("需要真实的S-57或S-101海图数据（>500KB，非mock）")
    
    return {
        "item": "ENC",
        "status": "PASS" if enc_ok else "FAIL",
        "detail": " | ".join(details) if details else "未找到ENC数据",
        "required": must_pass,
        "passed": enc_ok
    }


def check_tss_elements(plan_response_path: str, must_pass: bool) -> Dict:
    """
    检查TSS要素存在性
    从规划响应的验证报告中查找TSS/Rule 10相关条款
    """
    plan = load_json_safe(plan_response_path)
    validation_report = plan.get("validation_report", {})
    clause_refs = validation_report.get("clause_refs", [])
    
    # 查找TSS相关条款
    tss_patterns = r"TSS|Traffic\s+Separation|Rule\s*10|COLREG.*10|分道|通航"
    tss_hits = []
    for clause in clause_refs:
        clause_str = json.dumps(clause)
        if re.search(tss_patterns, clause_str, re.IGNORECASE):
            tss_hits.append(clause)
    
    tss_ok = len(tss_hits) > 0
    
    details = []
    if tss_ok:
        details.append(f"发现{len(tss_hits)}条TSS/Rule 10相关验证")
        for hit in tss_hits[:2]:  # 显示前2条
            std = hit.get("standard", "")
            clause = hit.get("clause", "")
            details.append(f"  • {std} {clause}")
    else:
        details.append("未找到TSS分道通航制验证证据")
    
    return {
        "item": "TSS",
        "status": "PASS" if tss_ok else "FAIL",
        "detail": "\n".join(details),
        "required": must_pass,
        "passed": tss_ok
    }


def check_vessel_model(ship_model: Dict, must_pass: bool) -> Dict:
    """
    检查船舶模型参数真实性
    参数必须在合理范围内
    """
    length_m = ship_model.get("length_m") or 0
    beam_m = ship_model.get("beam_m") or 0
    draft_m = ship_model.get("draft_m") or 0
    turn_radius_nm = ship_model.get("min_turn_radius_nm") or 0
    
    # 合理性检查
    checks = {
        "长度": (length_m > 30, f"{length_m:.1f}m"),
        "宽度": (beam_m > 5, f"{beam_m:.1f}m"),
        "吃水": (draft_m > 2, f"{draft_m:.1f}m"),
        "转弯半径": (turn_radius_nm > 0.2, f"{turn_radius_nm:.2f}nm")
    }
    
    all_ok = all(check[0] for check in checks.values())
    
    details = []
    for name, (ok, value) in checks.items():
        emoji = "✓" if ok else "✗"
        details.append(f"{emoji} {name}: {value}")
    
    return {
        "item": "VESSEL",
        "status": "PASS" if all_ok else "FAIL",
        "detail": " | ".join(details),
        "required": must_pass,
        "passed": all_ok
    }


def check_rtz_interop(datasets: Dict[str, Dict], plan_response_path: str, must_pass: bool) -> Dict:
    """
    检查RTZ互操作性
    - Schema文件存在
    - 往返一致性验证
    """
    rtz_schema = datasets.get("RTZ_SCHEMA", {})
    schema_exists = is_file_real(rtz_schema.get("path"), min_size=1000)
    
    # 尝试加载往返测试结果
    plan_dir = Path(plan_response_path).parent
    roundtrip_path = plan_dir / "rtz_roundtrip.json"
    
    roundtrip_ok = False
    hash_match = False
    
    if roundtrip_path.exists():
        plan = load_json_safe(plan_response_path)
        roundtrip = load_json_safe(str(roundtrip_path))
        
        route1 = plan.get("waypoints", [])
        route2 = roundtrip.get("waypoints", [])
        
        if route1 and route2:
            hash1 = compute_hash(route1)
            hash2 = compute_hash(route2)
            hash_match = (hash1 == hash2) and hash1 is not None
            roundtrip_ok = hash_match
    
    rtz_ok = schema_exists and roundtrip_ok
    
    details = []
    details.append(f"Schema: {'存在' if schema_exists else '缺失'}")
    details.append(f"往返测试: {'一致' if roundtrip_ok else '不一致或未测试'}")
    
    return {
        "item": "RTZ",
        "status": "PASS" if rtz_ok else "FAIL",
        "detail": " | ".join(details),
        "required": must_pass,
        "passed": rtz_ok
    }


def check_optional_datasets(datasets: Dict[str, Dict]) -> List[Dict]:
    """
    检查可选数据集
    S-102, S-111, S-124, S-104等
    """
    optional_types = ["S102", "S111", "S124", "S104"]
    results = []
    
    for dtype in optional_types:
        dataset = datasets.get(dtype, {})
        path = dataset.get("path")
        
        if not path:
            # 未使用是可接受的
            results.append({
                "item": dtype,
                "status": "INFO",
                "detail": "未使用（可选）",
                "required": False,
                "passed": True
            })
        elif is_mock_path(path):
            # Mock数据给警告
            results.append({
                "item": dtype,
                "status": "WARN",
                "detail": f"检测到mock/样例数据: {Path(path).name}",
                "required": False,
                "passed": True  # 可选项不影响通过
            })
        else:
            size_mb = dataset.get("size", 0) / 1024 / 1024
            results.append({
                "item": dtype,
                "status": "PASS",
                "detail": f"真实数据: {Path(path).name} ({size_mb:.1f}MB)",
                "required": False,
                "passed": True
            })
    
    return results


def generate_report(checks: List[Dict], scenario_info: Dict) -> Dict:
    """生成完整报告"""
    # 分类统计
    required_checks = [c for c in checks if c.get("required", False)]
    optional_checks = [c for c in checks if not c.get("required", False)]
    
    # 必须项是否全部通过
    all_required_pass = all(c.get("passed", False) for c in required_checks)
    
    # 统计
    stats = {
        "total": len(checks),
        "required": len(required_checks),
        "optional": len(optional_checks),
        "passed": len([c for c in checks if c.get("passed", False)]),
        "failed": len([c for c in checks if not c.get("passed", False) and c.get("required", False)]),
        "warned": len([c for c in checks if c.get("status") == "WARN"])
    }
    
    return {
        "scenario": scenario_info.get("scenario_id", "UNKNOWN"),
        "scenario_name": scenario_info.get("scenario_name", "Unknown"),
        "timestamp": Path.cwd().name,
        "checks": checks,
        "statistics": stats,
        "summary": {
            "must_pass": ["ENC", "TSS", "VESSEL", "RTZ"],
            "result": "PASS" if all_required_pass else "FAIL",
            "message": "所有必须项通过" if all_required_pass else "存在必须项未通过"
        }
    }


def render_markdown(report: Dict) -> str:
    """渲染Markdown格式报告"""
    lines = []
    
    # 标题
    lines.append(f"# 数据真实性门禁报告 Data-Real Gate Report")
    lines.append("")
    lines.append(f"**场景**: {report['scenario']} - {report['scenario_name']}")
    lines.append(f"**结果**: {report['summary']['result']}")
    lines.append("")
    
    # 必须项
    lines.append("## 必须项 (Required)")
    lines.append("")
    for check in report["checks"]:
        if check.get("required", False):
            emoji = OK if check["status"] == "PASS" else FAIL
            lines.append(f"### {emoji} {check['item']} — {check['status']}")
            lines.append(check["detail"])
            lines.append("")
    
    # 可选项
    lines.append("## 可选项 (Optional)")
    lines.append("")
    for check in report["checks"]:
        if not check.get("required", False):
            emoji = {
                "PASS": OK,
                "FAIL": FAIL,
                "WARN": WARN,
                "INFO": INFO
            }.get(check["status"], "")
            lines.append(f"- {emoji} **{check['item']}**: {check['detail']}")
    
    lines.append("")
    lines.append("---")
    
    # 统计
    stats = report["statistics"]
    lines.append("## 统计 Statistics")
    lines.append("")
    lines.append(f"- 总检查项: {stats['total']}")
    lines.append(f"- 必须项: {stats['required']} (通过: {stats['passed'] - (stats['total'] - stats['required'])})")
    lines.append(f"- 可选项: {stats['optional']} (警告: {stats['warned']})")
    lines.append("")
    
    # 总结
    lines.append("## 总结 Summary")
    lines.append("")
    if report["summary"]["result"] == "PASS":
        lines.append(f"{OK} **{report['summary']['message']}**")
        lines.append("")
        lines.append("系统已验证使用真实数据，满足IMO/IHO标准要求。")
    else:
        lines.append(f"{FAIL} **{report['summary']['message']}**")
        lines.append("")
        lines.append("请补充以下真实数据：")
        for check in report["checks"]:
            if check.get("required") and not check.get("passed"):
                lines.append(f"- {check['item']}: {check['detail']}")
    
    return "\n".join(lines)


def main():
    """主入口"""
    parser = argparse.ArgumentParser(description="数据真实性门禁校验器")
    parser.add_argument("--provenance", required=True, help="数据谱系YAML文件")
    parser.add_argument("--out", required=True, help="输出报告路径（.md）")
    parser.add_argument("--strict", action="store_true", help="严格模式（可选项也必须通过）")
    args = parser.parse_args()
    
    # 加载数据谱系
    try:
        provenance = yaml.safe_load(open(args.provenance, encoding="utf-8"))
    except Exception as e:
        print(f"Error loading provenance file: {e}", file=sys.stderr)
        sys.exit(1)
    
    # 准备数据
    datasets = {d["type"]: d for d in provenance.get("datasets", [])}
    ship_model = provenance.get("ship_model", {})
    required_real = provenance.get("required_real", ["ENC", "TSS", "VESSEL", "RTZ"])
    
    # 执行检查
    checks = []
    
    # 1. ENC数据
    checks.append(check_enc_data(datasets, "ENC" in required_real))
    
    # 2. TSS要素
    plan_response_path = provenance.get("plan_response_path", "")
    if plan_response_path and os.path.exists(plan_response_path):
        checks.append(check_tss_elements(plan_response_path, "TSS" in required_real))
    else:
        checks.append({
            "item": "TSS",
            "status": "FAIL",
            "detail": "规划响应文件不存在，无法验证TSS",
            "required": "TSS" in required_real,
            "passed": False
        })
    
    # 3. 船舶模型
    checks.append(check_vessel_model(ship_model, "VESSEL" in required_real))
    
    # 4. RTZ互操作
    checks.append(check_rtz_interop(datasets, plan_response_path, "RTZ" in required_real))
    
    # 5. 可选数据集
    checks.extend(check_optional_datasets(datasets))
    
    # 生成报告
    report = generate_report(checks, provenance)
    
    # 输出文件
    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    
    # Markdown报告
    md_content = render_markdown(report)
    out_path.write_text(md_content, encoding="utf-8")
    
    # JSON报告
    json_path = out_path.with_suffix(".json")
    json_path.write_text(
        json.dumps(report, ensure_ascii=False, indent=2),
        encoding="utf-8"
    )
    
    # 失败标记
    if report["summary"]["result"] == "FAIL":
        fail_path = out_path.parent / "FAIL"
        fail_path.write_text("fail", encoding="utf-8")
        print(f"{FAIL} Data-Real Gate: FAIL", file=sys.stderr)
        sys.exit(1)
    else:
        print(f"{OK} Data-Real Gate: PASS")
        sys.exit(0)


if __name__ == "__main__":
    main()