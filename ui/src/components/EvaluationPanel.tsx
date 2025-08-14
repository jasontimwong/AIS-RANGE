import React, { useMemo } from "react";

export interface RouteComparisonData {
  original_route?: Array<[number, number]>; // (lat, lon)
  dynamic_route?: Array<[number, number]>;  // (lat, lon)
  avoidance_points?: Array<[number, number]>; // (lat, lon)
  active_threats?: string[];
  last_update?: string;
}

interface Props {
  routeComparison: RouteComparisonData | null;
  // 前端可视化用的路线（[lon, lat]），用于确保面板随UI实际路径变化而刷新
  originalRouteLonLat?: Array<[number, number]>;
  dynamicRouteLonLat?: Array<[number, number]>;
}

function toRadians(deg: number): number {
  return (deg * Math.PI) / 180.0;
}

function haversineNm(lat1: number, lon1: number, lat2: number, lon2: number): number {
  const Rm = 6371000; // meters
  const dLat = toRadians(lat2 - lat1);
  const dLon = toRadians(lon2 - lon1);
  const a = Math.sin(dLat / 2) ** 2 + Math.cos(toRadians(lat1)) * Math.cos(toRadians(lat2)) * Math.sin(dLon / 2) ** 2;
  const c = 2 * Math.atan2(Math.sqrt(a), Math.sqrt(1 - a));
  const meters = Rm * c;
  return meters / 1852.0; // meters to nautical miles
}

function polylineLengthNm(points: Array<[number, number]> | undefined): number {
  if (!points || points.length < 2) return 0;
  let sum = 0;
  for (let i = 0; i < points.length - 1; i++) {
    const [lat1, lon1] = points[i];
    const [lat2, lon2] = points[i + 1];
    sum += haversineNm(lat1, lon1, lat2, lon2);
  }
  return sum;
}

function polylineLengthFromLonLat(points: Array<[number, number]> | undefined): number {
  if (!points || points.length < 2) return 0;
  let sum = 0;
  for (let i = 0; i < points.length - 1; i++) {
    const [lon1, lat1] = points[i];
    const [lon2, lat2] = points[i + 1];
    sum += haversineNm(lat1, lon1, lat2, lon2);
  }
  return sum;
}

export const EvaluationPanel: React.FC<Props> = ({ routeComparison, originalRouteLonLat, dynamicRouteLonLat }) => {
  const [params, setParams] = React.useState<{ vessel_speed_kn: number; fuel_per_nm_ton: number; fuel_price_usd_per_ton: number; co2_per_ton_fuel: number } | null>(null);

  React.useEffect(() => {
    // 拉取后端评估参数，保证与系统船舶信息一致
    fetch('/api/eval/params').then(r => r.ok ? r.json() : null).then(data => {
      if (data) setParams(data);
    }).catch(() => {});
  }, []);

  const metrics = useMemo(() => {
    if (!params) return null;
    // 1) 优先使用“段级对比”：在原始航线中找到与动态路径起/终点最近的锚点区间，
    //    用该区间长度与动态路径长度进行比较，更符合“避让段影响”的评估语义。
    let deltaNm = 0;
    let dynamicNm = 0;
    let originalNm = 0;

    const dyn = dynamicRouteLonLat && dynamicRouteLonLat.length >= 2 ? dynamicRouteLonLat : undefined;
    const base = originalRouteLonLat && originalRouteLonLat.length >= 2 ? originalRouteLonLat : undefined;

    if (dyn && base) {
      const start = dyn[0];
      const end = dyn[dyn.length - 1];
      // 找到原始路径中与动态路径起/终点最近的索引
      const nearestIdx = (list: Array<[number, number]>, p: [number, number]) => {
        let best = 0; let bestD = Infinity;
        for (let i = 0; i < list.length; i++) {
          const d = haversineNm(list[i][1], list[i][0], p[1], p[0]);
          if (d < bestD) { bestD = d; best = i; }
        }
        return best;
      };
      const iStart = nearestIdx(base, start);
      const iEnd = nearestIdx(base, end);
      const s = Math.min(iStart, iEnd);
      const e = Math.max(iStart, iEnd);
      // 计算原始路径该区间的长度
      let originalSegNm = 0;
      for (let i = s; i < e; i++) {
        const [lon1, lat1] = base[i];
        const [lon2, lat2] = base[i + 1];
        originalSegNm += haversineNm(lat1, lon1, lat2, lon2);
      }
      const dynamicSegNm = polylineLengthFromLonLat(dyn);
      originalNm = originalSegNm;
      dynamicNm = dynamicSegNm;
      deltaNm = dynamicSegNm - originalSegNm;
    }

    // 2) 若段级对比不可用，则回退到整条路径长度对比（前端优先，后端次之）
    if (!dyn || !base) {
      let originalWhole = base ? polylineLengthFromLonLat(base) : 0;
      let dynamicWhole = dyn ? polylineLengthFromLonLat(dyn) : 0;
      if ((!originalWhole || !dynamicWhole) && routeComparison) {
        originalWhole = originalWhole || polylineLengthNm(routeComparison.original_route);
        dynamicWhole = dynamicWhole || polylineLengthNm(routeComparison.dynamic_route);
      }
      originalNm = originalWhole;
      dynamicNm = dynamicWhole;
      deltaNm = dynamicWhole - originalWhole;
    }

    // 允许负值（动态路径更短时），但在展示时可取绝对值或保留符号；此处保留符号以忠实反映影响

    // 评估参数（来自后端配置）
    const vesselSpeedKn = params.vessel_speed_kn;
    const fuelPerNmTon = params.fuel_per_nm_ton;
    const fuelPriceUSDPerTon = params.fuel_price_usd_per_ton;
    const co2FactorPerTonFuel = params.co2_per_ton_fuel;

    const originalHours = originalNm / vesselSpeedKn;
    const dynamicHours = dynamicNm / vesselSpeedKn;
    const deltaHours = (dynamicNm - originalNm) / vesselSpeedKn;

    const originalFuelTon = originalNm * fuelPerNmTon;
    const dynamicFuelTon = dynamicNm * fuelPerNmTon;
    const deltaFuelTon = (dynamicNm - originalNm) * fuelPerNmTon;

    const deltaFuelCostUSD = deltaFuelTon * fuelPriceUSDPerTon;
    const deltaCO2Ton = deltaFuelTon * co2FactorPerTonFuel;

    return {
      originalNm,
      dynamicNm,
      deltaNm,
      originalHours,
      dynamicHours,
      deltaHours,
      deltaFuelTon,
      deltaFuelCostUSD,
      deltaCO2Ton,
      threats: routeComparison?.active_threats?.length || 0,
      lastUpdate: routeComparison?.last_update,
    };
  }, [routeComparison, originalRouteLonLat, dynamicRouteLonLat, params]);

  if (!metrics) return null;

  return (
    <div style={{
      background: "rgba(46, 52, 64, 0.95)",
      color: "#d8dee9",
      border: "1px solid #3b4252",
      borderRadius: 4,
      padding: 10,
      minWidth: 260,
    }}>
      <div style={{ color: "#81a1c1", fontWeight: 600, marginBottom: 6 }}>
        📈 避让影响评估
      </div>
      <div style={{ fontSize: 12, lineHeight: 1.5 }}>
        <div>原航程: <span style={{ color: "#88c0d0" }}>{metrics.originalNm.toFixed(1)} nm</span></div>
        <div>新航程: <span style={{ color: "#88c0d0" }}>{metrics.dynamicNm.toFixed(1)} nm</span></div>
        <div>航程增加: <span style={{ color: "#d08770" }}>{metrics.deltaNm.toFixed(1)} nm</span></div>
        <div style={{ marginTop: 6 }}>ETA延长: <span style={{ color: "#d08770" }}>{(metrics.deltaHours).toFixed(2)} 小时</span></div>
        <div>额外燃油: <span style={{ color: "#d08770" }}>{metrics.deltaFuelTon.toFixed(2)} 吨</span></div>
        <div>燃油成本: <span style={{ color: "#a3be8c" }}>${metrics.deltaFuelCostUSD.toFixed(0)}</span></div>
        <div>额外排放: <span style={{ color: "#bf616a" }}>{metrics.deltaCO2Ton.toFixed(2)} 吨CO₂</span></div>
        {metrics.threats > 0 && (
          <div style={{ marginTop: 6, color: "#ebcb8b" }}>活跃威胁: {metrics.threats} 个</div>
        )}
        {metrics.lastUpdate && (
          <div style={{ color: "#5e81ac", marginTop: 4 }}>更新: {new Date(metrics.lastUpdate).toLocaleString()}</div>
        )}
      </div>
    </div>
  );
};


