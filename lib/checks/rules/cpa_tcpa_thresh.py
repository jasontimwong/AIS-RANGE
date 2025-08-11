"""
CPA/TCPA Threshold Check
最小CPA/TCPA阈值检查
"""
from typing import Any, Dict, Optional


def check(rule_input: Dict[str, Any]) -> Dict[str, Any]:
    """
    检查 CPA.TCPA.THRESH 合规性
    """
    # 获取CPA/TCPA数据
    cpa_tcpa = rule_input.get("cpa_tcpa", {})
    thresholds = rule_input.get("cpa_tcpa_thresholds", {})
    
    # 默认阈值
    min_cpa_threshold = thresholds.get("min_cpa_nm", 1.0)
    min_tcpa_threshold = thresholds.get("min_tcpa_min", 12.0)
    
    # 获取实际值
    actual_cpa = cpa_tcpa.get("min_cpa_nm", float('inf'))
    actual_tcpa = cpa_tcpa.get("min_tcpa_min", float('inf'))
    
    # 如果没有其他船只
    if actual_cpa == float('inf'):
        return {
            "status": "COMPLIANT",
            "evidence": "No other vessels - CPA/TCPA not applicable",
            "clause_refs": [{
                "standard": "Company Policy",
                "clause": "CPA/TCPA Thresholds",
                "status": "COMPLIANT",
                "description": "No close quarters situations"
            }]
        }
    
    # 检查阈值
    cpa_ok = actual_cpa >= min_cpa_threshold
    tcpa_ok = actual_tcpa >= min_tcpa_threshold
    
    if cpa_ok and tcpa_ok:
        return {
            "status": "COMPLIANT",
            "evidence": f"CPA={actual_cpa:.1f}nm (≥{min_cpa_threshold}), TCPA={actual_tcpa:.1f}min (≥{min_tcpa_threshold})",
            "clause_refs": [{
                "standard": "COLREG/Company Policy",
                "clause": "CPA/TCPA Thresholds",
                "status": "COMPLIANT",
                "description": "Safe passing distances maintained"
            }]
        }
    else:
        violations = []
        if not cpa_ok:
            violations.append(f"CPA {actual_cpa:.1f}nm < {min_cpa_threshold}nm")
        if not tcpa_ok:
            violations.append(f"TCPA {actual_tcpa:.1f}min < {min_tcpa_threshold}min")
        
        return {
            "status": "FAIL",
            "evidence": f"Threshold violations: {', '.join(violations)}",
            "clause_refs": [{
                "standard": "COLREG/Company Policy",
                "clause": "CPA/TCPA Thresholds",
                "status": "FAIL",
                "description": "Minimum safe distances violated"
            }]
        }
