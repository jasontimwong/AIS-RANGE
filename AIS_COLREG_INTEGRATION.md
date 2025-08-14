# AIS与COLREG动态避碰系统集成文档

## 系统概述

本系统实现了完整的基于AIS（船舶自动识别系统）数据和COLREG（国际海上避碰规则）的动态路径规划功能，能够实时检测碰撞风险并生成符合国际海事规则的避让路径。

## 核心功能

### 1. AIS数据集成
- **实时数据接收**: 通过WebSocket接收AIS目标数据
- **多目标跟踪**: 同时跟踪多个船舶目标
- **数据解析**: 解析MMSI、位置、航速、航向等关键信息

### 2. 风险评估系统
- **CPA/TCPA计算**: 最接近点和到达时间计算
- **风险分级**:
  - HIGH: CPA < 0.5nm, TCPA < 12min
  - MEDIUM: CPA < 1.0nm, TCPA < 20min
  - LOW: CPA < 2.0nm, TCPA < 30min
- **遭遇态势识别**: 对遇、交叉、追越等情况判断

### 3. COLREG避让规则
实现的规则包括：
- **Rule 13**: 追越（Overtaking）
- **Rule 14**: 对遇（Head-on）
- **Rule 15**: 交叉（Crossing）
- **Rule 16**: 让路船行动（Give-way）
- **Rule 17**: 直航船行动（Stand-on）

### 4. 动态路径规划
- **自动避让点生成**: 根据COLREG规则生成避让航路点
- **路径优化**: 确保避让路径安全且高效
- **实时更新**: 每5秒更新一次路径评估

## 技术架构

### 后端组件
```
lib/
├── ais/                    # AIS系统核心
│   ├── __init__.py         # AIS目标数据结构
│   ├── manager.py          # AIS管理器
│   ├── cpa_calculator.py   # CPA/TCPA计算
│   ├── risk_assessor.py    # 风险评估器
│   └── ais_simulator_data.py # 模拟AIS数据
├── route/
│   ├── avoidance_algorithms.py # COLREG避让算法
│   └── dynamic_planner.py      # 动态路径规划器
```

### 前端组件
```
ui/src/
├── App.tsx                 # 主应用组件
├── components/
│   ├── CanvasMap.tsx      # 地图渲染组件
│   └── AISLayer.tsx       # AIS图层
├── hooks/
│   └── useAISData.ts      # AIS数据钩子
```

## API接口

### 初始化动态路径
```
POST /api/route/initialize
{
  "waypoints": [
    {"lat": 31.23, "lon": 121.508},
    {"lat": 31.0, "lon": 122.0}
  ]
}
```

### 获取动态路径
```
GET /api/route/dynamic?current_lat=31.23&current_lon=121.508
```

### AIS目标查询
```
GET /api/ais/targets?lat=31.23&lon=121.508&range_nm=100
```

### WebSocket连接
```
ws://localhost:8000/ws/ais
```

## 使用指南

### 1. 启动系统
```bash
# 启动后端服务
python3 service/app.py

# 启动前端开发服务器
cd ui && npm run dev
```

### 2. 启用动态避让
1. 在UI中勾选"启用AIS显示"
2. 勾选"启用动态路径规划"
3. 系统将自动检测威胁并生成避让路径

### 3. 查看结果
- **蓝色虚线**: 原始规划路径
- **绿色实线**: 动态避让路径
- **红色图标**: 高风险AIS目标
- **黄色图标**: 中风险AIS目标

## 关键算法

### CPA计算
```python
def calculate_cpa(own_lat, own_lon, own_sog, own_cog, 
                  target_lat, target_lon, target_sog, target_cog):
    # 转换为笛卡尔坐标
    # 计算相对速度
    # 求解最小距离点
    return cpa_distance, tcpa
```

### 遭遇态势判断
```python
def classify_encounter(own_cog, bearing, target_cog):
    relative_bearing = (bearing - own_cog) % 360
    heading_diff = abs((target_cog - own_cog + 180) % 360 - 180)
    
    if heading_diff > 170:  # 对遇
        return EncounterType.HEAD_ON
    elif 10 < relative_bearing < 112.5:  # 交叉让路
        return EncounterType.CROSSING_GIVE_WAY
    # ... 其他情况
```

### 避让动作生成
```python
def generate_avoidance_action(encounter_type):
    if encounter_type == HEAD_ON:
        return turn_right(15)  # 向右转15度
    elif encounter_type == CROSSING_GIVE_WAY:
        return turn_right(20)  # 向右转20度
    # ... 其他规则
```

## 性能指标
- **更新频率**: 5秒/次
- **最大跟踪目标**: 100个
- **计算延迟**: <100ms
- **WebSocket延迟**: <50ms

## 安全考虑
- 所有避让动作符合COLREG国际规则
- 考虑船舶动力学限制
- 保持最小安全距离
- 优先级处理多目标威胁

## 未来改进
- [ ] 集成真实AIS数据源
- [ ] 考虑天气和海况影响
- [ ] 优化多目标避让策略
- [ ] 添加避让动作回放功能
- [ ] 支持更多COLREG规则

## 版本历史
- v3.3.0 (2025-08-12): 初始版本，实现基本COLREG避让功能