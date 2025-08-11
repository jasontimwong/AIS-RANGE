# 变更日志 Changelog

所有重要变更都会记录在此文件中。

## [3.0.0] - 2025-08-11

### 🎉 主要更新 Major Updates
- **规则引擎完整实现** - 16个IMO/COLREG规则100%覆盖
- **真实TSS验证** - 基于NOAA ENC数据的精确几何验证
- **数据真实性门禁** - 完整的IMO/IHO标准合规验证

### ✨ 新增功能 Added
- 实现13个缺失的COLREG和ECDIS规则
  - COLREG Rule 7 - 碰撞危险评估
  - COLREG Rule 8 - 避免碰撞措施
  - COLREG Rule 13 - 追越
  - COLREG Rule 14 - 对遇
  - COLREG Rule 15 - 交叉
  - COLREG Rule 16 - 让路船动作
  - COLREG Rule 17 - 直航船动作
  - COLREG Rule 19 - 能见度不良
  - ECDIS.NOGO_OBSTACLE - 危险物避让
  - TSS.RULE10.NO_SEP_ZONE - 禁止穿越分隔区
  - SPD.LIMITS - 速度限制
  - CPA.TCPA.THRESH - CPA/TCPA阈值
  - RTZ.IO.ROUNDTRIP - RTZ往返一致性

- TSS几何验证系统
  - 从真实ENC提取TSS几何数据
  - 基于Shapely的精确几何计算
  - 车道覆盖率分析
  - 分隔区穿越检测
  - 边界裕度计算

- 数据真实性验证框架
  - ENC S-57数据验证
  - TSS要素检查
  - RTZ格式验证
  - 船舶参数验证

- 自动化验证流程
  - 一键运行完整验证脚本
  - 规则覆盖度报告生成
  - TSS合规报告生成

### 🔧 改进 Changed
- 升级规则映射算法，支持多种标准格式
- 优化TSS边界裕度计算逻辑
- 改进规则缺口检测机制
- 增强数据验证流程

### 📁 新增文件 New Files
```
lib/checks/rules/        # 13个新规则实现
├── colreg_rule7.py
├── colreg_rule8.py
├── colreg_rule13-19.py
├── cpa_tcpa_thresh.py
├── ecdis_nogo_obstacle.py
├── spd_limits.py
└── tss_rule10_no_sep_zone.py

tools/
├── rules_gap_report.py  # 规则覆盖度分析工具
├── tss_geovalidate.py   # TSS几何验证工具
└── data_real_gate.py    # 数据真实性验证工具

scripts/
├── rules_tss_gate_all.sh  # 总控验证脚本
└── data_real_gate.sh      # 数据验证脚本

data/tss/
└── sf_bay_tss.json      # 旧金山湾TSS几何数据
```

### 📊 验证结果 Validation Results
- **规则覆盖**: 16/16 (100%) ✅
- **TSS合规**: 全部通过 ✅
- **数据验证**: 真实NOAA数据 ✅
- **门禁状态**: 完全通过 ✅

---

## [2.0.0] - 2025-08-10

### ✨ 新增功能 Added
- FastAPI REST服务实现
- React前端UI界面
- WebSocket实时更新
- E2E测试框架
- 旧金山TSS场景验证

### 🔧 改进 Changed
- 重构Hybrid A*算法
- 优化路径规划性能
- 改进碰撞检测逻辑

---

## [1.0.0] - 2025-08-01

### ✨ 初始版本 Initial Release
- 基础路径规划算法
- 简单规则验证
- 命令行界面
- 基础测试套件

---

## 版本命名规则 Versioning

本项目遵循[语义化版本](https://semver.org/lang/zh-CN/)规范：

- **主版本号(MAJOR)**: 不兼容的API修改
- **次版本号(MINOR)**: 向下兼容的功能性新增
- **修订号(PATCH)**: 向下兼容的问题修正

当前版本: **3.0.0** - 完整合规版