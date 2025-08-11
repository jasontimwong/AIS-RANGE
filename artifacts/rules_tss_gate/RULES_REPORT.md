# 规则覆盖度报告
## Rules Coverage Report

**总体覆盖**: 16/16 (100.0%)

### 必须规则 (Mandatory)

- ✅ **ECDIS.SAFETY_CONTOUR** - 安全等深线/浅水不可入
- ✅ **ECDIS.NOGO_OBSTACLE** - 危险物/禁航区避让
- ✅ **TSS.RULE10.LANE_FOLLOW** - 分道制车道内通行
- ✅ **TSS.RULE10.NO_SEP_ZONE** - 禁止穿越分隔区
- ✅ **SPD.LIMITS** - 限速区不超速
- ✅ **CPA.TCPA.THRESH** - 最小 CPA/TCPA 满足阈值
- ✅ **RTZ.IO.ROUNDTRIP** - RTZ 导出→导入一致

### COLREG规则

- ✅ **COLREG.RULE7** - 碰撞危险评估
- ✅ **COLREG.RULE8** - 避免碰撞措施
- ✅ **COLREG.RULE10** - 分道制
- ✅ **COLREG.RULE13** - 追越
- ✅ **COLREG.RULE14** - 对遇
- ✅ **COLREG.RULE15** - 交叉
- ✅ **COLREG.RULE16** - 让路船动作
- ✅ **COLREG.RULE17** - 直航船动作
- ✅ **COLREG.RULE19** - 能见度不良

### 可选规则 (Optional)

- ⭕ **UKC.MIN_CLEARANCE** - UKC≥阈值
- ⭕ **S102.CONSISTENCY** - 与 S-57 可行域一致
- ⭕ **S111.EFFECT** - 流场影响 ETA/代价可解释
- ⭕ **S124.APPLIED** - 警告生效并受检

## ✅ 无缺口

所有必须规则和COLREG规则均已覆盖。

---
*生成时间: planner*