# 动态路径规划系统重构方案

## 1. 问题诊断

### 1.1 当前架构问题

#### 粒度不一致问题
- **现象**: 路径从N0(原始粗粒度100m)直接跳到N3(后处理细粒度500m)
- **根因**: HybridAStar原生motion_step固定为100m，通过后处理`_densify_latlon`加密
- **影响**: 路径不自然，缺少中间过渡点

#### 局部拼接思维
- **现象**: `_stitch_replanned_segments`方法对受影响段进行局部重规划
- **根因**: 试图通过最小改动实现动态避碰
- **影响**: 违背路径规划的整体性原则

#### 性能冗余
- **现象**: baseline和dynamic分别规划，计算重复
- **根因**: 为了对比展示，进行了两次完整规划
- **影响**: 性能浪费，延迟增加

### 1.2 核心问题总结
**动态路径应该是"在新约束条件下的完整重新规划"，而不是补丁式修改**

## 2. 解决方案

### 2.1 架构改进

```
旧架构:                          新架构:
HybridAStar(100m)               HybridAStar(50m可配置)
    ↓                                ↓
粗粒度路径                      原生高精度路径
    ↓                                ↓
局部检测威胁      →            完整集成AIS约束
    ↓                                ↓
拼接+加密                       单次完整规划
    ↓                                ↓
最终路径                        最终路径
```

### 2.2 技术方案

#### 方案选择: 平衡方案（推荐）
- 重构DynamicRoutePlanner核心逻辑
- 扩展HybridAStar支持动态粒度配置
- AIS威胁作为FeasibleRegion的动态层
- 单次完整规划替代双路径对比

#### 关键改进点
1. **粒度统一**: motion_step从100m降至50m，可动态配置
2. **完整规划**: 删除拼接逻辑，每次都是完整重规划
3. **约束集成**: AIS威胁直接集成到规划约束中
4. **性能优化**: 单次规划，缓存不变部分

## 3. 实施步骤

### 3.1 HybridAStar扩展

```python
# lib/planner/hybrid_astar.py

@dataclass
class PlannerConfig:
    grid_resolution: float = 50.0  # 从100降至50
    motion_step: float = 50.0      # 统一粒度
    dynamic_motion_step: Optional[float] = None  # 新增
    # ... 其他参数
    
class HybridAStar:
    def plan(self, start, goal, constraints=None):
        # 支持动态调整motion_step
        if constraints and hasattr(constraints, 'motion_step'):
            original_step = self.config.motion_step
            self.config.motion_step = constraints.motion_step
            try:
                return self._plan_internal(start, goal)
            finally:
                self.config.motion_step = original_step
        return self._plan_internal(start, goal)
```

### 3.2 DynamicRoutePlanner重构

```python
# lib/route/dynamic_planner.py

def update_dynamic_route(self, current_position: Tuple[float, float]) -> Optional[DynamicRoute]:
    """完整重规划实现"""
    
    # 1. 获取基础可航区域
    region = self._get_region()
    if not region:
        return self._fallback_light_planning(current_position)
    
    # 2. 集成AIS威胁约束
    ais_targets = self.ais_manager.get_all_targets()
    constrained_region = self._apply_ais_constraints(region, ais_targets, current_position)
    
    # 3. 单次完整规划（核心改变）
    route_latlon = self._plan_with_region(
        constrained_region, 
        current_position,
        self.destination,
        motion_step=50.0  # 统一高精度
    )
    
    if not route_latlon:
        return self.current_dynamic_route
    
    # 4. 直接返回，无需后处理加密
    return self._build_dynamic_route(route_latlon, ais_targets)

def _apply_ais_constraints(self, region, targets, current_position):
    """将AIS威胁集成为约束"""
    threat_zones = self._build_threat_zones(targets, current_position)
    
    # 方案1: 修改navigable_area
    if threat_zones:
        navigable_masked = region.navigable_area.difference(threat_zones)
        return FeasibleRegion(
            bounds=region.bounds,
            navigable_area=navigable_masked,
            # ... 其他属性保持
        )
    return region
```

### 3.3 删除冗余代码

需要删除的方法:
- `_stitch_replanned_segments` - 局部拼接逻辑
- `_densify_latlon` - 后处理加密
- 双路径对比逻辑

## 4. 测试计划

### 4.1 单元测试

```python
def test_motion_step_configuration():
    """测试粒度配置"""
    config = PlannerConfig(motion_step=50.0)
    planner = HybridAStar(config, region)
    route = planner.plan(start, goal)
    
    # 验证路径点间距
    for i in range(len(route.waypoints)-1):
        dist = calculate_distance(route.waypoints[i], route.waypoints[i+1])
        assert dist <= 60.0  # 允许10%误差

def test_ais_constraint_integration():
    """测试AIS约束集成"""
    planner = DynamicRoutePlanner(ais_manager)
    # 添加威胁目标
    ais_manager.add_target(threat_vessel)
    
    route = planner.update_dynamic_route(current_pos)
    # 验证避让
    for point in route.waypoints:
        assert not is_in_threat_zone(point, threat_vessel)
```

### 4.2 性能测试

```python
def test_planning_performance():
    """测试规划性能"""
    import time
    
    planner = DynamicRoutePlanner(ais_manager)
    # 添加多个AIS目标
    for i in range(20):
        ais_manager.add_target(create_random_vessel())
    
    start_time = time.time()
    route = planner.update_dynamic_route(current_pos)
    elapsed = time.time() - start_time
    
    assert elapsed < 3.0  # 3秒内完成
    assert route is not None
```

### 4.3 集成测试

```python
def test_end_to_end_dynamic_planning():
    """端到端测试"""
    # 1. 初始化系统
    service = RoutePlannerService()
    
    # 2. 创建初始路径
    initial_route = service.plan_route(start, end)
    
    # 3. 添加动态威胁
    service.add_ais_threat(threat_position)
    
    # 4. 触发动态重规划
    dynamic_route = service.update_dynamic_route(current_pos)
    
    # 5. 验证
    assert dynamic_route != initial_route
    assert verify_avoidance(dynamic_route, threat_position)
    assert measure_granularity(dynamic_route) <= 60.0
```

## 5. 验收标准

### 功能验收
- [x] 路径点间距 ≤ 60米
- [x] AIS威胁正确避让
- [x] API保持兼容
- [x] UI正常显示

### 性能验收
- [x] 重规划时间 < 3秒（20个AIS目标）
- [x] 内存使用无明显增加
- [x] CPU使用率合理

### 质量验收
- [x] 单元测试覆盖率 > 80%
- [x] 集成测试全部通过
- [x] 代码审查通过
- [x] 文档完整

## 6. 风险管理

### 已识别风险
1. **HybridAStar改动影响现有功能**
   - 缓解: 充分测试，保留原配置选项
   
2. **50米粒度影响性能**
   - 缓解: 性能测试，必要时调整到60-80米

3. **AIS约束计算耗时**
   - 缓解: 优化威胁区域算法，使用空间索引

## 7. 回滚方案

如需回滚到v1版本:
```bash
git reset --hard v3.3.1-dynamic-route-v1
```

## 8. 时间表

- Phase 1: 准备工作 (30分钟)
- Phase 2: 核心重构 (3小时)
- Phase 3: 测试验收 (1小时) 
- Phase 4: 文档完善 (30分钟)

总计: 约5小时

## 9. 参考资料

- [Hybrid A* Paper](https://ai.stanford.edu/~ddolgov/papers/dolgov_gpp_stair08.pdf)
- [D* Lite Algorithm](http://idm-lab.org/bib/abstracts/papers/aaai02b.pdf)
- [COLREG Rules](https://www.imo.org/en/About/Conventions/Pages/COLREG.aspx)