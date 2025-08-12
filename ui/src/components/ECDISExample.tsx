// ECDIS颜色方案集成示例
import React, { useState } from 'react';
import { ECDIS_PALETTE, ColorScheme, getDepthColor, DEFAULT_SAFETY_SETTINGS } from '../utils/ecdisColors';

// 示例：如何在CanvasMap中使用ECDIS颜色
export function useECDISColors() {
  const [colorScheme, setColorScheme] = useState<ColorScheme>('DAY');
  const [safetySettings, setSafetySettings] = useState(DEFAULT_SAFETY_SETTINGS);
  
  // 获取当前颜色方案
  const colors = ECDIS_PALETTE[colorScheme];
  
  // 地理渲染函数改进示例
  const drawGeographyECDIS = (
    ctx: CanvasRenderingContext2D,
    width: number,
    height: number,
    geoData: any
  ) => {
    // 1. 海洋背景（使用深水颜色）
    ctx.fillStyle = colors.DEPDW;
    ctx.fillRect(0, 0, width, height);
    
    // 2. 如果有水深数据，绘制不同深度区域
    // （这里是示例，实际需要真实水深数据）
    if (geoData.depths) {
      geoData.depths.forEach((depthArea: any) => {
        ctx.fillStyle = getDepthColor(
          depthArea.depth,
          safetySettings,
          colorScheme
        );
        // 绘制深度区域...
      });
    }
    
    // 3. 绘制陆地（使用ECDIS陆地色）
    ctx.fillStyle = colors.LANDA;
    ctx.strokeStyle = colors.CSTLN;
    ctx.lineWidth = 1;
    
    // 绘制陆地多边形...
    
    // 4. 绘制安全等深线（高亮显示）
    if (safetySettings.safetyContour) {
      ctx.strokeStyle = colorScheme === 'NIGHT' ? colors.CHRED : colors.CHBLK;
      ctx.lineWidth = 2;
      ctx.setLineDash([5, 3]);
      // 绘制安全等深线...
      ctx.setLineDash([]);
    }
    
    // 5. 绘制危险区域
    ctx.fillStyle = colors.RESARE;
    ctx.globalAlpha = 0.3;
    // 绘制限制区域...
    ctx.globalAlpha = 1.0;
  };
  
  // TSS分道通航制渲染改进
  const drawTSSECDIS = (
    ctx: CanvasRenderingContext2D,
    tssData: any
  ) => {
    // 使用ECDIS标准颜色
    ctx.strokeStyle = colors.TSSCRS;
    ctx.fillStyle = colors.TSSCRS;
    ctx.globalAlpha = 0.2;
    
    // 绘制航道...
    
    // 分隔带
    ctx.strokeStyle = colors.TSSLPT;
    ctx.setLineDash([10, 5]);
    // 绘制分隔带...
    
    ctx.globalAlpha = 1.0;
    ctx.setLineDash([]);
  };
  
  // 助航标志渲染
  const drawAidsToNavigationECDIS = (
    ctx: CanvasRenderingContext2D,
    x: number,
    y: number,
    type: string
  ) => {
    switch (type) {
      case 'light':
        // 灯塔 - 黄色星形
        ctx.fillStyle = colors.LIGHTS;
        ctx.strokeStyle = colors.CHBLK;
        drawStar(ctx, x, y, 8, 4);
        break;
        
      case 'buoy_red':
        // 红色浮标
        ctx.fillStyle = colors.BUOYAR;
        ctx.strokeStyle = colors.CHBLK;
        drawDiamond(ctx, x, y, 6);
        break;
        
      case 'buoy_green':
        // 绿色浮标
        ctx.fillStyle = colors.BUOYAG;
        ctx.strokeStyle = colors.CHBLK;
        drawTriangle(ctx, x, y, 6);
        break;
        
      case 'wreck':
        // 沉船
        ctx.strokeStyle = colors.WRECKS;
        drawWreckSymbol(ctx, x, y);
        break;
    }
  };
  
  return {
    colorScheme,
    setColorScheme,
    colors,
    safetySettings,
    setSafetySettings,
    drawGeographyECDIS,
    drawTSSECDIS,
    drawAidsToNavigationECDIS
  };
}

// 绘制星形（灯塔）
function drawStar(ctx: CanvasRenderingContext2D, x: number, y: number, r1: number, r2: number) {
  ctx.beginPath();
  for (let i = 0; i < 10; i++) {
    const radius = i % 2 === 0 ? r1 : r2;
    const angle = (Math.PI / 5) * i - Math.PI / 2;
    const px = x + Math.cos(angle) * radius;
    const py = y + Math.sin(angle) * radius;
    if (i === 0) ctx.moveTo(px, py);
    else ctx.lineTo(px, py);
  }
  ctx.closePath();
  ctx.fill();
  ctx.stroke();
}

// 绘制菱形（浮标）
function drawDiamond(ctx: CanvasRenderingContext2D, x: number, y: number, size: number) {
  ctx.beginPath();
  ctx.moveTo(x, y - size);
  ctx.lineTo(x + size, y);
  ctx.lineTo(x, y + size);
  ctx.lineTo(x - size, y);
  ctx.closePath();
  ctx.fill();
  ctx.stroke();
}

// 绘制三角形（浮标）
function drawTriangle(ctx: CanvasRenderingContext2D, x: number, y: number, size: number) {
  ctx.beginPath();
  ctx.moveTo(x, y - size);
  ctx.lineTo(x + size, y + size);
  ctx.lineTo(x - size, y + size);
  ctx.closePath();
  ctx.fill();
  ctx.stroke();
}

// 绘制沉船符号
function drawWreckSymbol(ctx: CanvasRenderingContext2D, x: number, y: number) {
  ctx.lineWidth = 2;
  // 椭圆
  ctx.beginPath();
  ctx.ellipse(x, y, 8, 5, 0, 0, Math.PI * 2);
  ctx.stroke();
  // 交叉
  ctx.beginPath();
  ctx.moveTo(x - 6, y - 4);
  ctx.lineTo(x + 6, y + 4);
  ctx.moveTo(x - 6, y + 4);
  ctx.lineTo(x + 6, y - 4);
  ctx.stroke();
}

// UI控制组件示例
export function ECDISControls({ onColorSchemeChange }: { onColorSchemeChange: (scheme: ColorScheme) => void }) {
  return (
    <div className="ecdis-controls" style={{
      position: 'absolute',
      top: '10px',
      right: '10px',
      background: 'rgba(255,255,255,0.9)',
      padding: '10px',
      borderRadius: '5px',
      boxShadow: '0 2px 5px rgba(0,0,0,0.3)'
    }}>
      <h4 style={{ margin: '0 0 10px 0' }}>ECDIS显示模式</h4>
      
      <div style={{ marginBottom: '10px' }}>
        <label>
          <input
            type="radio"
            name="colorScheme"
            value="DAY"
            defaultChecked
            onChange={(e) => onColorSchemeChange(e.target.value as ColorScheme)}
          />
          <span style={{ marginLeft: '5px' }}>☀️ 日间模式</span>
        </label>
      </div>
      
      <div style={{ marginBottom: '10px' }}>
        <label>
          <input
            type="radio"
            name="colorScheme"
            value="DUSK"
            onChange={(e) => onColorSchemeChange(e.target.value as ColorScheme)}
          />
          <span style={{ marginLeft: '5px' }}>🌅 黄昏模式</span>
        </label>
      </div>
      
      <div style={{ marginBottom: '10px' }}>
        <label>
          <input
            type="radio"
            name="colorScheme"
            value="NIGHT"
            onChange={(e) => onColorSchemeChange(e.target.value as ColorScheme)}
          />
          <span style={{ marginLeft: '5px' }}>🌙 夜间模式</span>
        </label>
      </div>
      
      <hr style={{ margin: '10px 0' }} />
      
      <h4 style={{ margin: '10px 0' }}>安全设置</h4>
      
      <div style={{ fontSize: '12px' }}>
        <div>安全水深: 10m</div>
        <div>安全等深线: 10m</div>
        <div style={{ color: '#ff0000' }}>⚠️ 浅水警告: &lt;5m</div>
      </div>
    </div>
  );
}