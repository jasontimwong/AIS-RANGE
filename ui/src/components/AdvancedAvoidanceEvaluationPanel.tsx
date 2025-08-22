import React from "react";

type LonLat = [number, number]; // [lon, lat]

export interface EvalParams {
  vessel_speed_kn: number;
  fuel_per_nm_ton: number;
  fuel_price_usd_per_ton: number;
  co2_per_ton_fuel: number;
}

interface Props {
  originalRoute: LonLat[];
  dynamicRoute: LonLat[];
  evalParams?: EvalParams; // 若未传，组件会自行拉取 /api/eval/params
  mode?: 'simple' | 'power'; // 预留：当前实现 simple 模式
}

function toRad(d: number): number { return d * Math.PI / 180; }
function haversineNm(a: LonLat, b: LonLat): number {
  const [lon1, lat1] = a; const [lon2, lat2] = b;
  const Rm = 6371000;
  const dLat = toRad(lat2 - lat1);
  const dLon = toRad(lon2 - lon1);
  const la1 = toRad(lat1); const la2 = toRad(lat2);
  const h = Math.sin(dLat/2)**2 + Math.cos(la1)*Math.cos(la2)*Math.sin(dLon/2)**2;
  const c = 2*Math.atan2(Math.sqrt(h), Math.sqrt(1-h));
  return (Rm * c) / 1852.0;
}

function polylineLengthNm(points: LonLat[]): number {
  if (!points || points.length < 2) return 0;
  let s = 0;
  for (let i=0;i<points.length-1;i++) s += haversineNm(points[i], points[i+1]);
  return s;
}

function nearestIndexOnPolyline(base: LonLat[], p: LonLat): number {
  let best = 0; let bestD = Infinity;
  for (let i=0;i<base.length;i++) {
    const d = haversineNm(base[i], p);
    if (d < bestD) { bestD = d; best = i; }
  }
  return best;
}

export const AdvancedAvoidanceEvaluationPanel: React.FC<Props> = ({ originalRoute, dynamicRoute, evalParams, mode='simple' }) => {
  const [params, setParams] = React.useState<EvalParams | null>(evalParams || null);
  const [error, setError] = React.useState<string | null>(null);
  const [advanced, setAdvanced] = React.useState<null | {
    delta_distance_nm: number;
    delta_time_hours: number;
    delta_fuel_ton: number;
    delta_cost_usd: number;
    delta_co2_ton: number;
    original_distance_nm: number;
    dynamic_distance_nm: number;
  }>(null);

  React.useEffect(() => {
    let mounted = true;
    if (!evalParams) {
      fetch('/api/eval/params')
        .then(r => r.ok ? r.json() : null)
        .then(data => { if (mounted && data) setParams(data as EvalParams); })
        .catch(() => {});
    }
    return () => { mounted = false; };
  }, [evalParams]);

  const metrics = React.useMemo(() => {
    if (!params) return null;
    if (!originalRoute || originalRoute.length < 2 || !dynamicRoute || dynamicRoute.length < 2) {
      setError('Insufficient path points for evaluation');
      return null;
    }
    setError(null);

    // 段级对齐
    const start = dynamicRoute[0];
    const end = dynamicRoute[dynamicRoute.length - 1];
    const iStart = nearestIndexOnPolyline(originalRoute, start);
    const iEnd = nearestIndexOnPolyline(originalRoute, end);
    const s = Math.min(iStart, iEnd);
    const e = Math.max(iStart, iEnd);

    let originalSeg: LonLat[] = [];
    for (let i=s;i<=e;i++) originalSeg.push(originalRoute[i]);
    const originalNm = polylineLengthNm(originalSeg);
    const dynamicNm = polylineLengthNm(dynamicRoute);

    // 简化模型（A）：线性海里油耗
    const v = params.vessel_speed_kn > 0 ? params.vessel_speed_kn : 1;
    const hoursOriginal = originalNm / v;
    const hoursDynamic = dynamicNm / v;
    const deltaHours = hoursDynamic - hoursOriginal;

    const fuelOriginalTon = originalNm * params.fuel_per_nm_ton;
    const fuelDynamicTon = dynamicNm * params.fuel_per_nm_ton;
    const deltaFuelTon = fuelDynamicTon - fuelOriginalTon;
    const deltaCostUSD = deltaFuelTon * params.fuel_price_usd_per_ton;
    const deltaCO2Ton = deltaFuelTon * params.co2_per_ton_fuel;

    return {
      s, e,
      segment: { startIndex: s, endIndex: e },
      originalNm, dynamicNm,
      deltaNm: dynamicNm - originalNm,
      hoursOriginal, hoursDynamic, deltaHours,
      fuelOriginalTon, fuelDynamicTon, deltaFuelTon,
      deltaCostUSD, deltaCO2Ton
    } as any;
  }, [originalRoute, dynamicRoute, params, mode]);

  // 调用后端 /api/eval/fuel（power模型），失败回退 simple 结果
  React.useEffect(() => {
    let mounted = true;
    async function run() {
      if (!params || !metrics) return;
      try {
        const m: any = metrics;
        const s: number = m.s, e: number = m.e;
        const originalSeg: LonLat[] = [];
        for (let i = s; i <= e; i++) originalSeg.push(originalRoute[i]);
        const toLatLon = (p: LonLat) => ({ lat: p[1], lon: p[0] });
        const payload = {
          original_route: originalSeg.map(toLatLon),
          dynamic_route: dynamicRoute.map(toLatLon),
          model: 'power',
          vessel_speed_kn: params.vessel_speed_kn,
          fuel_per_nm_ton: params.fuel_per_nm_ton,
          fuel_price_usd_per_ton: params.fuel_price_usd_per_ton,
          co2_per_ton_fuel: params.co2_per_ton_fuel,
        };
        const res = await fetch('/api/eval/fuel', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(payload) });
        if (!res.ok) throw new Error('eval failed');
        const data = await res.json();
        if (mounted && data && data.success) {
          setAdvanced({
            delta_distance_nm: data.delta_distance_nm,
            delta_time_hours: data.delta_time_hours,
            delta_fuel_ton: data.delta_fuel_ton,
            delta_cost_usd: data.delta_cost_usd,
            delta_co2_ton: data.delta_co2_ton,
            original_distance_nm: data.original_distance_nm,
            dynamic_distance_nm: data.dynamic_distance_nm,
          });
        }
      } catch (_) {
        if (mounted) setAdvanced(null);
      }
    }
    run();
    return () => { mounted = false; };
  }, [params, metrics, originalRoute, dynamicRoute]);

  if (!params || !metrics) return null;

  return (
    <div style={{
      background: 'rgba(46,52,64,0.95)',
      color: '#d8dee9',
      border: '1px solid #3b4252',
      borderRadius: 4,
      padding: 10,
      minWidth: 300
    }}>
      <div style={{ color: '#81a1c1', fontWeight: 600, marginBottom: 6 }}>
        ⚙️ Advanced Avoidance Impact Assessment (Segment-level)
      </div>
      {error && <div style={{ color: '#bf616a', fontSize: 12, marginBottom: 6 }}>{error}</div>}
      <div style={{ fontSize: 12, lineHeight: 1.5 }}>
        <div>Original Segment Distance: <span style={{ color: '#88c0d0' }}>{(advanced?.original_distance_nm ?? (metrics as any).originalNm).toFixed(2)} nm</span></div>
        <div>New Segment Distance: <span style={{ color: '#88c0d0' }}>{(advanced?.dynamic_distance_nm ?? (metrics as any).dynamicNm).toFixed(2)} nm</span></div>
        <div>ΔDistance: <span style={{ color: ((advanced?.delta_distance_nm ?? (metrics as any).deltaNm) as number) >= 0 ? '#d08770' : '#a3be8c' }}>{(advanced?.delta_distance_nm ?? (metrics as any).deltaNm).toFixed(2)} nm</span></div>
        <div style={{ marginTop: 6 }}>ΔTime: <span style={{ color: ((advanced?.delta_time_hours ?? (metrics as any).deltaHours) as number) >= 0 ? '#d08770' : '#a3be8c' }}>{(advanced?.delta_time_hours ?? (metrics as any).deltaHours).toFixed(2)} hours</span></div>
        <div>ΔFuel: <span style={{ color: ((advanced?.delta_fuel_ton ?? (metrics as any).deltaFuelTon) as number) >= 0 ? '#d08770' : '#a3be8c' }}>{(advanced?.delta_fuel_ton ?? (metrics as any).deltaFuelTon).toFixed(3)} tons</span></div>
        <div>ΔCost: <span style={{ color: '#a3be8c' }}>${(advanced?.delta_cost_usd ?? (metrics as any).deltaCostUSD).toFixed(0)}</span></div>
        <div>ΔCO₂: <span style={{ color: ((advanced?.delta_fuel_ton ?? (metrics as any).deltaFuelTon) as number) >= 0 ? '#bf616a' : '#a3be8c' }}>{(advanced?.delta_co2_ton ?? (metrics as any).deltaCO2Ton).toFixed(3)} tons</span></div>
        <div style={{ marginTop: 6, color: '#5e81ac' }}>Segment: [{(metrics as any).segment.startIndex} → {(metrics as any).segment.endIndex}]</div>
      </div>
    </div>
  );
};


