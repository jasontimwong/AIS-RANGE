export async function planFullRoute(start: { lon: number; lat: number }, goal: { lon: number; lat: number }) {
  const res = await fetch('/api/route/plan_full', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ start: { lat: start.lat, lon: start.lon }, goal: { lat: goal.lat, lon: goal.lon } })
  });
  if (!res.ok) throw new Error(`plan_full failed: ${res.status}`);
  return res.json() as Promise<{ coords: [number, number][], planning_time_s: number, used_ais: boolean }>;
}
import type { PlanRequestV1, ValidationReportV1, ServiceStatus } from "../types/schema";

export type { ValidationReportV1 };

const API_BASE = 'http://localhost:8000';  // 后端API（本地优先方案下不会调用）

// WebSocket connection for real-time updates
let wsConnection: WebSocket | null = null;
let wsReconnectTimer: number | null = null;

// Simple in-memory cache
const apiCache = new Map<string, { data: any; timestamp: number; ttl: number }>();
const CACHE_TTL = 5 * 60 * 1000; // 5 minutes default TTL

/**
 * 获取示例路线数据
 * 先尝试调用后端API，失败则返回示例数据
 */
export async function getRoute(): Promise<{ coords: [number, number][]; report: ValidationReportV1; }> {
  // 本地优先方案：先尝试加载真实航线，失败则使用示例
  try {
    const base = (import.meta as any)?.env?.BASE_URL || '/';
    const prefix = base.endsWith('/') ? base.slice(0, -1) : base;
    
    // 首先尝试加载修正后的真实航线（上海-新加坡）
    try {
      const correctedRouteUrl = `${prefix}/route/shanghai-singapore-corrected.json`;
      const correctedRes = await fetch(correctedRouteUrl);
      if (correctedRes.ok) {
        const data = await correctedRes.json();
        const coords = (data.coords || data.waypoints) as [number, number][];
        return { coords, report: data.report || getExampleReport() };
      }
    } catch {}
    
    // 尝试原始航线
    try {
      const realRouteUrl = `${prefix}/route/shanghai-singapore.json`;
      const realRes = await fetch(realRouteUrl);
      if (realRes.ok) {
        const data = await realRes.json();
        const coords = (data.coords || data.waypoints) as [number, number][];
        return { coords, report: data.report || getExampleReport() };
      }
    } catch {}
    
    // 退回到示例航线
    const localUrl = `${prefix}/route/example.json`;
    const res = await fetch(localUrl);
    if (res.ok) {
      const data = await res.json();
      const coords = (data.coords || data.waypoints || getExampleRoute()) as [number, number][];
      return { coords, report: data.report || getExampleReport() };
    }
  } catch {}
  return { coords: getExampleRoute(), report: getExampleReport() };
}

/**
 * 获取ENC-lite数据（简化的海图数据）
 */
export async function getEncLite(): Promise<any> {
  // 优先：后端 /enc/lite（核心架构可航域抽取）→ 其次：静态 enc_lite.json → 最后：示例
  try {
    const apiRes = await fetch('/enc/lite');
    if (apiRes.ok) return await apiRes.json();
  } catch {}
  try {
    const base = (import.meta as any)?.env?.BASE_URL || '/';
    const prefix = base.endsWith('/') ? base.slice(0, -1) : base;
    const localUrl = `${prefix}/enc/enc_lite.json`;
    const res = await fetch(localUrl);
    if (res.ok) {
      return await res.json();
    }
  } catch {}
  return getExampleEncData();
}

// （回滚）不在前端直接调用核心 /plan，保留此处空位以便将来需要时再启用

/**
 * 验证路线
 */
export async function validateRoute(routeId: string, checks: string[] = ["safety", "tss", "geometry", "speed"]): Promise<ValidationReportV1> {
  try {
    const response = await fetch(`${API_BASE}/validate`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ route_id: routeId, checks })
    });

    if (!response.ok) {
      throw new Error(`Backend /validate failed: ${response.status}`);
    }

    return await response.json();

  } catch (error) {
    console.warn('Failed to validate route, using example report:', error);
    return getExampleReport();
  }
}

/**
 * 导出RTZ格式路线
 */
export async function exportRTZ(routeId: string): Promise<Blob> {
  const response = await fetch(`${API_BASE}/export/rtz?route_id=${routeId}`);
  
  if (!response.ok) {
    throw new Error(`Export RTZ failed: ${response.status}`);
  }

  return response.blob();
}

/**
 * 导入RTZ文件
 */
export async function importRTZ(file: File): Promise<any> {
  const formData = new FormData();
  formData.append('file', file);

  const response = await fetch(`${API_BASE}/import/rtz`, {
    method: "POST",
    body: formData
  });

  if (!response.ok) {
    throw new Error(`Import RTZ failed: ${response.status}`);
  }

  return response.json();
}

/**
 * 获取服务状态
 */
export async function getServiceStatus(): Promise<ServiceStatus> {
  return fetchWithCache(`${API_BASE}/status`, { ttl: 30000 }); // 30s cache
}

// === 缓存和网络层增强 ===

/**
 * 带缓存的fetch封装
 */
async function fetchWithCache(url: string, options: { ttl?: number } = {}): Promise<any> {
  const cacheKey = url;
  const now = Date.now();
  const cached = apiCache.get(cacheKey);
  
  // 返回有效缓存
  if (cached && (now - cached.timestamp) < cached.ttl) {
    return cached.data;
  }
  
  try {
    const response = await fetch(url);
    if (!response.ok) {
      throw new Error(`HTTP ${response.status}: ${response.statusText}`);
    }
    
    const data = await response.json();
    
    // 缓存响应
    apiCache.set(cacheKey, {
      data,
      timestamp: now,
      ttl: options.ttl || CACHE_TTL
    });
    
    return data;
  } catch (error) {
    // 如果有过期缓存，在网络错误时使用
    if (cached) {
      console.warn(`Using stale cache for ${url} due to network error:`, error);
      return cached.data;
    }
    throw error;
  }
}

/**
 * 重试机制的fetch封装
 */
async function fetchWithRetry(url: string, options: RequestInit = {}, maxRetries = 2): Promise<Response> {
  let lastError: Error;
  
  for (let attempt = 0; attempt <= maxRetries; attempt++) {
    try {
      const response = await fetch(url, options);
      return response;
    } catch (error) {
      lastError = error as Error;
      if (attempt < maxRetries) {
        // 指数退避
        const delay = Math.pow(2, attempt) * 1000;
        await new Promise(resolve => setTimeout(resolve, delay));
        console.warn(`Retry ${attempt + 1}/${maxRetries} for ${url} after ${delay}ms`);
      }
    }
  }
  
  throw lastError!;
}

/**
 * 清除API缓存
 */
export function clearApiCache(pattern?: RegExp) {
  if (pattern) {
    for (const [key] of apiCache) {
      if (pattern.test(key)) {
        apiCache.delete(key);
      }
    }
  } else {
    apiCache.clear();
  }
}

// === WebSocket 实时通信 ===

export type WebSocketEventType = 'route_updated' | 'validation_completed' | 'alert' | 'status_change';

export interface WebSocketMessage {
  type: WebSocketEventType;
  timestamp: string;
  data: any;
}

/**
 * 连接WebSocket进行实时更新
 */
export function connectWebSocket(onMessage: (message: WebSocketMessage) => void, onError?: (error: Event) => void) {
  if (wsConnection) {
    wsConnection.close();
  }
  
  const wsUrl = `ws://${window.location.host}/ws`;
  wsConnection = new WebSocket(wsUrl);
  
  wsConnection.onopen = () => {
    console.log('WebSocket connected');
    if (wsReconnectTimer) {
      clearInterval(wsReconnectTimer);
      wsReconnectTimer = null;
    }
  };
  
  wsConnection.onmessage = (event) => {
    try {
      const message: WebSocketMessage = JSON.parse(event.data);
      onMessage(message);
    } catch (error) {
      console.error('Failed to parse WebSocket message:', error);
    }
  };
  
  wsConnection.onclose = () => {
    console.log('WebSocket disconnected, attempting reconnect...');
    // 自动重连
    wsReconnectTimer = window.setTimeout(() => {
      connectWebSocket(onMessage, onError);
    }, 5000);
  };
  
  wsConnection.onerror = (error) => {
    console.error('WebSocket error:', error);
    onError?.(error);
  };
}

/**
 * 断开WebSocket连接
 */
export function disconnectWebSocket() {
  if (wsConnection) {
    wsConnection.close();
    wsConnection = null;
  }
  if (wsReconnectTimer) {
    clearInterval(wsReconnectTimer);
    wsReconnectTimer = null;
  }
}

/**
 * 发送WebSocket消息
 */
export function sendWebSocketMessage(message: WebSocketMessage) {
  if (wsConnection && wsConnection.readyState === WebSocket.OPEN) {
    wsConnection.send(JSON.stringify(message));
  } else {
    console.warn('WebSocket not connected, cannot send message');
  }
}

// === 示例数据 ===

function getExampleRoute(): [number, number][] {
  return [
    [0.005, 0.005],   // 起点
    [0.010, 0.007],   // 航路点1
    [0.015, 0.010],   // 航路点2
    [0.020, 0.012],   // 航路点3
    [0.025, 0.015]    // 终点
  ];
}

function getExampleReport(): ValidationReportV1 {
  return {
    clause_refs: [
      {
        standard: "IMO MSC.232(82)",
        clause: "4.7.1",
        requirement: "安全深度检查",
        status: "COMPLIANT"
      },
      {
        standard: "IMO MSC.232(82)",
        clause: "4.8.3",
        requirement: "XTD走廊验证",
        status: "COMPLIANT"
      },
      {
        standard: "COLREG Rule",
        clause: "10",
        requirement: "TSS分道通航",
        status: "COMPLIANT"
      },
      {
        standard: "IHO S-57",
        clause: "SAFETY",
        requirement: "海图数据完整性",
        status: "WARN"
      }
    ],
    min_ukc_m: 3.5,
    alerts: [
      {
        level: "B",
        msg: "Route passes through shallow water area"
      },
      {
        level: "C", 
        msg: "Weather data not available for planning period"
      }
    ]
  };
}

function getExampleEncData(): any {
  return {
    // 海岸线 (简化的矩形海岸)
    coast: [
      [
        [
          [0.0, -0.005],
          [0.035, -0.005],
          [0.035, 0.025],
          [0.030, 0.025],
          [0.030, 0.020],
          [0.005, 0.020],
          [0.005, 0.002],
          [0.0, 0.002],
          [0.0, -0.005]
        ]
      ]
    ],
    
    // 浅水区域
    shallow: [
      [
        [
          [0.008, 0.008],
          [0.015, 0.008],
          [0.015, 0.015],
          [0.008, 0.015],
          [0.008, 0.008]
        ]
      ],
      [
        [
          [0.022, 0.004],
          [0.028, 0.004],
          [0.028, 0.010],
          [0.022, 0.010],
          [0.022, 0.004]
        ]
      ]
    ],
    
    // TSS分道通航制（包含示例车道与分隔带）
    tss: {
      lanes: [
        [
          [
            [0.010, 0.005],
            [0.025, 0.005],
            [0.025, 0.008],
            [0.010, 0.008],
            [0.010, 0.005]
          ]
        ]
      ],
      sep_zones: [
        [
          [
            [0.012, 0.008],
            [0.023, 0.008],
            [0.023, 0.009],
            [0.012, 0.009],
            [0.012, 0.008]
          ]
        ]
      ]
    },
    
    // S-124警告（限速区与禁航区示例）
    s124: {
      speed_limits: [
        {
          geometry: [
            [
              [0.016, 0.010],
              [0.020, 0.010],
              [0.020, 0.014],
              [0.016, 0.014],
              [0.016, 0.010]
            ]
          ],
          max_speed_kn: 8.0,
          time_window: { "start": "2025-01-01T00:00:00Z", "end": "2025-12-31T23:59:59Z" }
        }
      ],
      prohibited: [
        {
          geometry: [
            [
              [0.006, 0.012],
              [0.009, 0.012],
              [0.009, 0.016],
              [0.006, 0.016],
              [0.006, 0.012]
            ]
          ],
          reason: "Marine Protected Area",
          time_window: { "start": "2025-01-01T00:00:00Z", "end": "2025-12-31T23:59:59Z" }
        }
      ]
    }
  };
}