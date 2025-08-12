# ECDIS风格图层实现方案

## 一、核心改进项目

### 1. 颜色方案切换系统
```typescript
// 建议在CanvasMap.tsx中添加
const [colorScheme, setColorScheme] = useState<'DAY'|'DUSK'|'NIGHT'>('DAY');

// ECDIS标准颜色定义
const ECDIS_PALETTE = {
  DAY: {
    NODTA: '#d8d8d8',  // 无数据区域
    DEPVS: '#ffffff',  // 极浅水域(0-2m)
    DEPSH: '#dbeef7',  // 浅水域(2m-安全等深线)
    DEPMD: '#c6def7',  // 中等深度(安全等深线-2倍安全等深线)
    DEPDW: '#b5d6ef',  // 深水域(>2倍安全等深线)
    LANDA: '#ccb57b',  // 陆地区域
    LANDF: '#dec8a5',  // 前景陆地
    CSTLN: '#949494',  // 海岸线
    SNDG1: '#84ada5',  // 浅滩
    TSSCRS: '#ff6eb4', // 分道通航制
    RESARE: '#ff0000', // 限制区域
    OBSTRN: '#0000ff', // 障碍物
    WRECKS: '#000000', // 沉船
    LIGHTS: '#ffff00', // 灯光
    BUOYAG: '#ff0000', // 红色浮标
    BUOYBG: '#00ff00', // 绿色浮标
  },
  NIGHT: {
    NODTA: '#3f3f3f',
    DEPVS: '#5a5a5a',
    DEPSH: '#213139',
    DEPMD: '#182931',
    DEPDW: '#101821',
    LANDA: '#3f3919',
    LANDF: '#524a29',
    CSTLN: '#5a5a5a',
    // 夜间模式使用红色系保护夜视
    TSSCRS: '#8b0000',
    RESARE: '#8b0000',
    LIGHTS: '#ff4500',
  }
};
```

### 2. 安全等深线功能
```typescript
interface SafetySettings {
  safetyDepth: number;      // 安全水深(米)
  safetyContour: number;    // 安全等深线
  shallowContour: number;   // 浅水等深线
  deepContour: number;      // 深水等深线
  twoDeepContour: number;   // 两倍深水等深线
}

// 根据安全设置动态着色
function getDepthColor(depth: number, settings: SafetySettings, scheme: string) {
  const colors = ECDIS_PALETTE[scheme];
  if (depth < settings.shallowContour) return colors.DEPVS;
  if (depth < settings.safetyContour) return colors.DEPSH;
  if (depth < settings.deepContour) return colors.DEPMD;
  return colors.DEPDW;
}
```

### 3. 符号渲染系统
```typescript
// S-52 符号渲染
class ECDISSymbols {
  // 灯塔符号
  static drawLighthouse(ctx: CanvasRenderingContext2D, x: number, y: number, color: string) {
    ctx.save();
    ctx.fillStyle = color;
    ctx.strokeStyle = '#000000';
    ctx.lineWidth = 1;
    
    // 绘制塔身
    ctx.beginPath();
    ctx.moveTo(x - 4, y);
    ctx.lineTo(x - 2, y - 15);
    ctx.lineTo(x + 2, y - 15);
    ctx.lineTo(x + 4, y);
    ctx.closePath();
    ctx.fill();
    ctx.stroke();
    
    // 绘制光芒
    ctx.strokeStyle = '#ffff00';
    ctx.lineWidth = 2;
    for (let angle = 0; angle < 360; angle += 45) {
      const rad = angle * Math.PI / 180;
      ctx.beginPath();
      ctx.moveTo(x, y - 15);
      ctx.lineTo(x + Math.cos(rad) * 8, y - 15 + Math.sin(rad) * 8);
      ctx.stroke();
    }
    ctx.restore();
  }
  
  // 浮标符号
  static drawBuoy(ctx: CanvasRenderingContext2D, x: number, y: number, type: 'lateral'|'cardinal'|'special') {
    const colors = {
      lateral_port: '#ff0000',    // 左侧标(红)
      lateral_stbd: '#00ff00',    // 右侧标(绿)
      cardinal: '#ffff00',         // 方位标(黄黑)
      special: '#ffff00'           // 特殊标(黄)
    };
    
    // 实现浮标绘制...
  }
  
  // 沉船符号
  static drawWreck(ctx: CanvasRenderingContext2D, x: number, y: number, dangerous: boolean) {
    ctx.save();
    ctx.strokeStyle = dangerous ? '#ff0000' : '#000000';
    ctx.lineWidth = 2;
    
    // 绘制沉船符号(带叉的椭圆)
    ctx.beginPath();
    ctx.ellipse(x, y, 8, 5, 0, 0, Math.PI * 2);
    ctx.stroke();
    
    ctx.beginPath();
    ctx.moveTo(x - 6, y - 4);
    ctx.lineTo(x + 6, y + 4);
    ctx.moveTo(x - 6, y + 4);
    ctx.lineTo(x + 6, y - 4);
    ctx.stroke();
    ctx.restore();
  }
}
```

### 4. 图层管理优化
```typescript
// ECDIS标准图层分类
const ECDIS_LAYERS = {
  // BASE类别 - 始终显示
  BASE: [
    'coastline',      // 海岸线
    'safety_contour', // 安全等深线
    'isolated_danger',// 孤立危险物
    'buoy_lateral'    // 侧面标志
  ],
  
  // STANDARD类别 - 标准显示
  STANDARD: [
    'depth_contours', // 其他等深线
    'text_important', // 重要文字
    'buoy_cardinal',  // 方位标
    'traffic_lanes',  // 航道
    'restricted_area' // 限制区域
  ],
  
  // OTHER类别 - 可选显示
  OTHER: [
    'spot_soundings', // 点测深
    'submarine_cable',// 海底电缆
    'pipeline',       // 管道
    'anchorage',      // 锚地
    'small_text'      // 小字标注
  ]
};
```

### 5. 具体实现步骤

#### 第一阶段：基础ECDIS样式
1. 实现三种颜色方案切换（日/黄昏/夜）
2. 更新当前地理渲染使用ECDIS色彩
3. 添加深度数据渲染（如果有）

#### 第二阶段：安全功能
1. 实现安全等深线设置界面
2. 根据安全设置动态着色水深区域
3. 危险区域自动高亮警告

#### 第三阶段：符号系统
1. 实现S-52基础符号库
2. 添加助航标志渲染
3. 实现文字标注系统

#### 第四阶段：高级功能
1. 查询功能（点击获取要素信息）
2. 告警系统（接近危险区域）
3. 航线检查（检测航线是否通过危险区域）

## 二、立即可实现的改进

### 1. 添加ECDIS颜色切换按钮
```typescript
// 在App.tsx中添加
<select onChange={(e) => mapRef.current?.setColorScheme(e.target.value)}>
  <option value="DAY">日间模式</option>
  <option value="DUSK">黄昏模式</option>
  <option value="NIGHT">夜间模式</option>
</select>
```

### 2. 改进现有地理渲染
```typescript
// 使用ECDIS标准颜色替换当前颜色
function drawGeography(ctx, width, height, center, zoom, colorScheme = 'DAY') {
  const colors = ECDIS_PALETTE[colorScheme];
  
  // 海洋背景
  ctx.fillStyle = colors.DEPDW;
  ctx.fillRect(0, 0, width, height);
  
  // 陆地
  ctx.fillStyle = colors.LANDA;
  ctx.strokeStyle = colors.CSTLN;
  // ... 绘制陆地
}
```

### 3. 添加网格和坐标显示
```typescript
// 经纬度网格（ECDIS标准要求）
function drawGrid(ctx, width, height, viewport, colorScheme) {
  const colors = ECDIS_PALETTE[colorScheme];
  ctx.strokeStyle = colors.CSTLN;
  ctx.globalAlpha = 0.3;
  ctx.lineWidth = 0.5;
  
  // 绘制经纬度网格
  // 显示坐标值
}
```

## 三、数据需求

要实现完整的ECDIS功能，需要以下数据：

1. **水深数据**（等深线、测深点）
2. **助航标志**（灯塔、浮标位置和属性）
3. **航道信息**（推荐航线、分道通航制）
4. **危险物**（沉船、礁石、障碍物）
5. **港口设施**（码头、锚地、引航点）

## 四、参考资源

- IHO S-52: ECDIS显示规范
- IHO S-57: ENC数据格式
- IHO S-101: 新一代ENC产品规范
- OpenSeaMap: 开源海图数据
- NOAA ENC: 美国官方电子海图

## 五、预期效果

实现后将具备：
- 符合IMO/IHO标准的专业海图显示
- 三种光照条件下的优化显示
- 安全航行辅助功能
- 标准化的符号和颜色系统