# 数据真实性门禁系统 Data Real Gate System

## 概述

数据真实性门禁是一个自动化验证系统，用于确保旗舰CASE（旧金山TSS）使用真实的海事数据，符合IMO/IHO国际标准要求。

## 系统组成

### 1. 门禁脚本 (`scripts/data_real_gate.sh`)
- 解析场景配置和特性开关
- 生成数据谱系（data provenance）
- 调用校验器进行验证
- 输出人类可读报告

### 2. 校验器 (`tools/data_real_gate.py`)
- 执行详细的数据真实性检查
- 验证必须项和可选项
- 生成Markdown和JSON格式报告
- 返回PASS/FAIL状态

### 3. 数据谱系Schema (`schemas/data_provenance.v1.json`)
- 定义数据谱系的标准格式
- 确保数据追踪的一致性
- 支持CI/CD集成

### 4. RTZ Schema (`schemas/rtz_schema.json`)
- IEC 61174:2015标准规范
- 验证RTZ文件格式
- 支持往返一致性测试

## 必须项验证 (Required Items)

### 1. ENC数据 ✅
- **要求**: 真实的S-57或S-101海图数据
- **条件**: 
  - 文件大小 > 500KB
  - 非mock/sample/fixture路径
  - 来自官方源（NOAA/IHO/HO）
- **验证**: 路线区域覆盖 ≥ 95%

### 2. TSS要素 ✅
- **要求**: 分道通航制要素存在
- **条件**:
  - 从ENC解析出TSSLPT/TSEZNE等要素
  - 验证报告包含COLREG Rule 10条款
  - 路线与TSS有空间关系
- **验证**: 在航道内且不穿越分隔区

### 3. 船舶模型 ✅
- **要求**: 完整的船舶参数
- **条件**:
  - 船长 > 30m
  - 船宽 > 5m
  - 吃水 > 2m
  - 转弯半径 > 0.2nm
- **验证**: 参数在合理范围内

### 4. RTZ互操作 ✅
- **要求**: 标准格式支持
- **条件**:
  - RTZ Schema文件存在
  - 导入/导出往返一致
  - 哈希值匹配
- **验证**: IEC 61174合规

## 可选项验证 (Optional Items)

### S-102 水深栅格 ⭕
- 官方HDF5格式优先
- Mock数据给警告但可接受

### S-111 表层流 ⭕
- 官方NetCDF/GRIB格式优先
- Mock数据给警告但可接受

### S-124 航行警告 ⭕
- 官方VTS/HO数据优先
- Mock数据给警告但可接受

### S-104 潮汐/水位 ⭕
- 官方WaterML格式优先
- 未使用不影响通过

## 使用方法

### 1. 运行验证
```bash
# 验证旧金山TSS场景
./scripts/data_real_gate.sh scenarios/case_sf_tss.yaml

# 验证合成场景（参考用）
./scripts/data_real_gate.sh scenarios/case_synth.yaml
```

### 2. 查看报告
```bash
# 人类可读报告
cat artifacts/data_gate/REPORT.md

# 机器可读报告
cat artifacts/data_gate/REPORT.json

# 失败标记（如存在）
ls artifacts/data_gate/FAIL
```

### 3. CI/CD集成
```yaml
# GitHub Actions示例
- name: Data Real Gate Check
  run: |
    ./scripts/data_real_gate.sh scenarios/case_sf_tss.yaml
```

## 补齐真实数据指南

### 1. 获取NOAA ENC数据
```bash
# 下载旧金山湾海图
wget https://charts.noaa.gov/ENCs/US5CA12M.zip
unzip US5CA12M.zip -d datasets/enc/US5CA12M/
```

### 2. 更新场景配置
```yaml
enc:
  s57_path: "datasets/enc/US5CA12M/US5CA12M.000"
  source: "NOAA"
```

### 3. 添加RTZ往返测试
```bash
# 在E2E测试中包含RTZ验证
./scripts/run_case_sf_tss.sh
```

### 4. 替换Mock数据（可选）
- S-102: 从IHO获取高分辨率水深
- S-111: 从NOAA获取洋流数据
- S-124: 从VTS获取实时警告

## 验证结果解读

### PASS ✅
- 所有必须项通过
- 可以用于生产环境
- 满足IMO/IHO标准

### FAIL ❌
- 存在必须项未通过
- 需要补充真实数据
- 查看报告了解详情

### WARN ⚠️
- 可选项使用mock数据
- 不影响基本功能
- 建议替换为真实数据

## 常见问题

### Q: ENC文件太小被判定为mock？
A: 确保使用完整的NOAA ENC文件（通常>1MB），不要使用样例或裁剪版本。

### Q: TSS验证失败？
A: 检查validation_report中是否包含COLREG Rule 10相关条款，确保路线经过TSS区域。

### Q: RTZ往返不一致？
A: 运行完整的E2E测试生成rtz_roundtrip.json文件，确保导入导出功能正常。

### Q: 如何处理可选项警告？
A: 可选项警告不影响通过，但建议在生产环境使用真实数据以获得最佳效果。

## 扩展支持

### 添加新的必须项
1. 在`required_real`列表中添加项目
2. 在校验器中实现检查函数
3. 更新文档说明要求

### 支持新的数据格式
1. 在Schema中添加数据类型
2. 实现格式验证逻辑
3. 更新场景配置模板

## 合规声明

本系统符合以下国际标准：
- IMO MSC.232(82) ECDIS性能标准
- IHO S-57 电子海图数据传输标准
- IEC 61174:2015 RTZ航线交换格式
- COLREG Rule 10 TSS分道通航制度

---

**版本**: 1.0.0  
**更新日期**: 2025-08-11  
**维护者**: ECDIS Team