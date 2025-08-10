# S-124 航行警告映射（最小子集）
- 支持分类：`speed_limit`（限速）、`prohibited`（禁航区）
- 几何：Polygon（GeoJSON）
- 行为：限速 → 速度代价/硬约束；禁航区 → no-go 面
- 报告：clause_refs 标注来源（S-124 mock）与生效时间窗
