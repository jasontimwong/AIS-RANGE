import { useState, useEffect, useRef } from 'react';
// 与 CanvasMap 中 AISTarget 结构保持一致
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

export const useAISData = (enabled: boolean = false) => {
  const [targets, setTargets] = useState<AISTarget[]>([]);
  const [connected, setConnected] = useState(false);
  const wsRef = useRef<WebSocket | null>(null);

  useEffect(() => {
    if (!enabled) {
      // 如果禁用，断开连接
      if (wsRef.current) {
        wsRef.current.close();
        wsRef.current = null;
      }
      setTargets([]);
      setConnected(false);
      return;
    }

    // 建立WebSocket连接（根据当前页面协议/主机构造，走Vite代理，从而避免CORS）
    const connect = () => {
      try {
        const isSecure = window.location.protocol === 'https:';
        const wsProtocol = isSecure ? 'wss:' : 'ws:';
        const wsHost = window.location.host; // 包含端口
        const wsUrl = `${wsProtocol}//${wsHost}/ws/ais`;
        const ws = new WebSocket(wsUrl);
        
        ws.onopen = () => {
          console.log('AIS WebSocket connected');
          setConnected(true);
        };

        ws.onmessage = (event) => {
          try {
            const data = JSON.parse(event.data);
            if (data.type === 'ais_update' && data.targets) {
              setTargets(data.targets);
            }
          } catch (e) {
            console.error('Failed to parse AIS data:', e);
          }
        };

        ws.onerror = (error) => {
          console.error('AIS WebSocket error:', error);
        };

        ws.onclose = () => {
          console.log('AIS WebSocket disconnected');
          setConnected(false);
          // 尝试重连
          setTimeout(connect, 5000);
        };

        wsRef.current = ws;
      } catch (e) {
        console.error('Failed to connect AIS WebSocket:', e);
        setTimeout(connect, 5000);
      }
    };

    connect();

    // 清理函数
    return () => {
      if (wsRef.current) {
        wsRef.current.close();
        wsRef.current = null;
      }
    };
  }, [enabled]);

  // 获取指定范围内的目标
  const getTargetsInRange = async (lat: number, lon: number, range: number) => {
    try {
      const response = await fetch(
        `/api/ais/targets?lat=${lat}&lon=${lon}&range_nm=${range}`
      );
      if (response.ok) {
        const data = await response.json();
        return data.targets;
      }
    } catch (e) {
      console.error('Failed to fetch AIS targets:', e);
    }
    return [];
  };

  // 评估风险
  const assessRisk = async (lat: number, lon: number, sog: number, cog: number) => {
    try {
      const response = await fetch('/api/ais/risk', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ lat, lon, sog, cog })
      });
      if (response.ok) {
        return await response.json();
      }
    } catch (e) {
      console.error('Failed to assess risk:', e);
    }
    return null;
  };

  return {
    targets,
    connected,
    getTargetsInRange,
    assessRisk
  };
};