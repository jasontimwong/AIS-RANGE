import React, { useEffect, useRef } from 'react';
import { LonLat } from './CanvasMap';
import { lonLatToXY } from '../proj/mercator';

export interface AISTarget {
  mmsi: string;
  name: string;
  lat: number;
  lon: number;
  sog: number;
  cog: number;
  heading: number;
  ship_type: number;
  nav_status: number;
}

interface AISLayerProps {
  targets: AISTarget[];
  center: LonLat;
  zoom: number;
  width: number;
  height: number;
  visible: boolean;
}

// 船舶类型颜色
const getShipColor = (ship_type: number): string => {
  if (ship_type >= 60 && ship_type < 70) return '#FF6B6B';  // Passenger - 红色
  if (ship_type >= 70 && ship_type < 80) return '#4ECDC4';  // Cargo - 青色
  if (ship_type >= 80 && ship_type < 90) return '#FFD93D';  // Tanker - 黄色
  if (ship_type === 30) return '#95E77E';  // Fishing - 绿色
  return '#B8B8B8';  // Other - 灰色
};

// 航行状态符号
const getNavStatusSymbol = (nav_status: number): string => {
  switch(nav_status) {
    case 1: return '⚓';  // At anchor
    case 2: return '⚠️';  // Not under command
    case 7: return '🎣';  // Fishing
    default: return '';
  }
};

export const AISLayer: React.FC<AISLayerProps> = ({
  targets, center, zoom, width, height, visible
}) => {
  const canvasRef = useRef<HTMLCanvasElement>(null);

  // 使用与CanvasMap相同的坐标转换
  const projectToScreen = (lon: number, lat: number): [number, number] => {
    const pos = lonLatToXY(lon, lat, center[0], center[1], zoom, width, height);
    return [pos.x, pos.y];
  };

  useEffect(() => {
    if (!canvasRef.current || !visible) return;
    
    const canvas = canvasRef.current;
    const ctx = canvas.getContext('2d');
    if (!ctx) return;

    // 清除画布
    ctx.clearRect(0, 0, width, height);

    // 绘制每个AIS目标
    targets.forEach(target => {
      const [x, y] = projectToScreen(target.lon, target.lat);
      
      // 跳过屏幕外的目标
      if (x < -50 || x > width + 50 || y < -50 || y > height + 50) return;

      // 绘制船舶
      ctx.save();
      ctx.translate(x, y);
      ctx.rotate(target.heading * Math.PI / 180);

      // 船舶三角形
      const size = zoom > 10 ? 12 : 8;
      ctx.fillStyle = getShipColor(target.ship_type);
      ctx.beginPath();
      ctx.moveTo(0, -size);
      ctx.lineTo(-size/2, size);
      ctx.lineTo(size/2, size);
      ctx.closePath();
      ctx.fill();

      // 边框
      ctx.strokeStyle = '#000';
      ctx.lineWidth = 1;
      ctx.stroke();

      ctx.restore();

      // 速度矢量
      if (target.sog > 0.5) {
        const vectorLength = Math.min(target.sog * 3, 50);
        const endX = x + vectorLength * Math.sin(target.cog * Math.PI / 180);
        const endY = y - vectorLength * Math.cos(target.cog * Math.PI / 180);
        
        ctx.strokeStyle = 'rgba(255, 255, 255, 0.6)';
        ctx.lineWidth = 1;
        ctx.setLineDash([5, 5]);
        ctx.beginPath();
        ctx.moveTo(x, y);
        ctx.lineTo(endX, endY);
        ctx.stroke();
        ctx.setLineDash([]);
      }

      // 标签（缩放级别足够时显示）
      if (zoom > 10) {
        ctx.fillStyle = '#FFF';
        ctx.font = '10px monospace';
        ctx.fillText(target.name || target.mmsi, x + 15, y - 5);
        ctx.fillText(`${target.sog.toFixed(1)}kn`, x + 15, y + 5);
        
        // 航行状态符号
        const symbol = getNavStatusSymbol(target.nav_status);
        if (symbol) {
          ctx.font = '12px sans-serif';
          ctx.fillText(symbol, x - 20, y);
        }
      }
    });

  }, [targets, center, zoom, width, height, visible]);

  if (!visible) return null;

  return (
    <canvas
      ref={canvasRef}
      width={width}
      height={height}
      style={{
        position: 'absolute',
        top: 0,
        left: 0,
        pointerEvents: 'none',
        zIndex: 10  // 确保在地图上方
      }}
    />
  );
};