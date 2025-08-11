#!/usr/bin/env python3
"""
规则缺口报告生成器
Rules Gap Report Generator

生成规则清单、检查覆盖度、生成补全模板
"""

import argparse
import yaml
import json
import os
import re
import sys
import textwrap
from pathlib import Path
from typing import Dict, List, Set, Any

# 默认规则清单
REQUIRED_DEFAULT = {
    "mandatory": [
        {"id": "ECDIS.SAFETY_CONTOUR", "std": "IMO MSC.232/MSC.530", "desc": "安全等深线/浅水不可入"},
        {"id": "ECDIS.NOGO_OBSTACLE", "std": "IMO/IEC/IHO", "desc": "危险物/禁航区避让"},
        {"id": "TSS.RULE10.LANE_FOLLOW", "std": "COLREG Rule 10", "desc": "分道制车道内通行"},
        {"id": "TSS.RULE10.NO_SEP_ZONE", "std": "COLREG Rule 10", "desc": "禁止穿越分隔区"},
        {"id": "SPD.LIMITS", "std": "S-124/地方规则", "desc": "限速区不超速"},
        {"id": "CPA.TCPA.THRESH", "std": "COLREG/公司策略", "desc": "最小 CPA/TCPA 满足阈值"},
        {"id": "RTZ.IO.ROUNDTRIP", "std": "IEC 61174/PAS", "desc": "RTZ 导出→导入一致"}
    ],
    "colreg": [
        {"id": "COLREG.RULE7", "std": "COLREG", "desc": "碰撞危险评估"},
        {"id": "COLREG.RULE8", "std": "COLREG", "desc": "避免碰撞措施"},
        {"id": "COLREG.RULE10", "std": "COLREG", "desc": "分道制"},
        {"id": "COLREG.RULE13", "std": "COLREG", "desc": "追越"},
        {"id": "COLREG.RULE14", "std": "COLREG", "desc": "对遇"},
        {"id": "COLREG.RULE15", "std": "COLREG", "desc": "交叉"},
        {"id": "COLREG.RULE16", "std": "COLREG", "desc": "让路船动作"},
        {"id": "COLREG.RULE17", "std": "COLREG", "desc": "直航船动作"},
        {"id": "COLREG.RULE19", "std": "COLREG", "desc": "能见度不良"}
    ],
    "optional": [
        {"id": "UKC.MIN_CLEARANCE", "std": "内部/公司", "desc": "UKC≥阈值"},
        {"id": "S102.CONSISTENCY", "std": "IHO S-102", "desc": "与 S-57 可行域一致"},
        {"id": "S111.EFFECT", "std": "IHO S-111", "desc": "流场影响 ETA/代价可解释"},
        {"id": "S124.APPLIED", "std": "IHO S-124", "desc": "警告生效并受检"}
    ]
}


def load_manifest(path: str) -> Dict:
    """加载规则清单"""
    if not path or not os.path.exists(path):
        return REQUIRED_DEFAULT
    try:
        with open(path, encoding="utf-8") as f:
            return yaml.safe_load(f) or REQUIRED_DEFAULT
    except Exception as e:
        print(f"Warning: Failed to load manifest: {e}", file=sys.stderr)
        return REQUIRED_DEFAULT


def get_unique_ids(manifest: Dict) -> List[str]:
    """获取所有唯一规则ID"""
    ids = []
    for category in ("mandatory", "colreg", "optional"):
        for item in manifest.get(category, []):
            ids.append(item["id"])
    return ids


def extract_from_clause_refs(plan_resp_path: str) -> Set[str]:
    """从规划响应中提取已覆盖的规则ID"""
    if not plan_resp_path or not os.path.exists(plan_resp_path):
        return set()
    
    try:
        with open(plan_resp_path, encoding="utf-8") as f:
            data = json.load(f)
    except Exception as e:
        print(f"Warning: Failed to load plan response: {e}", file=sys.stderr)
        return set()
    
    clause_refs = data.get("validation_report", {}).get("clause_refs", [])
    observed = set()
    
    # 映射策略：从clause_refs提取规则ID
    for clause in clause_refs:
        # 尝试多种ID字段
        rule_id = clause.get("id") or clause.get("rule_id")
        
        if not rule_id:
            # 根据标准和条款合成ID
            std = str(clause.get("standard", "")).strip().upper()
            clause_num = str(clause.get("clause", "")).strip().upper()
            
            # 特殊映射 - 更全面的映射规则
            if "COLREG" in std:
                if "RULE 7" in clause_num:
                    observed.add("COLREG.RULE7")
                elif "RULE 8" in clause_num:
                    observed.add("COLREG.RULE8")
                elif "RULE 10" in clause_num:
                    observed.add("COLREG.RULE10")
                    observed.add("TSS.RULE10.LANE_FOLLOW")
                elif "RULE 13" in clause_num:
                    observed.add("COLREG.RULE13")
                elif "RULE 14" in clause_num:
                    observed.add("COLREG.RULE14")
                elif "RULE 15" in clause_num:
                    observed.add("COLREG.RULE15")
                elif "RULE 16" in clause_num:
                    observed.add("COLREG.RULE16")
                elif "RULE 17" in clause_num:
                    observed.add("COLREG.RULE17")
                elif "RULE 19" in clause_num:
                    observed.add("COLREG.RULE19")
            elif "S-57" in std:
                if "TSSLPT" in clause_num:
                    observed.add("TSS.RULE10.LANE_FOLLOW")
                elif "TSS.NO_SEP_ZONE" in clause_num or "NO_SEP_ZONE" in clause_num:
                    observed.add("TSS.RULE10.NO_SEP_ZONE")
            elif "MSC.232" in std or "SAFETY_CONTOUR" in clause_num:
                observed.add("ECDIS.SAFETY_CONTOUR")
            elif "NOGO_OBSTACLE" in clause_num or ("IMO/IEC/IHO" in std and "OBSTACLE" in clause_num):
                observed.add("ECDIS.NOGO_OBSTACLE")
            elif "61174" in std or "RTZ" in clause_num:
                observed.add("RTZ.IO.ROUNDTRIP")
            elif "S-124" in std or "SPEED" in clause_num:
                observed.add("SPD.LIMITS")
            elif "CPA" in clause_num or "TCPA" in clause_num:
                observed.add("CPA.TCPA.THRESH")
            elif std and clause_num:
                rule_id = f"{std}.{clause_num}"
                observed.add(rule_id)
        else:
            observed.add(rule_id)
    
    return observed


def emit_stub(rule_id: str):
    """生成规则实现存根"""
    # 创建规则目录
    base = Path("lib/checks/rules")
    base.mkdir(parents=True, exist_ok=True)
    
    # 生成Python文件名
    file_name = rule_id.lower().replace(".", "_").replace("-", "_")
    py_file = base / f"{file_name}.py"
    
    if not py_file.exists():
        stub_content = textwrap.dedent(f'''\
            """
            Auto-generated stub for {rule_id}
            请补全逻辑与单测
            """
            from typing import Any, Dict, Optional
            
            
            def check(rule_input: Dict[str, Any]) -> Dict[str, Any]:
                """
                检查 {rule_id} 合规性
                
                Args:
                    rule_input: 包含路线、ENC数据、船舶参数等输入
                    
                Returns:
                    包含status、evidence、clause_refs的验证结果
                """
                # TODO: 实现 {rule_id} 的判定逻辑
                # 返回格式: {{"status": "COMPLIANT"/"FAIL"/"WARN", "evidence": ..., "clause_refs": [...]}}
                
                return {{
                    "status": "WARN",
                    "evidence": "STUB - Not yet implemented",
                    "clause_refs": [{{
                        "standard": "TODO",
                        "clause": "{rule_id}",
                        "status": "WARN",
                        "description": "Rule check not yet implemented"
                    }}]
                }}
            ''')
        py_file.write_text(stub_content, encoding="utf-8")
        print(f"  生成存根: {py_file}")
    
    # 生成测试文件
    test_dir = Path("tests/checks")
    test_dir.mkdir(parents=True, exist_ok=True)
    
    test_file = test_dir / f"test_{file_name}.py"
    if not test_file.exists():
        test_content = textwrap.dedent(f'''\
            """
            Test for {rule_id} rule check
            """
            import pytest
            
            
            def test_{file_name}_stub():
                """测试 {rule_id} 规则检查"""
                # TODO: 实现真实测试用例
                assert True  # 占位测试
            
            
            def test_{file_name}_compliant():
                """测试 {rule_id} 合规场景"""
                # TODO: 测试合规情况
                pass
            
            
            def test_{file_name}_violation():
                """测试 {rule_id} 违规场景"""
                # TODO: 测试违规情况
                pass
            ''')
        test_file.write_text(test_content, encoding="utf-8")
        print(f"  生成测试: {test_file}")


def generate_report(manifest: Dict, observed: Set[str], missing: List[str], 
                   covered: List[str], optional: List[str]) -> str:
    """生成覆盖度报告"""
    lines = []
    lines.append("# 规则覆盖度报告")
    lines.append("## Rules Coverage Report")
    lines.append("")
    
    # 统计
    total_required = len(manifest.get("mandatory", [])) + len(manifest.get("colreg", []))
    lines.append(f"**总体覆盖**: {len(covered)}/{total_required} ({len(covered)*100/total_required:.1f}%)")
    lines.append("")
    
    # 必须规则
    lines.append("### 必须规则 (Mandatory)")
    lines.append("")
    for rule in manifest.get("mandatory", []):
        status = "✅" if rule["id"] in observed else "❌"
        lines.append(f"- {status} **{rule['id']}** - {rule['desc']}")
    lines.append("")
    
    # COLREG规则
    lines.append("### COLREG规则")
    lines.append("")
    for rule in manifest.get("colreg", []):
        status = "✅" if rule["id"] in observed else "❌"
        lines.append(f"- {status} **{rule['id']}** - {rule['desc']}")
    lines.append("")
    
    # 可选规则
    lines.append("### 可选规则 (Optional)")
    lines.append("")
    for rule in manifest.get("optional", []):
        status = "✅" if rule["id"] in observed else "⭕"
        lines.append(f"- {status} **{rule['id']}** - {rule['desc']}")
    lines.append("")
    
    # 缺口汇总
    if missing:
        lines.append("## 缺口分析")
        lines.append("")
        lines.append(f"**缺失规则数**: {len(missing)}")
        lines.append("")
        for rule_id in missing:
            # 查找规则详情
            rule_info = None
            for cat in ("mandatory", "colreg"):
                for r in manifest.get(cat, []):
                    if r["id"] == rule_id:
                        rule_info = r
                        break
                if rule_info:
                    break
            
            if rule_info:
                lines.append(f"- [ ] **{rule_id}** ({rule_info['std']}) - {rule_info['desc']}")
            else:
                lines.append(f"- [ ] **{rule_id}**")
        lines.append("")
        lines.append("**建议**: 运行 `--emit-stubs` 生成实现模板")
    else:
        lines.append("## ✅ 无缺口")
        lines.append("")
        lines.append("所有必须规则和COLREG规则均已覆盖。")
    
    lines.append("")
    lines.append("---")
    lines.append(f"*生成时间: {Path.cwd().name}*")
    
    return "\n".join(lines)


def main():
    parser = argparse.ArgumentParser(description="规则缺口报告生成器")
    parser.add_argument("--init", action="store_true", help="初始化默认规则清单")
    parser.add_argument("--manifest", default="docs/compliance/required_rules.yaml",
                       help="规则清单文件路径")
    parser.add_argument("--plan-resp", default="artifacts/case_sf_tss/plan_resp_1.json",
                       help="规划响应文件路径")
    parser.add_argument("--out", help="输出报告路径")
    parser.add_argument("--emit-stubs", action="store_true", help="生成缺失规则的实现存根")
    args = parser.parse_args()
    
    # 初始化规则清单
    if args.init:
        manifest_path = Path(args.manifest)
        if not manifest_path.exists():
            manifest_path.parent.mkdir(parents=True, exist_ok=True)
            with open(manifest_path, "w", encoding="utf-8") as f:
                yaml.safe_dump(REQUIRED_DEFAULT, f, allow_unicode=True, 
                             sort_keys=False, default_flow_style=False)
            print(f"✅ 已生成规则清单: {manifest_path}")
        else:
            print(f"✅ 规则清单已存在: {manifest_path}")
        
        # 如果只是初始化，不需要继续执行
        if not args.out:
            sys.exit(0)
    
    # 如果不是init操作，则out参数是必须的
    if not args.init and not args.out:
        parser.error("--out is required when not using --init")
    
    # 加载规则清单
    manifest = load_manifest(args.manifest)
    
    # 获取必须规则ID集合
    required_ids = set()
    for cat in ("mandatory", "colreg"):
        for rule in manifest.get(cat, []):
            required_ids.add(rule["id"])
    
    # 从规划响应提取已覆盖规则
    observed = extract_from_clause_refs(args.plan_resp)
    
    # 计算缺口
    missing = sorted(required_ids - observed)
    covered = sorted(required_ids & observed)
    
    # 可选规则
    optional_ids = set()
    for rule in manifest.get("optional", []):
        optional_ids.add(rule["id"])
    optional = sorted(optional_ids)
    
    # 生成报告
    report = generate_report(manifest, observed, missing, covered, optional)
    
    # 写入报告
    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(report, encoding="utf-8")
    print(f"✅ 已生成报告: {out_path}")
    
    # 生成实现存根
    if args.emit_stubs and missing:
        print(f"\n生成 {len(missing)} 个规则存根:")
        for rule_id in missing:
            emit_stub(rule_id)
    
    # 门禁判定：有缺口则创建FAIL文件
    if missing:
        fail_path = out_path.parent / "FAIL"
        fail_path.write_text(f"rules-gap: {len(missing)} missing", encoding="utf-8")
        print(f"\n❌ 规则缺口: {len(missing)} 个规则未覆盖")
        sys.exit(1)
    else:
        print("\n✅ 规则覆盖: 完整")
        sys.exit(0)


if __name__ == "__main__":
    main()