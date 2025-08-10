# RTZ到S-421字段映射

## 核心字段映射

| RTZ字段 | S-421字段 | 说明 |
|---------|-----------|------|
| routeName | routeName | 航线名称 |
| routeAuthor | routeAuthor | 作者 |
| routeStatus | routeStatus | 状态 |
| waypoint.position | waypoint.position | 位置坐标 |
| waypoint.speed | waypoint.plannedSpeed | 计划速度 |
| waypoint.radius | waypoint.turnRadius | 转向半径 |
| waypoint.portsideXTD | waypoint.crossTrackDistancePort | 左舷XTD |
| waypoint.starboardXTD | waypoint.crossTrackDistanceStarboard | 右舷XTD |
| leg.geometryType | routeLeg.legGeometryType | 几何类型 |

## 扩展字段（Extensions）

非对称字段放入extensions元素：
- 规划器信息 (plannerExtension)
- 合规状态 (complianceExtension)
- 优化参数 (optimizationExtension)

## 验证要求

1. 最少2个航点
2. 航点ID唯一
3. 腿段引用有效
4. 坐标范围合法
