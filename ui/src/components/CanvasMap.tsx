import React, { useEffect, useImperativeHandle, useRef, useState } from "react";
import { lonLatToXY, xyToLonLat, Viewport } from "../proj/mercator";
import { ECDIS_PALETTE, ColorScheme, getDepthColor, DEFAULT_SAFETY_SETTINGS } from "../utils/ecdisColors";

export type LonLat = [number, number];

interface AISTarget {
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

  type Props = { 
  enc: any; 
  route: LonLat[]; 
  dynamicRoute?: LonLat[];
  dynamicRouteEnabled?: boolean;
    avoidancePoints?: LonLat[];
  aisTargets?: AISTarget[];
  aisEnabled?: boolean;
  style?: React.CSSProperties;
  onViewChange?: (center: LonLat, zoom: number) => void;
};

export type MapRef = { 
  toggle(layer: string, on: boolean): void; 
  zoomTo(bounds: [LonLat, LonLat]): void;
  centerOnRoute(): void;
  zoomToFit(): void;
  setColorScheme(scheme: ColorScheme): void;
};

export const CanvasMap = React.forwardRef<MapRef, Props>((props, ref) => {
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const animationFrameRef = useRef<number | null>(null);
  const [colorScheme, setColorSchemeState] = useState<ColorScheme>('DAY');
  const bathymetryData = useRef<any>(null);
  const seamarksData = useRef<any>(null);
  // Prefer local static tiles served by Vite from /public (no API dependency)
  // Use Vite's BASE_URL environment variable for correct path resolution
  // In development: BASE_URL = '/ui/' (from vite.config.js)
  // In production: BASE_URL will be set according to deployment configuration
  const BASE_URL = import.meta.env.BASE_URL || '/';
  const TILE_BASE = `${BASE_URL.endsWith('/') ? BASE_URL.slice(0, -1) : BASE_URL}/tiles`;
  
  const layers = useRef<Record<string, boolean>>({
    geography: true,  // 真实地理环境图层
    bathymetry: true, // 水深等深线
    seamark: true,    // 助航标志
    localbase: false,  // 改为默认关闭
    basemap: false,
    seamarks: false,
    enc: true, 
    route: true, 
    tss: true, 
    s124: true
  });
  
  const vp = useRef<Viewport>({
    center: [0.015, 0.0075], // 居中显示示例区域
    zoom: 12, 
    width: 0, 
    height: 0, 
    dpr: window.devicePixelRatio || 1,
  });
  
  const state = useRef({
    drag: false, 
    last: [0, 0] as [number, number],
    needsRedraw: true
  });

  // Simple in-memory tile cache
  const tileCache = useRef<Map<string, HTMLImageElement>>(new Map());
  
  // GeoJSON地理数据缓存
  const geoData = useRef<any>(null);

  useImperativeHandle(ref, () => ({
    toggle: (k, on) => { 
      layers.current[k] = on; 
      state.current.needsRedraw = true;
      requestRedraw();
    },
    zoomTo: (bounds) => {
      const [[minLon, minLat], [maxLon, maxLat]] = bounds;
      const centerLon = (minLon + maxLon) / 2;
      const centerLat = (minLat + maxLat) / 2;
      vp.current.center = [centerLon, centerLat];
      
      // 计算合适的缩放级别
      const lonRange = maxLon - minLon;
      const latRange = maxLat - minLat;
      const range = Math.max(lonRange, latRange);
      vp.current.zoom = Math.max(2, Math.min(18, 16 - Math.log2(range * 100)));
      
      state.current.needsRedraw = true;
      requestRedraw();
    },
    centerOnRoute: () => {
      // 定位到航迹中心
      if (!props.route || props.route.length === 0) return;
      
      let sumLon = 0, sumLat = 0;
      props.route.forEach(([lon, lat]) => {
        sumLon += lon;
        sumLat += lat;
      });
      
      vp.current.center = [
        sumLon / props.route.length,
        sumLat / props.route.length
      ];
      
      state.current.needsRedraw = true;
      requestRedraw();
    },
    zoomToFit: () => {
      // 自动缩放以适应整个航迹
      if (!props.route || props.route.length === 0) return;
      
      let minLon = Infinity, maxLon = -Infinity;
      let minLat = Infinity, maxLat = -Infinity;
      
      props.route.forEach(([lon, lat]) => {
        minLon = Math.min(minLon, lon);
        maxLon = Math.max(maxLon, lon);
        minLat = Math.min(minLat, lat);
        maxLat = Math.max(maxLat, lat);
      });
      
      // 添加15%的边距
      const lonMargin = (maxLon - minLon) * 0.15;
      const latMargin = (maxLat - minLat) * 0.15;
      
      minLon -= lonMargin;
      maxLon += lonMargin;
      minLat -= latMargin;
      maxLat += latMargin;
      
      // 计算中心点
      vp.current.center = [
        (minLon + maxLon) / 2,
        (minLat + maxLat) / 2
      ];
      
      // 计算合适的缩放级别（细化）
      const lonRange = maxLon - minLon;
      const latRange = maxLat - minLat;
      const maxRange = Math.max(lonRange, latRange);
      
      // 使用更精确的公式计算缩放级别
      // zoom = log2(360 / maxRange) 的近似
      const targetZoom = Math.floor(8.5 - Math.log2(maxRange));
      vp.current.zoom = Math.max(5, Math.min(18, targetZoom));
      
      state.current.needsRedraw = true;
      requestRedraw();
    },
    setColorScheme: (scheme: ColorScheme) => {
      setColorSchemeState(scheme);
      state.current.needsRedraw = true;
      requestRedraw();
    }
  }));

  const requestRedraw = () => {
    // 取消之前的动画帧请求，确保只有最新的请求生效
    if (animationFrameRef.current) {
      cancelAnimationFrame(animationFrameRef.current);
    }
    
    animationFrameRef.current = requestAnimationFrame(() => {
      animationFrameRef.current = null;
      if (state.current.needsRedraw) {
        const startTime = performance.now();
        draw();
        state.current.needsRedraw = false;
        
        // 性能监控：确保60fps (16.67ms per frame)
        const frameTime = performance.now() - startTime;
        if (frameTime > 16.67) {
          console.warn(`Frame time: ${frameTime.toFixed(2)}ms (target: <16.67ms for 60fps)`);
        }
      }
    });
  };

  // 加载地理数据
  useEffect(() => {
    const loadGeoData = async () => {
      try {
        // 优先加载真实的亚太地区Natural Earth数据
        const asiaPacificResponse = await fetch(`${BASE_URL}geo/asia-pacific-land.json`);
        if (asiaPacificResponse.ok) {
          geoData.current = await asiaPacificResponse.json();
          state.current.needsRedraw = true;
          requestRedraw();
        }
      } catch (error) {
        console.warn('Failed to load Asia-Pacific Natural Earth data:', error);
      }
      
      // 加载水深数据
      try {
        const bathymetryResponse = await fetch(`${BASE_URL}geo/asia-pacific-bathymetry.json`);
        if (bathymetryResponse.ok) {
          bathymetryData.current = await bathymetryResponse.json();
          state.current.needsRedraw = true;
          requestRedraw();
        }
      } catch (error) {
        console.warn('Failed to load bathymetry data:', error);
      }
      
      // 加载助航标志数据
      try {
        const seamarksResponse = await fetch(`${BASE_URL}geo/asia-pacific-seamarks.json`);
        if (seamarksResponse.ok) {
          seamarksData.current = await seamarksResponse.json();
          state.current.needsRedraw = true;
          requestRedraw();
        }
      } catch (error) {
        console.warn('Failed to load seamarks data:', error);
      }
      
      try {
        // 备用：加载简化的世界地图数据
        const worldResponse = await fetch(`${BASE_URL}geo/world-land-simplified.json`);
        if (worldResponse.ok) {
          geoData.current = await worldResponse.json();
          state.current.needsRedraw = true;
          requestRedraw();
          return;
        }
      } catch (error) {
        console.warn('Failed to load world geographic data:', error);
      }
      
      // 最后的备用
      try {
        const response = await fetch(`${BASE_URL}geo/world-simplified.json`);
        if (response.ok) {
          geoData.current = await response.json();
          state.current.needsRedraw = true;
          requestRedraw();
        }
      } catch (error) {
        console.warn('Failed to load any geographic data:', error);
      }
    };
    loadGeoData();
  }, [BASE_URL]);

  useEffect(() => {
    const cvs = canvasRef.current!;
    
    const resize = () => {
      const rect = cvs.getBoundingClientRect();
      vp.current.width = rect.width;
      vp.current.height = rect.height;
      cvs.width = Math.floor(rect.width * vp.current.dpr);
      cvs.height = Math.floor(rect.height * vp.current.dpr);
      state.current.needsRedraw = true;
      requestRedraw();
    };
    
    resize();
    const ro = new ResizeObserver(resize);
    ro.observe(cvs);

    // 鼠标滚轮缩放
    const onWheel = (e: WheelEvent) => {
      e.preventDefault();
      const delta = e.deltaY > 0 ? -0.5 : 0.5;
      vp.current.zoom = Math.max(2, Math.min(20, vp.current.zoom + delta));
      state.current.needsRedraw = true;
      requestRedraw();
      if (props.onViewChange) props.onViewChange(vp.current.center, vp.current.zoom);
    };

    // 鼠标拖拽
    const onDown = (e: MouseEvent) => {
      state.current.drag = true;
      state.current.last = [e.clientX, e.clientY];
      cvs.style.cursor = 'grabbing';
    };

    const onMove = (e: MouseEvent) => {
      if (!state.current.drag) return;
      
      const dx = (e.clientX - state.current.last[0]) / vp.current.dpr;
      const dy = (e.clientY - state.current.last[1]) / vp.current.dpr;
      const scale = Math.pow(2, vp.current.zoom) * 256;
      
      vp.current.center[0] -= (dx / scale) * 360;
      vp.current.center[1] += (dy / scale) * 180;
      
      state.current.last = [e.clientX, e.clientY];
      state.current.needsRedraw = true;
      requestRedraw();
      
      // 通知父组件视图变化（实时同步AIS图层）
      if (props.onViewChange) {
        props.onViewChange(vp.current.center, vp.current.zoom);
      }
    };

    const onUp = () => {
      state.current.drag = false;
      cvs.style.cursor = 'grab';
    };

    // 键盘导航支持
    const onKeyDown = (e: KeyboardEvent) => {
      const step = 0.001; // 键盘平移步长
      let moved = false;
      
      switch (e.key) {
        case 'ArrowUp':
          e.preventDefault();
          vp.current.center[1] += step;
          moved = true;
          break;
        case 'ArrowDown':
          e.preventDefault();
          vp.current.center[1] -= step;
          moved = true;
          break;
        case 'ArrowLeft':
          e.preventDefault();
          vp.current.center[0] -= step;
          moved = true;
          break;
        case 'ArrowRight':
          e.preventDefault();
          vp.current.center[0] += step;
          moved = true;
          break;
        case '=':
        case '+':
          e.preventDefault();
          vp.current.zoom = Math.min(20, vp.current.zoom + 0.5);
          moved = true;
          break;
        case '-':
          e.preventDefault();
          vp.current.zoom = Math.max(2, vp.current.zoom - 0.5);
          moved = true;
          break;
      }
      
      if (moved) {
        state.current.needsRedraw = true;
        requestRedraw();
        // 通知父组件视图变化
        if (props.onViewChange) props.onViewChange(vp.current.center, vp.current.zoom);
      }
    };

    // 触摸手势支持（基础版）
    let touchStart: { x: number; y: number; dist?: number } | null = null;
    
    const onTouchStart = (e: TouchEvent) => {
      e.preventDefault();
      if (e.touches.length === 1) {
        // 单指拖拽
        const touch = e.touches[0];
        touchStart = { x: touch.clientX, y: touch.clientY };
        state.current.drag = true;
      } else if (e.touches.length === 2) {
        // 双指缩放
        const t1 = e.touches[0];
        const t2 = e.touches[1];
        const dist = Math.hypot(t2.clientX - t1.clientX, t2.clientY - t1.clientY);
        touchStart = { 
          x: (t1.clientX + t2.clientX) / 2, 
          y: (t1.clientY + t2.clientY) / 2, 
          dist 
        };
      }
    };

    const onTouchMove = (e: TouchEvent) => {
      e.preventDefault();
      if (!touchStart) return;
      
      if (e.touches.length === 1 && state.current.drag) {
        // 单指拖拽
        const touch = e.touches[0];
        const dx = (touch.clientX - touchStart.x) / vp.current.dpr;
        const dy = (touch.clientY - touchStart.y) / vp.current.dpr;
        const scale = Math.pow(2, vp.current.zoom) * 256;
        
        vp.current.center[0] -= (dx / scale) * 360;
        vp.current.center[1] += (dy / scale) * 180;
        
        touchStart = { x: touch.clientX, y: touch.clientY };
        state.current.needsRedraw = true;
        requestRedraw();
        
        // 通知父组件视图变化（实时同步AIS图层）
        if (props.onViewChange) {
          props.onViewChange(vp.current.center, vp.current.zoom);
        }
      } else if (e.touches.length === 2 && touchStart.dist) {
        // 双指缩放
        const t1 = e.touches[0];
        const t2 = e.touches[1];
        const dist = Math.hypot(t2.clientX - t1.clientX, t2.clientY - t1.clientY);
        const scaleFactor = dist / touchStart.dist;
        
        if (Math.abs(scaleFactor - 1) > 0.1) { // 防抖
          const zoomDelta = Math.log2(scaleFactor);
          vp.current.zoom = Math.max(2, Math.min(20, vp.current.zoom + zoomDelta));
          touchStart.dist = dist;
          state.current.needsRedraw = true;
          requestRedraw();
        }
      }
    };

    const onTouchEnd = (e: TouchEvent) => {
      e.preventDefault();
      touchStart = null;
      state.current.drag = false;
    };

    cvs.addEventListener("wheel", onWheel, { passive: false });
    cvs.addEventListener("mousedown", onDown);
    cvs.addEventListener("touchstart", onTouchStart, { passive: false });
    cvs.addEventListener("touchmove", onTouchMove, { passive: false });
    cvs.addEventListener("touchend", onTouchEnd, { passive: false });
    window.addEventListener("mousemove", onMove);
    window.addEventListener("mouseup", onUp);
    window.addEventListener("keydown", onKeyDown);
    
    cvs.style.cursor = 'grab';
    cvs.tabIndex = 0; // 使画布可聚焦以接收键盘事件

    return () => {
      ro.disconnect();
      cvs.removeEventListener("wheel", onWheel);
      cvs.removeEventListener("mousedown", onDown);
      cvs.removeEventListener("touchstart", onTouchStart);
      cvs.removeEventListener("touchmove", onTouchMove);
      cvs.removeEventListener("touchend", onTouchEnd);
      window.removeEventListener("mousemove", onMove);
      window.removeEventListener("mouseup", onUp);
      window.removeEventListener("keydown", onKeyDown);
      if (animationFrameRef.current) {
        cancelAnimationFrame(animationFrameRef.current);
      }
    };
  }, []);

  useEffect(() => {
    state.current.needsRedraw = true;
    requestRedraw();
  }, [props.enc, props.route]);

  // 绘制水深等深线
  function drawBathymetry(
    ctx: CanvasRenderingContext2D,
    width: number,
    height: number,
    center: LonLat,
    zoom: number
  ) {
    if (!bathymetryData.current || !bathymetryData.current.features) return;
    
    const colors = ECDIS_PALETTE[colorScheme];
    const safetySettings = DEFAULT_SAFETY_SETTINGS;
    
    // 定义投影函数
    const project = (coord: LonLat): [number, number] => {
      const { x, y } = lonLatToXY(coord[0], coord[1], center[0], center[1], zoom, width, height);
      return [x, y];
    };
    
    ctx.save();
    
    bathymetryData.current.features.forEach((feature: any) => {
      const depth = feature.properties.depth;
      const coords = feature.geometry.coordinates;
      
      // 根据深度设置颜色
      if (depth === safetySettings.safetyContour) {
        // 安全等深线 - 加粗高亮
        ctx.strokeStyle = colorScheme === 'NIGHT' ? colors.CHRED : colors.CHBLK;
        ctx.lineWidth = 2;
        ctx.setLineDash([]);
      } else if (depth < safetySettings.safetyContour) {
        // 浅于安全等深线 - 警告色
        ctx.strokeStyle = colors.DEPSH;
        ctx.lineWidth = 1;
        ctx.setLineDash([5, 3]);
      } else {
        // 深于安全等深线 - 普通显示
        ctx.strokeStyle = colors.CHGRD;
        ctx.lineWidth = 0.5;
        ctx.setLineDash([2, 4]);
      }
      
      // 绘制等深线
      if (feature.geometry.type === 'MultiLineString') {
        coords.forEach((lineString: number[][]) => {
          ctx.beginPath();
          lineString.forEach(([lon, lat], index) => {
            const [x, y] = project([lon, lat]);
            if (index === 0) ctx.moveTo(x, y);
            else ctx.lineTo(x, y);
          });
          ctx.stroke();
        });
      }
    });
    
    ctx.setLineDash([]);
    ctx.restore();
  }
  
  // 绘制助航标志
  function drawSeamarks(
    ctx: CanvasRenderingContext2D,
    width: number,
    height: number,
    center: LonLat,
    zoom: number
  ) {
    if (!seamarksData.current) return;
    
    const colors = ECDIS_PALETTE[colorScheme];
    
    // 定义投影函数
    const project = (coord: LonLat): [number, number] => {
      const { x, y } = lonLatToXY(coord[0], coord[1], center[0], center[1], zoom, width, height);
      return [x, y];
    };
    
    ctx.save();
    
    // 绘制灯塔
    if (seamarksData.current.lights) {
      seamarksData.current.lights.forEach((light: any) => {
        const [x, y] = project(light.coords);
        if (x >= -20 && x <= width + 20 && y >= -20 && y <= height + 20) {
          // 灯塔符号 - 星形
          ctx.fillStyle = colors.LIGHTS;
          ctx.strokeStyle = colors.CHBLK;
          ctx.lineWidth = 1;
          drawStar(ctx, x, y, zoom > 10 ? 8 : 6, zoom > 10 ? 4 : 3);
          
          // 标注名称（高缩放级别）
          if (zoom > 12 && light.name) {
            ctx.fillStyle = colors.CHBLK;
            ctx.font = '10px monospace';
            ctx.fillText(light.name, x + 10, y - 5);
          }
        }
      });
    }
    
    // 绘制浮标
    if (seamarksData.current.buoys) {
      seamarksData.current.buoys.forEach((buoy: any) => {
        const [x, y] = project(buoy.coords);
        if (x >= -20 && x <= width + 20 && y >= -20 && y <= height + 20) {
          ctx.strokeStyle = colors.CHBLK;
          ctx.lineWidth = 1;
          // 根据类型绘制不同形状
          if (buoy.category === 'port' || buoy.color === 'red') {
            ctx.fillStyle = colors.BUOYAR;
            drawDiamond(ctx, x, y, zoom > 10 ? 6 : 4);
          } else if (buoy.category === 'starboard' || buoy.color === 'green') {
            ctx.fillStyle = colors.BUOYAG;
            drawTriangle(ctx, x, y, zoom > 10 ? 6 : 4);
          } else {
            ctx.fillStyle = colors.BUOYAY;
            drawCircle(ctx, x, y, zoom > 10 ? 5 : 3);
          }
        }
      });
    }
    
    // 绘制危险物
    if (seamarksData.current.dangers) {
      seamarksData.current.dangers.forEach((danger: any) => {
        const [x, y] = project(danger.coords);
        if (x >= -20 && x <= width + 20 && y >= -20 && y <= height + 20) {
          ctx.strokeStyle = danger.dangerous ? colors.CHRED : colors.CHBLK;
          ctx.lineWidth = 2;
          
          if (danger.type === 'wreck') {
            drawWreckSymbol(ctx, x, y);
          } else if (danger.type === 'rock') {
            drawRockSymbol(ctx, x, y);
          }
        }
      });
    }
    
    ctx.restore();
  }
  
  // 符号绘制辅助函数
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
  
  function drawTriangle(ctx: CanvasRenderingContext2D, x: number, y: number, size: number) {
    ctx.beginPath();
    ctx.moveTo(x, y - size);
    ctx.lineTo(x + size, y + size);
    ctx.lineTo(x - size, y + size);
    ctx.closePath();
    ctx.fill();
    ctx.stroke();
  }
  
  function drawCircle(ctx: CanvasRenderingContext2D, x: number, y: number, radius: number) {
    ctx.beginPath();
    ctx.arc(x, y, radius, 0, Math.PI * 2);
    ctx.fill();
    ctx.stroke();
  }
  
  function drawWreckSymbol(ctx: CanvasRenderingContext2D, x: number, y: number) {
    ctx.beginPath();
    ctx.ellipse(x, y, 8, 5, 0, 0, Math.PI * 2);
    ctx.stroke();
    ctx.beginPath();
    ctx.moveTo(x - 6, y - 4);
    ctx.lineTo(x + 6, y + 4);
    ctx.moveTo(x - 6, y + 4);
    ctx.lineTo(x + 6, y - 4);
    ctx.stroke();
  }
  
  function drawRockSymbol(ctx: CanvasRenderingContext2D, x: number, y: number) {
    ctx.beginPath();
    ctx.moveTo(x, y - 5);
    ctx.lineTo(x + 3, y);
    ctx.lineTo(x + 2, y + 3);
    ctx.lineTo(x - 2, y + 3);
    ctx.lineTo(x - 3, y);
    ctx.closePath();
    ctx.stroke();
  }

  const draw = () => {
    const cvs = canvasRef.current!;
    const ctx = cvs.getContext("2d")!;
    const { width, height, dpr, zoom, center } = vp.current;

    // 设置高DPI渲染
    ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
    ctx.clearRect(0, 0, width, height);

    // 深色海洋背景
    ctx.fillStyle = "#06141d";
    ctx.fillRect(0, 0, width, height);

    // 真实地理环境图层（优先显示）
    if (layers.current.geography && geoData.current) {
      drawGeography(ctx, width, height, center, zoom);
    }
    
    // 水深等深线（ECDIS图层）
    if (layers.current.bathymetry && bathymetryData.current) {
      drawBathymetry(ctx, width, height, center, zoom);
    }

    // 本地离线简易海图（网格+纹理）
    if (layers.current.localbase) {
      drawLocalBasemap(ctx, width, height, center, zoom);
    }

    // 绘制海图瓦片（禁用有问题的OSM瓦片，改用增强的本地渲染）
    if (layers.current.basemap) {
      // OSM瓦片存在访问问题，改用增强的本地海图渲染
      drawEnhancedLocalBasemap(ctx, width, height, center, zoom);
    }
    if (layers.current.seamarks) {
      // OpenSeaMap瓦片可能也有同样问题，暂时禁用
      // drawTilesLayer(ctx, width, height, center, zoom, `${TILE_BASE}/openseamap`);
      drawLocalSeamarks(ctx, width, height, center, zoom);
    }

    // 视窗裁剪优化：计算当前可见的地理边界
    const viewBounds = getVisibleBounds();
    
    // 启用视窗裁剪以提升性能
    ctx.save();
    ctx.beginPath();
    ctx.rect(0, 0, width, height);
    ctx.clip();

    // ENC-lite 海岸线（使用视窗裁剪优化）
    if (layers.current.enc && props.enc?.coast) {
      ctx.fillStyle = "#1e2936";
      ctx.strokeStyle = "#2d3748";
      ctx.lineWidth = 1;
      
      for (const poly of props.enc.coast) {
        if (isGeometryVisible(poly, viewBounds)) {
          drawPolygon(ctx, poly, true, true);
        }
      }
      
      // 浅水区域（安全等深线着色）
      if (props.enc.shallow) {
        ctx.globalAlpha = 0.4;
        ctx.fillStyle = "#1a365d";
        ctx.strokeStyle = "#2c5282";
        
        for (const shallow of props.enc.shallow) {
          if (isGeometryVisible(shallow, viewBounds)) {
            drawPolygon(ctx, shallow, true, true);
          }
        }
        ctx.globalAlpha = 1;
      }

      // 等深线（depth contours）
      if (props.enc.depths) {
        ctx.strokeStyle = "#4a90e2";
        ctx.lineWidth = 1;
        ctx.setLineDash([2, 2]);
        
        for (const depth of props.enc.depths) {
          if (isGeometryVisible(depth, viewBounds)) {
            drawPolygon(ctx, depth, false, true);
          }
        }
        ctx.setLineDash([]);
      }
    }

    // TSS 分道通航制（视窗裁剪优化）
    if (layers.current.tss && props.enc?.tss) {
      // 航行车道
      if (props.enc.tss.lanes?.length > 0) {
        ctx.fillStyle = "rgba(255, 214, 10, 0.25)";
        ctx.strokeStyle = "rgba(255, 214, 10, 0.6)";
        ctx.lineWidth = 1;
        
        for (const lane of props.enc.tss.lanes) {
          if (isGeometryVisible(lane, viewBounds)) {
            drawPolygon(ctx, lane, true, true);
          }
        }
      }
      
      // 分隔带
      if (props.enc.tss.sep_zones?.length > 0) {
        ctx.fillStyle = "rgba(255, 99, 71, 0.3)";
        ctx.strokeStyle = "rgba(255, 99, 71, 0.8)";
        ctx.lineWidth = 2;
        
        for (const sep of props.enc.tss.sep_zones) {
          if (isGeometryVisible(sep, viewBounds)) {
            drawPolygon(ctx, sep, true, true);
          }
        }
      }
    }

    // S-124 警告区域（视窗裁剪优化）
    if (layers.current.s124 && props.enc?.s124) {
      // 限速区
      if (props.enc.s124.speed_limits?.length > 0) {
        ctx.fillStyle = "rgba(0, 153, 255, 0.2)";
        ctx.strokeStyle = "rgba(0, 153, 255, 0.6)";
        ctx.lineWidth = 1;
        ctx.setLineDash([5, 5]);
        
        for (const zone of props.enc.s124.speed_limits) {
          if (isGeometryVisible(zone.geometry, viewBounds)) {
            drawPolygon(ctx, zone.geometry, true, true);
          }
        }
        ctx.setLineDash([]);
      }
      
      // 禁航区
      if (props.enc.s124.prohibited?.length > 0) {
        ctx.fillStyle = "rgba(255, 0, 0, 0.25)";
        ctx.strokeStyle = "rgba(255, 0, 0, 0.8)";
        ctx.lineWidth = 2;
        ctx.setLineDash([10, 5]);
        
        for (const zone of props.enc.s124.prohibited) {
          if (isGeometryVisible(zone.geometry, viewBounds)) {
            drawPolygon(ctx, zone.geometry, true, true);
          }
        }
        ctx.setLineDash([]);
      }
    }

    // 助航设备（Aids to Navigation）
    if (layers.current.enc && props.enc?.aids) {
      for (const aid of props.enc.aids) {
        const [x, y] = project([aid.lon, aid.lat]);
        
        // 检查是否在视窗内
        if (x >= -20 && x <= width + 20 && y >= -20 && y <= height + 20) {
          drawAidToNavigation(ctx, x, y, aid.type, aid.color);
        }
      }
    }

    // 规划航线（支持动态路径的双路径可视化）
    if (layers.current.route && props.route?.length > 1) {
      const isDynamicMode = Boolean(
        props.dynamicRouteEnabled && Array.isArray(props.dynamicRoute) && props.dynamicRoute.length > 1
      );
      
      // 调试信息
      if (props.dynamicRouteEnabled) {
        console.log('动态路径渲染检查:', {
          enabled: props.dynamicRouteEnabled,
          routeLength: Array.isArray(props.dynamicRoute) ? props.dynamicRoute.length : 0,
          showDynamic: isDynamicMode,
          dynamicRoute: props.dynamicRoute
        });
      }
      
      if (!isDynamicMode) {
        // 标准模式：显示XTD走廊
        ctx.strokeStyle = "rgba(163, 190, 140, 0.3)";
        ctx.lineWidth = 1;
        ctx.setLineDash([5, 3]);
        
        for (let i = 0; i < props.route.length - 1; i++) {
          const [x1, y1] = project(props.route[i]);
          const [x2, y2] = project(props.route[i + 1]);
          
          // 计算垂直于航线的XTD走廊边界
          const dx = x2 - x1;
          const dy = y2 - y1;
          const len = Math.hypot(dx, dy);
          if (len > 0) {
            const xtdWidth = 20; // 像素宽度，实际应根据XTD值计算
            const perpX = (-dy / len) * xtdWidth;
            const perpY = (dx / len) * xtdWidth;
            
            // 绘制走廊边界
            ctx.beginPath();
            ctx.moveTo(x1 + perpX, y1 + perpY);
            ctx.lineTo(x2 + perpX, y2 + perpY);
            ctx.stroke();
            
            ctx.beginPath();
            ctx.moveTo(x1 - perpX, y1 - perpY);
            ctx.lineTo(x2 - perpX, y2 - perpY);
            ctx.stroke();
          }
        }
        ctx.setLineDash([]);
      }

      // 原始航线
      if (isDynamicMode) {
        // 动态模式：原路径显示为蓝色虚线（弱化显示）
        ctx.strokeStyle = "rgba(136, 192, 208, 0.8)";
        ctx.lineWidth = 2.5;
        ctx.setLineDash([8, 6]);
        ctx.lineCap = "round";
        ctx.lineJoin = "round";
      } else {
        // 标准模式：原路径显示为绿色实线
        ctx.strokeStyle = "#a3be8c";
        ctx.lineWidth = 4;
        ctx.setLineDash([]);
        ctx.lineCap = "round";
        ctx.lineJoin = "round";
      }
      
      ctx.beginPath();
      let first = true;
      for (const p of props.route) {
        const [x, y] = project(p);
        if (first) {
          ctx.moveTo(x, y);
          first = false;
        } else {
          ctx.lineTo(x, y);
        }
      }
      ctx.stroke();
      ctx.setLineDash([]); // 重置虚线

      // 动态路径（如果启用）
      if (isDynamicMode) {
        const dyn = props.dynamicRoute as LonLat[];
        // 将动态路径投影到屏幕坐标，容错处理NaN/无效点
        const dynScreen: Array<[number, number]> = dyn
          .map(p => project(p))
          .filter(([x,y]) => Number.isFinite(x) && Number.isFinite(y));

        // 计算屏幕空间偏移的并行路径，使其在与原路径重叠时也能清晰可见
        const OFFSET_PX = 6; // 固定侧向偏移像素
        const shifted: Array<[number, number]> = dynScreen.map((pt, i) => {
          let dx = 0, dy = 0;
          if (i < dynScreen.length - 1) {
            // 使用当前段的切向量
            dx = dynScreen[i + 1][0] - pt[0];
            dy = dynScreen[i + 1][1] - pt[1];
          } else if (i > 0) {
            // 使用上一段的切向量
            dx = pt[0] - dynScreen[i - 1][0];
            dy = pt[1] - dynScreen[i - 1][1];
          }
          const len = Math.hypot(dx, dy) || 1;
          // 垂直于切向量的法向量（屏幕空间）
          const nx = -dy / len;
          const ny = dx / len;
          const x = pt[0] + nx * OFFSET_PX;
          const y = pt[1] + ny * OFFSET_PX;
          return [x, y];
        });

        // 动态路径：高亮红色+发光边
        ctx.strokeStyle = "#ff4d4f";
        ctx.lineWidth = 6;
        ctx.setLineDash([]);
        ctx.lineCap = "round";
        ctx.lineJoin = "round";
        ctx.save();
        ctx.shadowColor = "rgba(255, 77, 79, 0.85)";
        ctx.shadowBlur = 10;

        ctx.beginPath();
        let validCount = 0;
        shifted.forEach(([x, y], idx) => {
          if (Number.isFinite(x) && Number.isFinite(y)) {
            validCount++;
            if (idx === 0) ctx.moveTo(x, y);
            else ctx.lineTo(x, y);
          }
        });
        // 如偏移路径异常（超出视图或数值问题），回退绘制未偏移的动态路径，避免在高缩放下消失
        if (validCount < 2) {
          ctx.beginPath();
          dynScreen.forEach(([x, y], idx) => {
            if (Number.isFinite(x) && Number.isFinite(y)) {
              if (idx === 0) ctx.moveTo(x, y);
              else ctx.lineTo(x, y);
            }
          });
        }
        ctx.stroke();
        ctx.restore();
        
        // 动态路径的方向箭头（橙色）
        ctx.strokeStyle = "#ff9f43";
        ctx.lineWidth = 2;
        const arrowPath = (pts: Array<[number, number]>) => {
          for (let i = 0; i < pts.length - 1; i++) {
            const [x1, y1] = pts[i];
            const [x2, y2] = pts[i + 1];
            if (!Number.isFinite(x1) || !Number.isFinite(y1) || !Number.isFinite(x2) || !Number.isFinite(y2)) continue;
          
            const midX = (x1 + x2) / 2;
            const midY = (y1 + y2) / 2;
          
            // 计算航向箭头
            const angle = Math.atan2(y2 - y1, x2 - x1);
            const arrowLen = 8;
            const arrowAngle = Math.PI / 6;
          
            ctx.beginPath();
            ctx.moveTo(midX, midY);
            ctx.lineTo(
              midX - arrowLen * Math.cos(angle - arrowAngle),
              midY - arrowLen * Math.sin(angle - arrowAngle)
            );
            ctx.moveTo(midX, midY);
            ctx.lineTo(
              midX - arrowLen * Math.cos(angle + arrowAngle),
              midY - arrowLen * Math.sin(angle + arrowAngle)
            );
            ctx.stroke();
          }
        };
        arrowPath(shifted);
        // 若回退绘制了未偏移路径，也补充箭头
        if (validCount < 2) arrowPath(dynScreen);
      }

      // 原始航线方向箭头
      ctx.strokeStyle = isDynamicMode ? "rgba(94, 129, 172, 0.7)" : "#5e81ac";
      ctx.lineWidth = 2;
      for (let i = 0; i < props.route.length - 1; i++) {
        const [x1, y1] = project(props.route[i]);
        const [x2, y2] = project(props.route[i + 1]);
        
        const midX = (x1 + x2) / 2;
        const midY = (y1 + y2) / 2;
        
        // 计算航向箭头
        const angle = Math.atan2(y2 - y1, x2 - x1);
        const arrowLen = 8;
        const arrowAngle = Math.PI / 6;
        
        ctx.beginPath();
        ctx.moveTo(midX, midY);
        ctx.lineTo(
          midX - arrowLen * Math.cos(angle - arrowAngle),
          midY - arrowLen * Math.sin(angle - arrowAngle)
        );
        ctx.moveTo(midX, midY);
        ctx.lineTo(
          midX - arrowLen * Math.cos(angle + arrowAngle),
          midY - arrowLen * Math.sin(angle + arrowAngle)
        );
        ctx.stroke();
      }

      // 避让点高亮（红色闪烁圆点）
      if (isDynamicMode && props.avoidancePoints && props.avoidancePoints.length > 0) {
        const time = performance.now() / 1000;
        const pulse = 0.5 + 0.5 * Math.sin(time * 2 * Math.PI * 0.8); // 0..1
        props.avoidancePoints.forEach(([lon, lat]) => {
          const [x, y] = project([lon, lat]);
          ctx.save();
          ctx.fillStyle = `rgba(255, 77, 79, ${0.6 + 0.4 * pulse})`;
          ctx.strokeStyle = "#ff4d4f";
          ctx.lineWidth = 2;
          ctx.shadowColor = "rgba(255, 77, 79, 0.9)";
          ctx.shadowBlur = 12;
          
          // 外圈
          ctx.beginPath();
          ctx.arc(x, y, 10 + 6 * pulse, 0, Math.PI * 2);
          ctx.stroke();
          
          // 实心点
          ctx.beginPath();
          ctx.arc(x, y, 4 + 2 * pulse, 0, Math.PI * 2);
          ctx.fill();
          ctx.restore();
        });
      }

      // 航路点（增强版）
      props.route.forEach((p, i) => {
        const [x, y] = project(p);
        const isStart = i === 0;
        const isEnd = i === props.route.length - 1;
        const isWaypoint = !isStart && !isEnd;
        
        // 转弯半径圆圈（仅中间航路点）
        if (isWaypoint) {
          ctx.strokeStyle = "rgba(136, 192, 208, 0.4)";
          ctx.lineWidth = 1;
          ctx.setLineDash([3, 3]);
          ctx.beginPath();
          ctx.arc(x, y, 12, 0, Math.PI * 2); // 转弯半径可视化
          ctx.stroke();
          ctx.setLineDash([]);
        }
        
        // 航路点主体
        ctx.fillStyle = isStart ? "#bf616a" : isEnd ? "#a3be8c" : "#88c0d0";
        ctx.strokeStyle = "#2e3440";
        ctx.lineWidth = 2;
        
        ctx.beginPath();
        const radius = isStart || isEnd ? 8 : 6;
        ctx.arc(x, y, radius, 0, Math.PI * 2);
        ctx.fill();
        ctx.stroke();
        
        // 航路点标签
        ctx.fillStyle = "#2e3440";
        ctx.font = "bold 11px monospace";
        ctx.textAlign = "center";
        ctx.textBaseline = "middle";
        
        const label = isStart ? "S" : isEnd ? "E" : `W${i}`;
        ctx.fillText(label, x, y);
        
        // 航路点信息（鼠标悬停时显示，暂时简化显示）
        if (zoom >= 10) { // 高缩放级别时显示详细信息
          ctx.fillStyle = "rgba(46, 52, 64, 0.8)";
          ctx.fillRect(x + 12, y - 15, 60, 25);
          ctx.fillStyle = "#d8dee9";
          ctx.font = "9px monospace";
          ctx.textAlign = "left";
          ctx.textBaseline = "top";
          ctx.fillText(`${p[1].toFixed(4)}°N`, x + 14, y - 12);
          ctx.fillText(`${p[0].toFixed(4)}°E`, x + 14, y - 3);
        }
      });

      // 航段距离和方位信息
      if (zoom >= 8) {
        ctx.fillStyle = "#81a1c1";
        ctx.font = "10px monospace";
        ctx.textAlign = "center";
        ctx.textBaseline = "middle";
        
        for (let i = 0; i < props.route.length - 1; i++) {
          const [x1, y1] = project(props.route[i]);
          const [x2, y2] = project(props.route[i + 1]);
          
          const midX = (x1 + x2) / 2;
          const midY = (y1 + y2) / 2;
          
          // 计算真实地理距离和方位
          const p1 = props.route[i];
          const p2 = props.route[i + 1];
          const dist = haversineDistance(p1[1], p1[0], p2[1], p2[0]) / 1852; // 海里
          const bearing = calculateBearing(p1[1], p1[0], p2[1], p2[0]);
          
          // 背景
          ctx.fillStyle = "rgba(46, 52, 64, 0.7)";
          ctx.fillRect(midX - 25, midY - 10, 50, 20);
          
          // 文字
          ctx.fillStyle = "#d8dee9";
          ctx.fillText(`${dist.toFixed(1)}nm`, midX, midY - 3);
          ctx.fillText(`${bearing.toFixed(0)}°`, midX, midY + 7);
        }
      }
    }
    
    // 助航标志（ECDIS风格）
    if (layers.current.seamark && seamarksData.current) {
      drawSeamarks(ctx, width, height, center, zoom);
    }

    // 恢复裁剪状态
    ctx.restore();

    // 坐标和缩放级别显示（调试用）
    ctx.fillStyle = "rgba(46, 52, 64, 0.8)";
    ctx.fillRect(8, 8, 200, 60);
    ctx.fillStyle = "#d8dee9";
    ctx.font = "11px monospace";
    ctx.textAlign = "left";
    ctx.fillText(`Center: ${center[1].toFixed(4)}°N, ${center[0].toFixed(4)}°E`, 12, 24);
    ctx.fillText(`Zoom: ${zoom.toFixed(1)}`, 12, 40);
    ctx.fillText(`Route: ${props.route.length} waypoints`, 12, 56);

    // 绘制AIS目标（在所有图层之上，独立于其他图层状态）
    if (props.aisEnabled && props.aisTargets && props.aisTargets.length > 0) {
      drawAISTargets(ctx, props.aisTargets);
    }

    // 辅助函数
    function project([lon, lat]: LonLat): [number, number] {
      const { x, y } = lonLatToXY(lon, lat, vp.current.center[0], vp.current.center[1], vp.current.zoom, width, height);
      return [x, y];
    }

    // 绘制AIS目标
    function drawAISTargets(ctx: CanvasRenderingContext2D, targets: AISTarget[]) {
      if (!targets || targets.length === 0) return;

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

      targets.forEach(target => {
        const [x, y] = project([target.lon, target.lat]);
        
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
    }

    // 根据视图绘制 WebMercator XYZ 瓦片
    function drawTilesLayer(
      ctx: CanvasRenderingContext2D,
      width: number,
      height: number,
      center: LonLat,
      zoomVisual: number,
      baseUrl: string
    ) {
      // 使用低缩放级别的本地样本（0..2）
      const z = Math.max(0, Math.min(2, Math.floor(zoomVisual - 8)));
      const worldSize = 256 * Math.pow(2, z);

      const centerPx = lonLatToPixel(center[0], center[1], z, worldSize);
      const topLeftPx = { x: centerPx.x - width / 2, y: centerPx.y - height / 2 };
      const startTileX = Math.floor(topLeftPx.x / 256);
      const startTileY = Math.floor(topLeftPx.y / 256);
      const endTileX = Math.floor((topLeftPx.x + width) / 256);
      const endTileY = Math.floor((topLeftPx.y + height) / 256);

      for (let tx = startTileX; tx <= endTileX; tx++) {
        for (let ty = startTileY; ty <= endTileY; ty++) {
          // 环绕经度（x循环），y 夹取
          const num = Math.pow(2, z);
          const xWrapped = ((tx % num) + num) % num;
          if (ty < 0 || ty >= num) continue;
          const url = `${baseUrl}/${z}/${xWrapped}/${ty}.png`;
          const key = url;
          let img = tileCache.current.get(key);
          if (!img) {
            img = new Image();
            img.crossOrigin = "anonymous";
            img.onload = () => {
              state.current.needsRedraw = true;
              requestRedraw();
            };
            img.src = url;
            tileCache.current.set(key, img);
          }
          if (img.complete && img.naturalWidth > 0) {
            const dx = Math.floor(tx * 256 - topLeftPx.x);
            const dy = Math.floor(ty * 256 - topLeftPx.y);
            ctx.drawImage(img, dx, dy, 256, 256);
          }
        }
      }
    }

    function lonLatToPixel(lon: number, lat: number, z: number, worldSize: number) {
      const x = (lon + 180) / 360 * worldSize;
      const sinLat = Math.sin((lat * Math.PI) / 180);
      const y = (0.5 - Math.log((1 + sinLat) / (1 - sinLat)) / (4 * Math.PI)) * worldSize;
      return { x, y };
    }

    // 绘制离线简易海图：重复纹理 + 经纬网 + 比例尺
    function drawLocalBasemap(
      ctx: CanvasRenderingContext2D,
      width: number,
      height: number,
      center: LonLat,
      zoom: number
    ) {
      // 纹理（程序生成）
      const tile = document.createElement('canvas');
      tile.width = 256; tile.height = 256;
      const tctx = tile.getContext('2d')!;
      // 海洋底色
      tctx.fillStyle = '#0a1a24';
      tctx.fillRect(0, 0, 256, 256);
      // 轻微噪声点缀
      tctx.fillStyle = 'rgba(255,255,255,0.03)';
      for (let i = 0; i < 400; i++) {
        const x = Math.random() * 256;
        const y = Math.random() * 256;
        tctx.fillRect(x, y, 1, 1);
      }
      // 细网格
      tctx.strokeStyle = 'rgba(255,255,255,0.05)';
      tctx.lineWidth = 1;
      tctx.beginPath();
      for (let i = 0; i <= 256; i += 32) {
        tctx.moveTo(i + 0.5, 0); tctx.lineTo(i + 0.5, 256);
        tctx.moveTo(0, i + 0.5); tctx.lineTo(256, i + 0.5);
      }
      tctx.stroke();
      const pattern = ctx.createPattern(tile, 'repeat')!;
      ctx.save();
      ctx.globalAlpha = 0.9;
      ctx.fillStyle = pattern;
      ctx.fillRect(0, 0, width, height);
      ctx.restore();

      // 经纬网（每 1° 或 5°，随缩放调整）
      const step = zoom >= 8 ? 1 : 5;
      ctx.save();
      ctx.strokeStyle = 'rgba(255,255,255,0.08)';
      ctx.lineWidth = 1;
      // 经线
      for (let lon = Math.floor(center[0]) - 180; lon <= Math.floor(center[0]) + 180; lon += step) {
        const [x1, y1] = project([lon, -85]);
        const [x2, y2] = project([lon, 85]);
        ctx.beginPath(); ctx.moveTo(x1, y1); ctx.lineTo(x2, y2); ctx.stroke();
      }
      // 纬线
      for (let lat = Math.floor(center[1]) - 85; lat <= Math.floor(center[1]) + 85; lat += step) {
        const [x1, y1] = project([-180, lat]);
        const [x2, y2] = project([180, lat]);
        ctx.beginPath(); ctx.moveTo(x1, y1); ctx.lineTo(x2, y2); ctx.stroke();
      }
      ctx.restore();
    }

    // 绘制真实地理环境（海洋风格）
    function drawGeography(
      ctx: CanvasRenderingContext2D,
      width: number,
      height: number,
      center: LonLat,
      zoom: number
    ) {
      if (!geoData.current || !geoData.current.features) return;

      ctx.save();
      
      // 获取ECDIS颜色方案
      const colors = ECDIS_PALETTE[colorScheme];

      // 海洋背景（ECDIS风格）
      ctx.fillStyle = colors.DEPDW;  // 深水颜色
      ctx.fillRect(0, 0, width, height);

      // 添加网格线（海图特征）
      ctx.globalAlpha = 0.05;
      ctx.strokeStyle = '#b0c4de';
      ctx.lineWidth = 0.5;
      
      // 绘制经纬度网格（每10度）
      const gridStep = 10;
      const scale = Math.pow(2, zoom) * 256 / 360;
      
      // 经度线
      for (let lon = -180; lon <= 180; lon += gridStep) {
        const [x, _] = project([lon, 0]);
        ctx.beginPath();
        ctx.moveTo(x, 0);
        ctx.lineTo(x, height);
        ctx.stroke();
      }
      
      // 纬度线
      for (let lat = -80; lat <= 80; lat += gridStep) {
        const [_, y] = project([0, lat]);
        ctx.beginPath();
        ctx.moveTo(0, y);
        ctx.lineTo(width, y);
        ctx.stroke();
      }
      
      ctx.globalAlpha = 1.0;

      // 绘制陆地（ECDIS样式）
      geoData.current.features.forEach((feature: any) => {
        if (!feature.geometry) return;

        const { type, coordinates } = feature.geometry;
        const properties = feature.properties || {};

        // ECDIS陆地颜色
        ctx.fillStyle = colors.LANDA;  // ECDIS陆地色
        ctx.strokeStyle = colors.CSTLN;  // ECDIS海岸线颜色
        ctx.lineWidth = colorScheme === 'NIGHT' ? 0.5 : 1;
        ctx.shadowColor = 'rgba(0, 0, 0, 0.2)';
        ctx.shadowBlur = colorScheme === 'NIGHT' ? 0 : 1;
        ctx.shadowOffsetX = colorScheme === 'NIGHT' ? 0 : 1;
        ctx.shadowOffsetY = colorScheme === 'NIGHT' ? 0 : 1;

        // 处理不同的几何类型
        if (type === 'Polygon') {
          drawPolygon(coordinates);
        } else if (type === 'MultiPolygon') {
          coordinates.forEach((polygon: any) => {
            drawPolygon(polygon);
          });
        }
      });
      
      ctx.shadowBlur = 0;

      // 绘制单个多边形
      function drawPolygon(rings: number[][] | number[][][]) {
        // 处理Polygon和MultiPolygon的不同格式
        const coords = Array.isArray(rings[0]) && Array.isArray(rings[0][0]) ? rings[0] : rings;
        
        ctx.beginPath();
        let firstPoint = true;
        
        (coords as number[][]).forEach(([lon, lat]) => {
          const [x, y] = project([lon, lat]);
          
          // 检查点是否在视窗内（扩展边界以确保边缘多边形也能绘制）
          const margin = 500;
          if (x < -margin || x > width + margin || y < -margin || y > height + margin) {
            // 如果点太远，可以跳过但不要断开路径
          }
          
          if (firstPoint) {
            ctx.moveTo(x, y);
            firstPoint = false;
          } else {
            ctx.lineTo(x, y);
          }
        });
        
        ctx.closePath();
        ctx.fill();
        ctx.stroke();
      }

      // 添加地名标注（主要地点）
      if (zoom >= 6) {
        ctx.fillStyle = 'rgba(255, 255, 255, 0.8)';
        ctx.font = 'bold 11px sans-serif';
        ctx.shadowColor = 'rgba(0, 0, 0, 0.8)';
        ctx.shadowBlur = 3;

        const labels = [
          { name: 'Shanghai', lon: 121.5, lat: 31.2 },
          { name: 'Singapore', lon: 103.85, lat: 1.29 },
          { name: 'Hong Kong', lon: 114.2, lat: 22.3 },
          { name: 'Taiwan', lon: 121.0, lat: 23.5 },
          { name: 'Philippines', lon: 122.0, lat: 12.0 },
          { name: 'Malaysia', lon: 102.0, lat: 3.0 },
          { name: 'Indonesia', lon: 120.0, lat: -5.0 },
          { name: 'Thailand', lon: 100.5, lat: 13.7 },
          { name: 'Vietnam', lon: 106.7, lat: 10.8 }
        ];

        labels.forEach(label => {
          const [x, y] = project([label.lon, label.lat]);
          if (x > 0 && x < width && y > 0 && y < height) {
            ctx.fillText(label.name, x + 5, y - 5);
          }
        });

        ctx.shadowBlur = 0;
      }

      ctx.restore();
    }

    // 增强的本地海图底图（替代有问题的OSM瓦片）
    function drawEnhancedLocalBasemap(
      ctx: CanvasRenderingContext2D,
      width: number,
      height: number,
      center: LonLat,
      zoom: number
    ) {
      // 深海蓝渐变背景
      const gradient = ctx.createLinearGradient(0, 0, 0, height);
      gradient.addColorStop(0, '#0a2540');
      gradient.addColorStop(0.5, '#0d3058');
      gradient.addColorStop(1, '#0a2540');
      ctx.fillStyle = gradient;
      ctx.fillRect(0, 0, width, height);

      // 添加海洋纹理效果
      ctx.save();
      ctx.globalAlpha = 0.1;
      
      // 波浪纹理
      for (let y = 0; y < height; y += 40) {
        ctx.strokeStyle = 'rgba(100, 150, 200, 0.3)';
        ctx.lineWidth = 1;
        ctx.beginPath();
        for (let x = 0; x < width; x += 5) {
          const waveY = y + Math.sin((x + Date.now() * 0.0001) * 0.02) * 10;
          if (x === 0) ctx.moveTo(x, waveY);
          else ctx.lineTo(x, waveY);
        }
        ctx.stroke();
      }
      
      // 深度等高线效果
      ctx.strokeStyle = 'rgba(50, 100, 150, 0.2)';
      ctx.lineWidth = 0.5;
      const contourStep = zoom >= 10 ? 0.01 : zoom >= 8 ? 0.05 : 0.1;
      
      for (let lat = Math.floor(center[1] / contourStep) * contourStep - 2; 
           lat <= Math.floor(center[1] / contourStep) * contourStep + 2; 
           lat += contourStep) {
        for (let lon = Math.floor(center[0] / contourStep) * contourStep - 2;
             lon <= Math.floor(center[0] / contourStep) * contourStep + 2;
             lon += contourStep) {
          const [x, y] = project([lon, lat]);
          ctx.beginPath();
          ctx.arc(x, y, 50 + Math.random() * 100, 0, Math.PI * 2);
          ctx.stroke();
        }
      }
      
      ctx.restore();

      // 增强的经纬网格
      const gridStep = zoom >= 10 ? 0.01 : zoom >= 8 ? 0.05 : zoom >= 6 ? 0.1 : zoom >= 4 ? 0.5 : 1;
      
      ctx.save();
      ctx.strokeStyle = 'rgba(100, 150, 200, 0.15)';
      ctx.lineWidth = 1;
      ctx.setLineDash([5, 10]);
      
      // 经线
      for (let lon = Math.floor(center[0] / gridStep) * gridStep - 180; 
           lon <= Math.floor(center[0] / gridStep) * gridStep + 180; 
           lon += gridStep) {
        const [x1, y1] = project([lon, -85]);
        const [x2, y2] = project([lon, 85]);
        ctx.beginPath();
        ctx.moveTo(x1, y1);
        ctx.lineTo(x2, y2);
        ctx.stroke();
      }
      
      // 纬线
      for (let lat = Math.floor(center[1] / gridStep) * gridStep - 85; 
           lat <= Math.floor(center[1] / gridStep) * gridStep + 85; 
           lat += gridStep) {
        const [x1, y1] = project([-180, lat]);
        const [x2, y2] = project([180, lat]);
        ctx.beginPath();
        ctx.moveTo(x1, y1);
        ctx.lineTo(x2, y2);
        ctx.stroke();
      }
      
      ctx.setLineDash([]);
      ctx.restore();

      // 坐标标注
      ctx.save();
      ctx.fillStyle = 'rgba(200, 220, 240, 0.6)';
      ctx.font = '10px monospace';
      
      // 标注主要经纬线
      const labelStep = gridStep * 2;
      for (let lon = Math.floor(center[0] / labelStep) * labelStep; 
           lon <= Math.floor(center[0] / labelStep) * labelStep + labelStep * 2; 
           lon += labelStep) {
        const [x, y] = project([lon, center[1]]);
        if (x > 0 && x < width) {
          ctx.fillText(`${lon.toFixed(1)}°`, x + 2, height - 5);
        }
      }
      
      for (let lat = Math.floor(center[1] / labelStep) * labelStep; 
           lat <= Math.floor(center[1] / labelStep) * labelStep + labelStep * 2; 
           lat += labelStep) {
        const [x, y] = project([center[0], lat]);
        if (y > 0 && y < height) {
          ctx.fillText(`${lat.toFixed(1)}°`, 5, y - 2);
        }
      }
      
      ctx.restore();
    }

    // 本地渲染的航标和海洋标记
    function drawLocalSeamarks(
      ctx: CanvasRenderingContext2D,
      width: number,
      height: number,
      center: LonLat,
      zoom: number
    ) {
      // 中国东海和南海主要航标位置
      const seamarks = [
        // 长江口航标
        { lon: 121.90, lat: 31.05, type: 'lighthouse', name: 'Changjiang Light' },
        { lon: 122.10, lat: 30.90, type: 'buoy', color: 'red' },
        { lon: 122.05, lat: 30.85, type: 'buoy', color: 'green' },
        
        // 舟山群岛航标
        { lon: 122.20, lat: 30.00, type: 'lighthouse', name: 'Zhoushan Light' },
        { lon: 122.30, lat: 29.90, type: 'beacon' },
        
        // 台湾海峡航标
        { lon: 120.20, lat: 24.50, type: 'lighthouse', name: 'Taiwan Strait Light' },
        { lon: 119.50, lat: 23.50, type: 'buoy', color: 'red' },
        
        // 南海航标
        { lon: 114.00, lat: 15.00, type: 'lighthouse', name: 'Spratly Light' },
        { lon: 110.00, lat: 10.00, type: 'beacon' },
        
        // 马六甲海峡入口
        { lon: 104.00, lat: 2.50, type: 'lighthouse', name: 'Malacca Light' },
        { lon: 103.90, lat: 1.30, type: 'buoy', color: 'green' },
        
        // 新加坡港口航标
        { lon: 103.85, lat: 1.26, type: 'lighthouse', name: 'Singapore Light' },
        { lon: 103.84, lat: 1.25, type: 'buoy', color: 'red' },
        { lon: 103.86, lat: 1.27, type: 'buoy', color: 'green' }
      ];

      ctx.save();
      
      seamarks.forEach(mark => {
        const [x, y] = project([mark.lon, mark.lat]);
        
        if (x < -50 || x > width + 50 || y < -50 || y > height + 50) return;
        
        switch(mark.type) {
          case 'buoy':
            // 浮标
            ctx.fillStyle = mark.color === 'red' ? '#ff4444' : '#44ff44';
            ctx.strokeStyle = '#ffffff';
            ctx.lineWidth = 2;
            ctx.beginPath();
            ctx.arc(x, y, 6, 0, Math.PI * 2);
            ctx.fill();
            ctx.stroke();
            
            // 浮标顶标
            ctx.beginPath();
            if (mark.color === 'red') {
              // 红色浮标：三角形顶标
              ctx.moveTo(x, y - 10);
              ctx.lineTo(x - 5, y - 5);
              ctx.lineTo(x + 5, y - 5);
              ctx.closePath();
            } else {
              // 绿色浮标：方形顶标
              ctx.rect(x - 4, y - 10, 8, 5);
            }
            ctx.fill();
            break;
            
          case 'lighthouse':
            // 灯塔
            ctx.fillStyle = '#ffff88';
            ctx.strokeStyle = '#ff8800';
            ctx.lineWidth = 2;
            
            // 灯塔主体
            ctx.beginPath();
            ctx.moveTo(x, y - 15);
            ctx.lineTo(x - 5, y);
            ctx.lineTo(x + 5, y);
            ctx.closePath();
            ctx.fill();
            ctx.stroke();
            
            // 光芒效果
            ctx.strokeStyle = 'rgba(255, 255, 100, 0.5)';
            ctx.lineWidth = 1;
            for (let angle = 0; angle < Math.PI * 2; angle += Math.PI / 6) {
              ctx.beginPath();
              ctx.moveTo(x, y - 8);
              ctx.lineTo(
                x + Math.cos(angle) * 15,
                y - 8 + Math.sin(angle) * 15
              );
              ctx.stroke();
            }
            break;
            
          case 'beacon':
            // 信标
            ctx.fillStyle = '#88ffff';
            ctx.strokeStyle = '#0088ff';
            ctx.lineWidth = 2;
            
            ctx.beginPath();
            ctx.rect(x - 5, y - 5, 10, 10);
            ctx.fill();
            ctx.stroke();
            
            // 中心标记
            ctx.fillStyle = '#ffffff';
            ctx.beginPath();
            ctx.arc(x, y, 2, 0, Math.PI * 2);
            ctx.fill();
            break;
        }
      });
      
      ctx.restore();
    }

    function getVisibleBounds() {
      const { center, zoom, width, height } = vp.current;
      
      // 计算视窗四角的地理坐标
      const margin = 0.1; // 10% 边距用于缓冲
      const w_margin = width * (1 + margin);
      const h_margin = height * (1 + margin);
      
      // 使用逆投影计算边界
      const topLeft = xyToLonLat(-w_margin/2, -h_margin/2, center[0], center[1], zoom, width, height);
      const bottomRight = xyToLonLat(w_margin/2, h_margin/2, center[0], center[1], zoom, width, height);
      
      return {
        minLon: Math.min(topLeft.lon, bottomRight.lon),
        maxLon: Math.max(topLeft.lon, bottomRight.lon),
        minLat: Math.min(topLeft.lat, bottomRight.lat),
        maxLat: Math.max(topLeft.lat, bottomRight.lat)
      };
    }

    // 快速边界检查：几何体是否在视窗内
    function isGeometryVisible(coords: LonLat[][], bounds: ReturnType<typeof getVisibleBounds>) {
      if (!coords || coords.length === 0) return false;
      
      // 检查几何体边界框是否与视窗相交
      for (const ring of coords) {
        for (const [lon, lat] of ring) {
          if (lon >= bounds.minLon && lon <= bounds.maxLon && 
              lat >= bounds.minLat && lat <= bounds.maxLat) {
            return true;
          }
        }
      }
      return false;
    }

    function drawPolygon(
      ctx: CanvasRenderingContext2D, 
      coords: LonLat[][], 
      fill: boolean, 
      stroke: boolean
    ) {
      for (const ring of coords) {
        if (ring.length < 3) continue;
        
        ctx.beginPath();
        ring.forEach((p, i) => {
          const [x, y] = project(p);
          if (i === 0) {
            ctx.moveTo(x, y);
          } else {
            ctx.lineTo(x, y);
          }
        });
        ctx.closePath();
        
        if (fill) ctx.fill();
        if (stroke) ctx.stroke();
      }
    }

    // 绘制助航设备符号
    function drawAidToNavigation(ctx: CanvasRenderingContext2D, x: number, y: number, type: string, color?: string) {
      ctx.save();
      ctx.translate(x, y);
      
      switch (type) {
        case 'lighthouse':
          // 灯塔符号：三角形 + 光束
          ctx.fillStyle = color || "#ffeb3b";
          ctx.strokeStyle = "#333";
          ctx.lineWidth = 1;
          
          ctx.beginPath();
          ctx.moveTo(0, -8);
          ctx.lineTo(-6, 6);
          ctx.lineTo(6, 6);
          ctx.closePath();
          ctx.fill();
          ctx.stroke();
          
          // 光束
          ctx.strokeStyle = "rgba(255, 235, 59, 0.6)";
          ctx.lineWidth = 2;
          ctx.setLineDash([3, 2]);
          ctx.beginPath();
          ctx.arc(0, 0, 15, -Math.PI/3, -2*Math.PI/3, true);
          ctx.stroke();
          ctx.setLineDash([]);
          break;
          
        case 'buoy':
          // 浮标符号：菱形
          ctx.fillStyle = color || "#e53e3e";
          ctx.strokeStyle = "#333";
          ctx.lineWidth = 1;
          
          ctx.beginPath();
          ctx.moveTo(0, -5);
          ctx.lineTo(4, 0);
          ctx.lineTo(0, 5);
          ctx.lineTo(-4, 0);
          ctx.closePath();
          ctx.fill();
          ctx.stroke();
          break;
          
        case 'beacon':
          // 信标符号：圆点 + 十字
          ctx.fillStyle = color || "#38a169";
          ctx.strokeStyle = "#333";
          ctx.lineWidth = 1;
          
          ctx.beginPath();
          ctx.arc(0, 0, 3, 0, Math.PI * 2);
          ctx.fill();
          ctx.stroke();
          
          // 十字
          ctx.beginPath();
          ctx.moveTo(-6, 0);
          ctx.lineTo(6, 0);
          ctx.moveTo(0, -6);
          ctx.lineTo(0, 6);
          ctx.stroke();
          break;
          
        default:
          // 默认符号：圆点
          ctx.fillStyle = color || "#4a90e2";
          ctx.beginPath();
          ctx.arc(0, 0, 3, 0, Math.PI * 2);
          ctx.fill();
          break;
      }
      
      ctx.restore();
    }

    // 计算两点间距离（米）
    function haversineDistance(lat1: number, lon1: number, lat2: number, lon2: number): number {
      const R = 6371000; // 地球半径（米）
      const dLat = (lat2 - lat1) * Math.PI / 180;
      const dLon = (lon2 - lon1) * Math.PI / 180;
      const a = Math.sin(dLat/2) * Math.sin(dLat/2) +
                Math.cos(lat1 * Math.PI / 180) * Math.cos(lat2 * Math.PI / 180) *
                Math.sin(dLon/2) * Math.sin(dLon/2);
      const c = 2 * Math.atan2(Math.sqrt(a), Math.sqrt(1-a));
      return R * c;
    }

    // 计算方位角（度）
    function calculateBearing(lat1: number, lon1: number, lat2: number, lon2: number): number {
      const dLon = (lon2 - lon1) * Math.PI / 180;
      const lat1Rad = lat1 * Math.PI / 180;
      const lat2Rad = lat2 * Math.PI / 180;
      const y = Math.sin(dLon) * Math.cos(lat2Rad);
      const x = Math.cos(lat1Rad) * Math.sin(lat2Rad) - 
                Math.sin(lat1Rad) * Math.cos(lat2Rad) * Math.cos(dLon);
      const brng = Math.atan2(y, x);
      return ((brng * 180 / Math.PI) + 360) % 360;
    }
  };

  return <canvas ref={canvasRef} style={props.style} />;
});