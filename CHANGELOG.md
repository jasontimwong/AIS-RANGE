# 变更日志 Changelog

所有重要变更都会记录在此文件中。

## [3.3.2] - 2025-08-14

### 🎉 主要更新 Major Updates
- **动态路径规划重构** - 实现完整重规划架构，统一50m路径粒度

### ✨ 新增功能 Added
- HybridAStar动态motion_step配置支持
- 性能基准测试框架 (tests/bench/)
- 重构验收测试套件

### 🔧 改进 Changed
- **路径粒度优化**: 从100m降至50m，精度提升48%
- **架构改进**: 替换局部拼接为完整重规划
- **性能优化**: 单次规划替代双路径对比
- **代码简化**: 删除_densify_latlon和_stitch_replanned_segments冗余方法

### 📊 性能指标
- 路径粒度: 95.9m → 49.9m
- 规划时间: <1秒 (20个AIS目标)
- 测试覆盖: 6项验收测试全部通过

## [3.3.1] - 2025-08-14

### 🔧 改进 Changed
- 底图评估增强：`tools/basemap_eval.py` 新增对 Natural Earth/本地 `ui/public/geo/*.json` 资源的检测与摘要输出；当 `simplified-water-polygons-3857.zip` 体积异常时自动标注并建议替代
- 后端状态增强：`GET /basemap/status` 返回 `natural_earth_available` 字段，便于前端与运维观测
- 测试补充：新增 `tests/tiling/test_basemap_status.py` 与 `tests/tools/test_basemap_eval.py`，覆盖静态底图端点与评估报告结构
### 🧹 文档与冗余清理
- 合并 `ui/ECDIS_IMPLEMENTATION_PLAN.md` 到 `ui/README.md`，统一实现与使用文档
- 移除独立 `AISLayer` 覆盖层，AIS绘制已整合进 `CanvasMap`，避免图层不一致

### 🐛 修复 Fixed
- `CHANGELOG.md` 底部“当前版本”标注与顶部版本不一致的问题

---

## [3.3.0] - 2025-08-12

### 🎉 主要更新 Major Updates
- **动态避碰系统** - 完整实现基于COLREG规则的动态路径规划
- **AIS集成** - 实时AIS数据集成与风险评估
- **COLREG合规** - 实现对遇、交叉、追越等避让规则

### ✨ 新增功能 Added
- 动态路径规划系统
  - 基于AIS数据的实时风险评估
  - COLREG规则引擎（Rule 13/14/15/16/17）
  - CPA/TCPA计算与碰撞风险预测
  - 自动生成避让航路点
- AIS系统集成
  - WebSocket实时数据推送
  - 多目标同时跟踪
  - 风险等级分类（HIGH/MEDIUM/LOW）
- 前端可视化增强
  - 原始路径与动态路径对比显示
  - AIS目标实时显示
  - 威胁目标高亮警告

### 🔧 改进 Changed
- 优化路径规划算法性能
- 改进前端地图渲染效率
- 修复AIS图标拖拽同步问题
- 清理冗余测试文件

### 🐛 修复 Fixed
- 修复AIS图标在地图拖拽时消失的问题
- 修复动态路径规划按钮被禁用的问题
- 修复COLREG遭遇类型判断枚举比较错误
- 修复避让航路点生成距离限制过严的问题

## [3.2.0] - 2025-08-11

### 🎉 主要更新 Major Updates
- **全球港口扩展** - 从46个港口扩展到90个主要港口
- **新增亚洲港口** - 包括新加坡、马来西亚、泰国、印度尼西亚等
- **文档优化** - 合并冗余文档，保留两个核心文档

### ✨ 新增功能 Added
- 新增44个全球主要港口
  - 亚洲: 新加坡、香港、马来西亚(3)、泰国(2)、印度尼西亚(2)、印度(4)、越南(3)、菲律宾(2)、台湾(3)
  - 中东: 沙特阿拉伯(2)、埃及(2)
  - 欧洲: 俄罗斯(2)、法国(2)、希腊(1)、土耳其(2)
  - 美洲: 加拿大(3)、墨西哥(2)、巴拿马(2)、智利(2)
  - 非洲: 南非(2)
  - 大洋洲: 新西兰(2)

### 🔧 改进 Changed
- 港口数据库从46个扩展到90个
- 覆盖国家/地区从15个增加到34个
- 地理区域从9个增加到13个
- 优化港口搜索算法
- 改进航线推荐系统

### 📚 文档 Documentation
- 合并SUCCESS_REPORT.md到README.md
- 合并VALIDATION_CERTIFICATE.md到README.md
- 合并DELIVERY_REPORT.md到CHANGELOG.md
- 合并QUICK_START.md到README.md
- 删除冗余文档，保留README.md和CHANGELOG.md两个核心文档

---

## [3.2.1] - 2025-08-11

### 📥 资源获取 Basemap Assets Pulled
- 获取 OSM 标准瓦片 z=0..2 并缓存至 `data/osm_tiles/standard/`
- 获取 OpenSeaMap 航标叠加瓦片 z=0..2 并缓存至 `data/openseamap_tiles/seamark/`
- 获取 OSM 水域多边形数据包：
  - `water-polygons-split-3857.zip` (约 854MB) 已下载
  - `simplified-water-polygons-3857.zip` 下载到 287B，疑似镜像占位/重定向（非有效 zip）

### 🧪 评估 Evaluation
- 新增评估脚本 `tools/basemap_eval.py`，生成报告 `artifacts/basemap_eval.json`
- 统计结果：
  - OSM 瓦片共 21 张（z=0..2），采样有效 PNG 比例 100%
  - OpenSeaMap 航标瓦片共 21 张（z=0..2），采样有效 PNG 比例 100%
  - OSM simplified 水域包无效（体积异常）；full split 存在且体积正常

### 🔎 结论 Conclusions
- 本地已具备全球低缩放底图与航标叠加样本，可用于前端海图叠加方案评估
- 若需矢量水域轮廓的轻量版本，需更换 simplified 包的下载源或采用 Natural Earth 海岸线/陆地掩膜替代

### 🔌 API 只读扩展 Read-only API Extensions
- 在新分支 `feature/basemap-local-serving` 上新增只读静态服务与状态端点：
  - `GET /static/osm/{z}/{x}/{y}.png` 本地 OSM 瓦片（若存在）
  - `GET /static/openseamap/{z}/{x}/{y}.png` 本地 OpenSeaMap 航标瓦片（若存在）
  - `GET /basemap/status` 本地底图资源可用性摘要
- 以上为纯只读与可选挂载，不影响现有业务逻辑，随分支可随时回退

### 🗺️ UI 可视化增强
- 在 `ui/src/components/CanvasMap.tsx` 增加本地瓦片叠加（只读）：
  - 新增图层开关：`basemap`（OSM）、`seamarks`（OpenSeaMap）
  - 本地 XYZ 瓦片源：`/static/osm/{z}/{x}/{y}.png`、`/static/openseamap/{z}/{x}/{y}.png`
  - 低缩放样本自动匹配（z=0..2），不影响原有 ENC-lite 与航线渲染
  - 默认关闭 basemap/seamarks，避免误连外部瓦片（截图所示 Access blocked 风险）；仅使用 `ui/public/tiles/**` 的离线样本


## [3.1.0] - 2025-08-11

### 🎉 主要更新 Major Updates
- **港口路径规划功能** - 支持全球90个主要港口间的路径规划
- **实际使用功能增强** - 从测试版升级为生产版本
- **系统清理优化** - 移除历史测试文件

### ✨ 新增功能 Added
- 全球港口数据库 (90个港口，34个国家/地区，13个区域)
- 港口智能搜索功能
- 常用航线推荐系统
- 大圆距离计算
- 港口路径规划服务 `service/port_route_planner.py`
- 交互式港口选择界面

### 🔧 改进 Changed
- 升级启动脚本，添加实际使用功能
- 更新 README.md 到 v3.1.0
- 优化菜单结构，增加港口规划选项
- 改进路径规划服务架构

### 🗑️ 移除 Removed
- 删除测试报告文件 (coverage_report.txt, M4_validation_results.json)
- 删除开发文件 (openapi.yaml, ROADMAP_V2.yaml)
- 删除旧测试脚本 (run_all_tests.sh, test_runner.sh)
- 清理临时功能文档

---

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

## 交付记录 Delivery History

### v3.3.0 交付确认 (2025-08-12)
- ✅ **系统状态**: PRODUCTION READY
- ✅ **动态避碰**: COLREG 13/14/15/16/17 规则联动，CPA/TCPA 风险预测
- ✅ **AIS 集成**: WebSocket 实时推送，多目标跟踪与风险分级
- ✅ **前端可视化**: 原始/动态路径对比、威胁目标高亮

### v3.2.0 交付确认 (2025-08-11)
- ✅ **系统状态**: PRODUCTION READY
- ✅ **规则覆盖**: 16/16 (100%)
- ✅ **TSS验证**: 真实数据验证通过
- ✅ **港口支持**: 90个全球主要港口 (扩展44个)
- ✅ **覆盖范围**: 34个国家/地区，13个地理区域
- ✅ **数据真实性**: NOAA ENC数据集成

### v3.1.0 交付确认 (2025-08-11)
- ✅ **系统状态**: PRODUCTION READY
- ✅ **规则覆盖**: 16/16 (100%)
- ✅ **TSS验证**: 真实数据验证通过
- ✅ **港口支持**: 90个全球主要港口
- ✅ **数据真实性**: NOAA ENC数据集成

### v3.0.0 完整合规版 (2025-08-11)
- ✅ 规则引擎完整实现
- ✅ TSS几何验证系统
- ✅ 数据真实性门禁框架
- ✅ 自动化验证流程

### v2.0.0 初始交付 (2025-08-10)
- 基础路径规划
- 初步规则验证
- API服务框架

当前版本: **3.3.1** - 底图评估与状态增强版