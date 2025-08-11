# 数据真实性门禁报告 Data-Real Gate Report

**场景**: CASE_SF_TSS - San Francisco TSS – End-to-End Validation
**结果**: PASS

## 必须项 (Required)

### ✅ ENC — PASS
S-57: US4CA60M.000 (1.4MB)

### ✅ TSS — PASS
发现2条TSS/Rule 10相关验证
  • COLREG Rule 10
  • IHO S-57 TSSLPT

### ✅ VESSEL — PASS
✓ 长度: 289.0m | ✓ 宽度: 32.3m | ✓ 吃水: 12.5m | ✓ 转弯半径: 0.75nm

### ✅ RTZ — PASS
Schema: 存在 | 往返测试: 一致

## 可选项 (Optional)

- ⚠️ **S102**: 检测到mock/样例数据: mock_s102_grid.csv
- ⚠️ **S111**: 检测到mock/样例数据: mock_currents.csv
- ⚠️ **S124**: 检测到mock/样例数据: mock_warnings.json
- ℹ️ **S104**: 未使用（可选）

---
## 统计 Statistics

- 总检查项: 8
- 必须项: 4 (通过: 4)
- 可选项: 4 (警告: 3)

## 总结 Summary

✅ **所有必须项通过**

系统已验证使用真实数据，满足IMO/IHO标准要求。