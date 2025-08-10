# S-102 适配映射（最小子集）
- 输入：`datasets/s102/mock_s102_grid.csv`（lon, lat, depth_m）
- 输出：内部深度栅格（行优先，lat 从大到小或文档声明一致）
- 规则：
  - 安全等深线阈值 `safety_depth_m` → `to_no_go_mask(depth)`
  - 与 S-57 DEPARE/等深线的一致性，以面积差 ≤ 2% 为合格（报告差异热图）
