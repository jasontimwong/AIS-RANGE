"""
风险评估器 - 综合评估碰撞风险并生成避让建议
"""

from typing import List, Dict, Optional, Tuple
from dataclasses import dataclass
from enum import Enum
from lib.ais import AISTarget, NavStatus
from lib.ais.cpa_calculator import AISCPACalculator, CPAResult

class EncounterType(Enum):
    """遭遇态势类型"""
    HEAD_ON = "对遇"
    CROSSING_GIVE_WAY = "交叉让路"
    CROSSING_STAND_ON = "交叉直航"
    OVERTAKING = "追越"
    OVERTAKEN = "被追越"
    SAFE = "安全"

@dataclass
class RiskAssessment:
    """风险评估结果"""
    target: AISTarget
    cpa_result: CPAResult
    encounter_type: EncounterType
    recommended_action: str
    priority: int  # 1最高

class AISRiskAssessor:
    """AIS风险评估器"""
    
    def __init__(self):
        self.cpa_calculator = AISCPACalculator()
        
    def assess_risks(self, own_lat: float, own_lon: float, own_sog: float, own_cog: float,
                    targets: List[AISTarget]) -> List[RiskAssessment]:
        """评估所有目标的风险"""
        assessments = []
        
        # 计算所有CPA
        cpa_results = AISCPACalculator.calculate_multiple_cpa(
            own_lat, own_lon, own_sog, own_cog, targets
        )
        
        # 创建目标字典
        target_dict = {t.mmsi: t for t in targets}
        
        # 评估每个目标
        for cpa_result in cpa_results:
            target = target_dict[cpa_result.target_mmsi]
            
            # 判断遭遇态势
            encounter = self._classify_encounter(own_cog, cpa_result.bearing, target.cog)
            
            # 生成建议
            action = self._recommend_action(encounter, cpa_result, target)
            
            # 确定优先级
            priority = self._calculate_priority(cpa_result, encounter, target)
            
            assessment = RiskAssessment(
                target=target,
                cpa_result=cpa_result,
                encounter_type=encounter,
                recommended_action=action,
                priority=priority
            )
            
            assessments.append(assessment)
        
        # 按优先级排序
        assessments.sort(key=lambda x: x.priority)
        
        return assessments
    
    def _classify_encounter(self, own_cog: float, bearing: float, target_cog: float) -> EncounterType:
        """判断遭遇态势（COLREG规则）"""
        
        # 计算相对方位
        relative_bearing = (bearing - own_cog) % 360
        
        # 计算航向差
        heading_diff = abs((target_cog - own_cog + 180) % 360 - 180)
        
        # 对遇判断（Rule 14）
        if heading_diff > 170 and relative_bearing < 10 or relative_bearing > 350:
            return EncounterType.HEAD_ON
        
        # 追越判断（Rule 13）
        if 112.5 < relative_bearing < 247.5:  # 目标在正横后
            if heading_diff < 45:  # 航向相近
                return EncounterType.OVERTAKING
        elif relative_bearing < 67.5 or relative_bearing > 292.5:  # 本船在目标正横后
            if heading_diff < 45:
                return EncounterType.OVERTAKEN
        
        # 交叉判断（Rule 15）
        if 10 < relative_bearing < 112.5:  # 目标在右舷
            return EncounterType.CROSSING_GIVE_WAY
        elif 247.5 < relative_bearing < 350:  # 目标在左舷
            return EncounterType.CROSSING_STAND_ON
        
        return EncounterType.SAFE
    
    def _recommend_action(self, encounter: EncounterType, cpa_result: CPAResult, 
                         target: AISTarget) -> str:
        """根据COLREG规则推荐避让行动"""
        
        if cpa_result.risk_level == "SAFE":
            return "保持航向航速"
        
        # 特殊船舶状态检查
        if target.nav_status in [NavStatus.NOT_UNDER_COMMAND, 
                                 NavStatus.RESTRICTED_MANEUVERABILITY]:
            return f"避让受限船舶，建议向{'右' if cpa_result.bearing < 180 else '左'}转向"
        
        actions = {
            EncounterType.HEAD_ON: "向右转向避让（COLREG Rule 14）",
            EncounterType.CROSSING_GIVE_WAY: "从目标船尾通过，向右转向或减速（COLREG Rule 15）",
            EncounterType.CROSSING_STAND_ON: "保持航向航速，密切监视（COLREG Rule 17）",
            EncounterType.OVERTAKING: "从任一舷追越，保持安全距离（COLREG Rule 13）",
            EncounterType.OVERTAKEN: "保持航向航速（COLREG Rule 13）",
            EncounterType.SAFE: "保持航向航速"
        }
        
        base_action = actions.get(encounter, "评估态势")
        
        # 添加紧急程度
        if cpa_result.risk_level == "HIGH" and cpa_result.tcpa < 6:
            base_action = "⚠️ 紧急！" + base_action
        
        return base_action
    
    def _calculate_priority(self, cpa_result: CPAResult, encounter: EncounterType, 
                          target: AISTarget) -> int:
        """计算处理优先级（1最高）"""
        
        # 基础优先级
        priority = 100
        
        # 风险等级影响
        risk_scores = {"HIGH": 0, "MEDIUM": 20, "LOW": 40, "SAFE": 60}
        priority += risk_scores.get(cpa_result.risk_level, 60)
        
        # TCPA影响
        if cpa_result.tcpa != float('inf'):
            priority += min(cpa_result.tcpa, 30)
        
        # 遭遇态势影响
        encounter_scores = {
            EncounterType.HEAD_ON: -10,
            EncounterType.CROSSING_GIVE_WAY: -5,
            EncounterType.OVERTAKING: 5,
            EncounterType.CROSSING_STAND_ON: 10,
            EncounterType.OVERTAKEN: 15,
            EncounterType.SAFE: 50
        }
        priority += encounter_scores.get(encounter, 0)
        
        # 特殊状态船舶
        if target.nav_status in [NavStatus.NOT_UNDER_COMMAND, 
                                 NavStatus.RESTRICTED_MANEUVERABILITY]:
            priority -= 20
        
        return max(1, int(priority))