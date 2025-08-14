import React, { useEffect, useState, useRef } from "react";
import { CanvasMap, MapRef, LonLat } from "./components/CanvasMap";
import { getRoute, getEncLite, ValidationReportV1, exportRTZ, importRTZ } from "./api/client";
import { ColorScheme } from "./utils/ecdisColors";
import { useAISData } from "./hooks/useAISData";
import { EvaluationPanel } from "./components/EvaluationPanel";
import { AdvancedAvoidanceEvaluationPanel } from "./components/AdvancedAvoidanceEvaluationPanel";

export function App() {
  const mapRef = useRef<MapRef>(null);
  const lastUserViewChangeAt = useRef<number>(0);
  const autoFitDoneRef = useRef<boolean>(false);
  const [route, setRoute] = useState<LonLat[]>([]);
  const [enc, setEnc] = useState<any>(null);
  const [report, setReport] = useState<ValidationReportV1 | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [colorScheme, setColorScheme] = useState<ColorScheme>('DAY');
  const fileInputRef = useRef<HTMLInputElement>(null);
  const [aisEnabled, setAisEnabled] = useState(false);
  const [aisScenario, setAisScenario] = useState<'default' | 'aggressive'>('default');
  const [dynamicRouteEnabled, setDynamicRouteEnabled] = useState(false);
  const [mapState, setMapState] = useState({ center: [121.508, 31.23] as LonLat, zoom: 8 });
  const [dynamicRoute, setDynamicRoute] = useState<LonLat[]>([]);
  const [routeComparison, setRouteComparison] = useState<any>(null);
  const { targets, connected } = useAISData(aisEnabled);

  useEffect(() => {
    (async () => {
      try {
        setLoading(true);
        
        // 加载ENC-lite数据和示例路线
        const [encLite, planData] = await Promise.all([
          getEncLite(),
          getRoute()
        ]);
        
        setEnc(encLite);
        setRoute(planData.coords);
        setReport(planData.report);
        setError(null);
        
        // 自动定位到航迹
        setTimeout(() => {
          mapRef.current?.zoomToFit();
        }, 100);
      } catch (err) {
        console.error('Failed to load data:', err);
        setError(`加载失败: ${err instanceof Error ? err.message : 'Unknown error'}`);
        
        // 设置默认上海-新加坡航线
        setRoute([
          [121.508, 31.23],   // 上海港
          [122.0, 31.0],      // 出长江口
          [122.5, 30.5],      // 东海
          [123.0, 29.5],      // 继续南下
          [122.8, 28.0],      // 浙江东部海域
          [122.0, 26.5],      // 福建东部海域
          [121.0, 25.0],      // 台湾海峡北部
          [119.5, 23.5],      // 台湾海峡中部
          [118.0, 22.0],      // 台湾海峡南部
          [116.5, 20.5],      // 南海北部
          [114.5, 18.0],      // 南海中部
          [112.0, 15.0],      // 南海中南部
          [110.0, 12.0],      // 继续向南
          [108.0, 9.0],       // 接近马来半岛
          [106.0, 6.0],       // 马来半岛东岸
          [104.5, 3.5],       // 马六甲海峡北口
          [103.9, 2.0],       // 马六甲海峡
          [103.85, 1.27]      // 新加坡港
        ]);
        setEnc({
          coast: [
            [[[0.0, -0.01], [0.04, -0.01], [0.04, 0.025], [0.0, 0.025], [0.0, -0.01]]]
          ],
          shallow: [
            [[[0.005, 0.005], [0.015, 0.005], [0.015, 0.015], [0.005, 0.015], [0.005, 0.005]]]
          ],
          tss: { lanes: [], sep_zones: [] },
          s124: { speed_limits: [], prohibited: [] }
        });
        setReport({
          clause_refs: [
            { standard: "IMO MSC.232(82)", clause: "4.7.1", status: "COMPLIANT" },
            { standard: "COLREG Rule", clause: "10", status: "COMPLIANT" },
            { standard: "IHO S-57", clause: "SAFETY", status: "WARN" }
          ],
          min_ukc_m: 3.5,
          alerts: [
            { level: "B", msg: "Shallow water detected along route" }
          ]
        });
      } finally {
        setLoading(false);
      }
    })();
  }, []);

  // 动态路径管理
  useEffect(() => {
    if (!dynamicRouteEnabled) {
      setDynamicRoute([]);
      setRouteComparison(null);
      return;
    }

    // 检查路径是否有效
    if (!route || route.length === 0) {
      console.warn('警告: 没有基础路径，无法初始化动态路径规划');
      return;
    }

    console.log('启用动态路径规划，基础路径点数:', route.length);

    // 如果启用动态路径但AIS未启用，自动启用AIS
    if (!aisEnabled) {
      console.log('自动启用AIS以支持动态路径规划');
      setAisEnabled(true);
      return; // 等待下一次渲染后重新初始化
    }

    // 初始化动态路径（确保后端已就绪，且AIS已启用）
    const initializeDynamicRoute = async () => {
      try {
        // 简单健康检查，避免后台未启时卡在初始化
        const status = await fetch('/status').then(r => r.ok ? r.json() : null).catch(() => null);
        if (!status) {
          console.warn('后端未就绪，延迟动态路径初始化');
          setTimeout(initializeDynamicRoute, 2000);
          return;
        }
        const waypoints = route.map(([lon, lat]) => ({ lat, lon }));
        const response = await fetch('/api/route/initialize', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ waypoints })
        });

        if (response.ok) {
          const data = await response.json();
          console.log('动态路径已初始化:', data);
          
          // 获取动态路径数据
          fetchDynamicRoute();
        }
      } catch (error) {
        console.error('初始化动态路径失败:', error);
      }
    };

    initializeDynamicRoute();

    // 定期更新动态路径
    const updateInterval = setInterval(fetchDynamicRoute, 5000);
    return () => clearInterval(updateInterval);
  }, [dynamicRouteEnabled, route, aisEnabled]);

  // 获取动态路径数据
  const fetchDynamicRoute = async () => {
    try {
      console.log('正在获取动态路径，当前位置:', mapState.center);
      const response = await fetch(`/api/route/dynamic?current_lat=${mapState.center[1]}&current_lon=${mapState.center[0]}`);
      if (response.ok) {
        const data = await response.json();
        console.log('获取到动态路径数据:', data);
          if (data.route_comparison) {
          setRouteComparison(data.route_comparison);
          const dynamicWaypoints = data.route_comparison.dynamic_route || [];
          console.log('动态航路点:', dynamicWaypoints);
          // 后端现已返回 (lat, lon)；前端使用 [lon, lat]
          const convertedRoute = dynamicWaypoints.map(([lat, lon]: [number, number]) => [lon, lat] as LonLat);
          setDynamicRoute(convertedRoute);
            // 同步避让点到 CanvasMap 作为高亮标记
            const avoidance = (data.route_comparison.avoidance_points || []).map(([lat, lon]: [number, number]) => [lon, lat] as LonLat);
            // 为了传递到 CanvasMap，存入 enc 的临时字段或通过 props 传递
            setEnc((prev: any) => ({ ...(prev || {}), __avoidance_points: avoidance }));
          console.log('已设置动态路径，点数:', convertedRoute.length);

          // 视图自适应：仅首次动态路径就绪且用户最近未交互时触发
          try {
            const now = Date.now();
            const recentUserChange = now - lastUserViewChangeAt.current < 2000;
            if (!autoFitDoneRef.current && !recentUserChange && mapRef.current?.zoomTo) {
              const allPts = [...route, ...convertedRoute];
              if (allPts.length > 1) {
                let minLon = Infinity, maxLon = -Infinity;
                let minLat = Infinity, maxLat = -Infinity;
                for (const [lon, lat] of allPts) {
                  if (lon < minLon) minLon = lon;
                  if (lon > maxLon) maxLon = lon;
                  if (lat < minLat) minLat = lat;
                  if (lat > maxLat) maxLat = lat;
                }
                const lonMargin = (maxLon - minLon) * 0.1 || 0.05;
                const latMargin = (maxLat - minLat) * 0.1 || 0.05;
                mapRef.current.zoomTo([[minLon - lonMargin, minLat - latMargin], [maxLon + lonMargin, maxLat + latMargin]]);
                autoFitDoneRef.current = true;
              }
            }
          } catch (e) {
            console.warn('自动视图适配失败:', e);
          }
        }
      } else {
        console.error('获取动态路径失败，状态码:', response.status);
      }
    } catch (error) {
      console.error('获取动态路径失败:', error);
    }
  };

  // 切换AIS场景（default/aggressive），并在需要时重新初始化动态路径
  const handleScenarioChange = async (scenario: 'default' | 'aggressive') => {
    try {
      const res = await fetch('/api/ais/scenario', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ scenario })
      });
      if (!res.ok) throw new Error(`切换AIS场景失败: ${res.status}`);
      setAisScenario(scenario);

      // 若动态路径已启用，则重新初始化以立即体现差异
      if (dynamicRouteEnabled && route && route.length > 0) {
        const waypoints = route.map(([lon, lat]) => ({ lat, lon }));
        await fetch('/api/route/initialize', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ waypoints })
        });
        setTimeout(() => { fetchDynamicRoute(); }, 300);
      }
    } catch (e) {
      console.error(e);
    }
  };

  // 添加键盘快捷键支持
  useEffect(() => {
    const handleKeyPress = (e: KeyboardEvent) => {
      if (e.target instanceof HTMLInputElement || e.target instanceof HTMLTextAreaElement) {
        return; // 忽略输入框中的按键
      }
      
      switch(e.key.toLowerCase()) {
        case ' ':
          e.preventDefault();
          mapRef.current?.centerOnRoute();
          break;
        case 'f':
          e.preventDefault();
          mapRef.current?.zoomToFit();
          break;
      }
    };

    window.addEventListener('keydown', handleKeyPress);
    return () => window.removeEventListener('keydown', handleKeyPress);
  }, []);

  // RTZ导出处理
  const handleExportRTZ = async () => {
    try {
      const blob = await exportRTZ("current_route");
      const url = URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = `ECDIS_Route_${new Date().toISOString().slice(0,16).replace(/:/g,'-')}.rtz`;
      document.body.appendChild(a);
      a.click();
      document.body.removeChild(a);
      URL.revokeObjectURL(url);
    } catch (err) {
      console.error('RTZ导出失败:', err);
    }
  };

  // RTZ导入处理
  const handleImportRTZ = async (event: React.ChangeEvent<HTMLInputElement>) => {
    const file = event.target.files?.[0];
    if (!file) return;

    try {
      const result = await importRTZ(file);
      console.log('RTZ导入成功:', result);
      
      // 重新加载所有数据（路线和ENC数据）
      const [encLite, routeData] = await Promise.all([
        getEncLite(),
        getRoute()
      ]);
      
      setEnc(encLite);
      setRoute(routeData.coords);
      setReport(routeData.report);
      setError(null);
      

    } catch (err) {
      console.error('RTZ导入失败:', err);
      setError(`RTZ导入失败: ${err instanceof Error ? err.message : 'Unknown error'}`);
    }
  };

  if (loading) {
    return (
      <div style={{ 
        display: 'flex', 
        alignItems: 'center', 
        justifyContent: 'center', 
        height: '100vh',
        background: '#0b0f12',
        color: '#d8dee9'
      }}>
        <div>🚢 Loading ECDIS UI...</div>
      </div>
    );
  }

  return (
    <div style={{
      display: "grid", 
      gridTemplateColumns: "320px 1fr", 
      height: "100vh",
      background: "#0b0f12"
    }}>
      {/* 左侧面板 */}
      <aside style={{
        padding: "16px", 
        borderRight: "1px solid #3b4252", 
        background: "#0b0f12", 
        color: "#d8dee9",
        overflowY: "auto"
      }}>
        <h2 style={{ 
          marginBottom: "16px", 
          fontSize: "18px",
          color: "#88c0d0"
        }}>
          🗺️ ECDIS 图层
        </h2>
        
        {/* ECDIS颜色方案 */}
        <div style={{ marginBottom: "24px" }}>
          <h3 style={{ fontSize: "14px", marginBottom: "8px", color: "#81a1c1" }}>ECDIS显示模式</h3>
          <select
            value={colorScheme}
            onChange={(e) => {
              const scheme = e.target.value as ColorScheme;
              setColorScheme(scheme);
              mapRef.current?.setColorScheme(scheme);
            }}
            style={{
              width: "100%",
              padding: "8px",
              borderRadius: "4px",
              background: "#2e3440",
              color: "#d8dee9",
              border: "1px solid #4c566a",
              fontSize: "14px"
            }}
          >
            <option value="DAY">☀️ 日间模式</option>
            <option value="DUSK">🌅 黄昏模式</option>
            <option value="NIGHT">🌙 夜间模式</option>
          </select>
          <div style={{ 
            marginTop: "8px", 
            fontSize: "12px", 
            color: "#5e81ac" 
          }}>
            {colorScheme === 'NIGHT' && "红色系保护夜视能力"}
            {colorScheme === 'DUSK' && "低对比度减少眩光"}
            {colorScheme === 'DAY' && "高对比度日光可读"}
          </div>
        </div>
        
        {/* 图层控制 */}
        <div style={{ marginBottom: "24px" }}>
          <h3 style={{ fontSize: "14px", marginBottom: "8px", color: "#81a1c1" }}>基础图层</h3>
          <ul style={{ listStyle: "none" }}>
            <li style={{ margin: "4px 0" }}>
              <label style={{ display: "flex", alignItems: "center", cursor: "pointer" }}>
                <input 
                  type="checkbox" 
                  defaultChecked
                  onChange={e => mapRef.current?.toggle("geography", e.target.checked)}
                  style={{ marginRight: "8px" }}
                /> 
                🌍 真实地理环境（亚太地区海岸线）
              </label>
            </li>
            <li style={{ margin: "4px 0" }}>
              <label style={{ display: "flex", alignItems: "center", cursor: "pointer" }}>
                <input 
                  type="checkbox" 
                  defaultChecked
                  onChange={e => mapRef.current?.toggle("bathymetry", e.target.checked)}
                  style={{ marginRight: "8px" }}
                /> 
                📊 水深等深线（5m-200m）
              </label>
            </li>
            <li style={{ margin: "4px 0" }}>
              <label style={{ display: "flex", alignItems: "center", cursor: "pointer" }}>
                <input 
                  type="checkbox" 
                  defaultChecked
                  onChange={e => mapRef.current?.toggle("seamark", e.target.checked)}
                  style={{ marginRight: "8px" }}
                /> 
                🔦 助航标志（灯塔、浮标、危险物）
              </label>
            </li>
            <li style={{ margin: "4px 0" }}>
              <label style={{ display: "flex", alignItems: "center", cursor: "pointer" }}>
                <input 
                  type="checkbox" 
                  onChange={e => mapRef.current?.toggle("localbase", e.target.checked)}
                  style={{ marginRight: "8px" }}
                /> 
                本地离线底图（程序纹理+经纬网）
              </label>
            </li>
            <li style={{ margin: "4px 0" }}>
              <label style={{ display: "flex", alignItems: "center", cursor: "pointer" }}>
                <input 
                  type="checkbox" 
                  onChange={e => mapRef.current?.toggle("basemap", e.target.checked)}
                  style={{ marginRight: "8px" }}
                /> 
                增强海图底图（深海渲染+等深线）
              </label>
            </li>
            <li style={{ margin: "4px 0" }}>
              <label style={{ display: "flex", alignItems: "center", cursor: "pointer" }}>
                <input 
                  type="checkbox" 
                  onChange={e => mapRef.current?.toggle("seamarks", e.target.checked)}
                  style={{ marginRight: "8px" }}
                /> 
                航标系统（浮标+灯塔+信标）
              </label>
            </li>
            <li style={{ margin: "4px 0" }}>
              <label style={{ display: "flex", alignItems: "center", cursor: "pointer" }}>
                <input 
                  type="checkbox" 
                  defaultChecked 
                  onChange={e => mapRef.current?.toggle("enc", e.target.checked)}
                  style={{ marginRight: "8px" }}
                /> 
                ENC 海岸线
              </label>
            </li>
            <li style={{ margin: "4px 0" }}>
              <label style={{ display: "flex", alignItems: "center", cursor: "pointer" }}>
                <input 
                  type="checkbox" 
                  defaultChecked 
                  onChange={e => mapRef.current?.toggle("route", e.target.checked)}
                  style={{ marginRight: "8px" }}
                /> 
                规划航线
              </label>
            </li>
            <li style={{ margin: "4px 0" }}>
              <label style={{ display: "flex", alignItems: "center", cursor: "pointer" }}>
                <input 
                  type="checkbox" 
                  defaultChecked 
                  onChange={e => mapRef.current?.toggle("tss", e.target.checked)}
                  style={{ marginRight: "8px" }}
                /> 
                TSS 分道通航
              </label>
            </li>
            <li style={{ margin: "4px 0" }}>
              <label style={{ display: "flex", alignItems: "center", cursor: "pointer" }}>
                <input 
                  type="checkbox" 
                  defaultChecked 
                  onChange={e => mapRef.current?.toggle("s124", e.target.checked)}
                  style={{ marginRight: "8px" }}
                /> 
                S-124 警告
              </label>
            </li>
          </ul>
        </div>

        {/* AIS控制 */}
        <div style={{ marginBottom: "24px" }}>
          <h3 style={{ fontSize: "14px", marginBottom: "8px", color: "#81a1c1" }}>AIS系统</h3>
          <label style={{ display: "flex", alignItems: "center", cursor: "pointer" }}>
            <input 
              type="checkbox" 
              checked={aisEnabled}
              onChange={e => setAisEnabled(e.target.checked)}
              style={{ marginRight: "8px" }}
            /> 
            🚢 启用AIS显示
          </label>
          {aisEnabled && (
            <div style={{ marginTop: "8px", fontSize: "12px", color: "#5e81ac" }}>
              {connected ? `✅ 已连接 - ${targets.length}个目标` : '⏳ 连接中...'}
            </div>
          )}

          {/* AIS场景切换 */}
          <div style={{ marginTop: "8px" }}>
            <label style={{ display: 'block', fontSize: '12px', color: '#81a1c1', marginBottom: '4px' }}>攻击场景</label>
            <select
              value={aisScenario}
              onChange={(e) => handleScenarioChange(e.target.value as 'default' | 'aggressive')}
              style={{
                width: '100%',
                padding: '6px',
                borderRadius: '4px',
                background: '#2e3440',
                color: '#d8dee9',
                border: '1px solid #4c566a',
                fontSize: '12px'
              }}
            >
              <option value="default">默认（常规环境）</option>
              <option value="aggressive">强攻击（高风险屏障）</option>
            </select>
          </div>
        </div>

        {/* 动态避让控制 */}
        <div style={{ marginBottom: "24px" }}>
          <h3 style={{ fontSize: "14px", marginBottom: "8px", color: "#81a1c1" }}>动态避让</h3>
          <label style={{ display: "flex", alignItems: "center", cursor: "pointer" }}>
            <input 
              type="checkbox" 
              checked={dynamicRouteEnabled}
              onChange={e => setDynamicRouteEnabled(e.target.checked)}
              style={{ marginRight: "8px" }}
              disabled={false}
            /> 
            🧭 启用动态路径规划
          </label>
          {dynamicRouteEnabled && (
            <div style={{ marginTop: "8px", fontSize: "12px" }}>
              {routeComparison ? (
                <div>
                  <div style={{ color: "#a3be8c" }}>
                    ✅ 路径规划活跃 - {routeComparison.active_threats?.length || 0}个威胁
                  </div>
                  <div style={{ color: "#88c0d0", marginTop: "4px" }}>
                    🔵 原路径({routeComparison.original_route?.length || 0}点) / 🟢 动态路径({routeComparison.dynamic_route?.length || 0}点)
                  </div>
                  {routeComparison.avoidance_points?.length > 0 && (
                    <div style={{ color: "#d08770", marginTop: "4px" }}>
                      🔄 生成了 {routeComparison.avoidance_points.length} 个避让点
                    </div>
                  )}
                  {routeComparison.active_threats?.length > 0 && (
                    <div style={{ color: "#ebcb8b", marginTop: "4px" }}>
                      ⚠️ 威胁: {routeComparison.active_threats.join(', ')}
                    </div>
                  )}
                </div>
              ) : route.length === 0 ? (
                <div style={{ color: "#bf616a" }}>❌ 需要先设置基础路径</div>
              ) : !aisEnabled ? (
                <div style={{ color: "#ebcb8b" }}>⏳ 正在启用AIS...</div>
              ) : (
                <div style={{ color: "#5e81ac" }}>⏳ 正在初始化动态路径...</div>
              )}
            </div>
          )}
        </div>

        {/* 校核报告 */}
        <div style={{ marginBottom: "24px" }}>
          <h3 style={{ fontSize: "14px", marginBottom: "8px", color: "#81a1c1" }}>合规校核</h3>
          <div style={{ 
            fontSize: "12px", 
            lineHeight: 1.4,
            background: "#2e3440",
            padding: "12px",
            borderRadius: "4px",
            border: "1px solid #3b4252"
          }}>
            {error && (
              <div style={{ color: "#bf616a", marginBottom: "8px" }}>
                ⚠️ {error}
              </div>
            )}
            {report?.clause_refs ? (
              <div>
                <div style={{ marginBottom: "8px", fontWeight: "bold" }}>标准条款:</div>
                {report.clause_refs.slice(0, 5).map((clause: any, i: number) => (
                  <div key={i} style={{ 
                    margin: "4px 0",
                    display: "flex",
                    justifyContent: "space-between"
                  }}>
                    <span>{clause.standard} {clause.clause}</span>
                    <span style={{ 
                      color: clause.status === "COMPLIANT" ? "#a3be8c" : 
                            clause.status === "WARN" ? "#ebcb8b" : "#bf616a"
                    }}>
                      {clause.status}
                    </span>
                  </div>
                ))}
                {report.min_ukc_m && (
                  <div style={{ marginTop: "8px" }}>
                    最小UKC: <span style={{ color: "#88c0d0" }}>{report.min_ukc_m}m</span>
                  </div>
                )}
              </div>
            ) : (
              "加载中..."
            )}
          </div>
        </div>

        {/* RTZ路线管理 */}
        <div style={{ marginBottom: "24px" }}>
          <h3 style={{ fontSize: "14px", marginBottom: "8px", color: "#81a1c1" }}>RTZ路线管理</h3>
          <div style={{ display: "flex", flexDirection: "column", gap: "8px" }}>
            <button
              onClick={handleExportRTZ}
              style={{
                padding: "6px 12px",
                background: "#5e81ac",
                color: "white",
                border: "none",
                borderRadius: "4px",
                cursor: "pointer",
                fontSize: "12px"
              }}
            >
              📥 导出RTZ
            </button>
            <div>
              <input
                ref={fileInputRef}
                type="file"
                accept=".rtz,.xml"
                onChange={handleImportRTZ}
                style={{ display: "none" }}
              />
              <button
                onClick={() => fileInputRef.current?.click()}
                style={{
                  padding: "6px 12px",
                  background: "#a3be8c",
                  color: "white",
                  border: "none",
                  borderRadius: "4px",
                  cursor: "pointer",
                  fontSize: "12px",
                  width: "100%"
                }}
              >
                📤 导入RTZ
              </button>
            </div>
          </div>
        </div>

        {/* 告警面板 */}
        {report?.alerts && report.alerts.length > 0 && (
          <div>
            <h3 style={{ fontSize: "14px", marginBottom: "8px", color: "#81a1c1" }}>系统告警</h3>
            <div style={{
              background: "#2e3440",
              padding: "12px",
              borderRadius: "4px",
              border: "1px solid #3b4252"
            }}>
              {report.alerts.map((alert: any, i: number) => (
                <div key={i} style={{
                  margin: "4px 0",
                  fontSize: "12px",
                  color: alert.level === "A" ? "#bf616a" : 
                        alert.level === "B" ? "#ebcb8b" : "#81a1c1"
                }}>
                  [{alert.level}] {alert.msg}
                </div>
              ))}
            </div>
          </div>
        )}
      </aside>

      {/* 地图主区域 */}
      <main style={{ position: "relative" }}>
        <CanvasMap
          ref={mapRef}
          enc={enc}
          route={route}
          dynamicRoute={dynamicRoute}
          dynamicRouteEnabled={dynamicRouteEnabled}
          aisTargets={targets}
          aisEnabled={aisEnabled}
          avoidancePoints={enc?.__avoidance_points}
          style={{ width: "100%", height: "100%", display: "block" }}
          onViewChange={(center, zoom) => {
            setMapState({ center, zoom });
            lastUserViewChangeAt.current = Date.now();
          }}
        />

        
          {/* 地图控制按钮 */}
        <div style={{
          position: "absolute",
          top: "16px",
          right: "16px",
          display: "flex",
          flexDirection: "column",
          gap: "8px"
        }}>
            {/* 右上角评估面板（有对比数据时显示） */}
            {routeComparison && (
              <div style={{ alignSelf: "flex-end" }}>
                <EvaluationPanel 
                  routeComparison={routeComparison}
                  originalRouteLonLat={route}
                  dynamicRouteLonLat={dynamicRoute}
                />
              </div>
            )}
            {/* 可选启用的高级评估面板（段级对齐 + 真实参数），默认展示在评估卡下方 */}
            {routeComparison && (
              <div style={{ alignSelf: "flex-end" }}>
                <div style={{ height: 8 }} />
                <AdvancedAvoidanceEvaluationPanel 
                  originalRoute={route}
                  dynamicRoute={dynamicRoute}
                />
              </div>
            )}
          {/* 航迹定位控制 */}
          <div style={{
            background: "rgba(46, 52, 64, 0.95)",
            padding: "8px",
            borderRadius: "4px",
            border: "1px solid #3b4252",
            display: "flex",
            gap: "8px"
          }}>
            <button
              onClick={() => mapRef.current?.centerOnRoute()}
              style={{
                padding: "4px 8px",
                background: "#5e81ac",
                color: "white",
                border: "none",
                borderRadius: "3px",
                cursor: "pointer",
                fontSize: "12px",
                display: "flex",
                alignItems: "center",
                gap: "4px"
              }}
              title="定位到航迹中心"
            >
              🎯 航迹中心
            </button>
            <button
              onClick={() => mapRef.current?.zoomToFit()}
              style={{
                padding: "4px 8px",
                background: "#81a1c1",
                color: "white",
                border: "none",
                borderRadius: "3px",
                cursor: "pointer",
                fontSize: "12px",
                display: "flex",
                alignItems: "center",
                gap: "4px"
              }}
              title="自动缩放以显示完整航迹"
            >
              🔍 适应视图
            </button>
          </div>
          
          {/* 操作提示 */}
          <div style={{
            background: "rgba(46, 52, 64, 0.9)",
            padding: "8px",
            borderRadius: "4px",
            border: "1px solid #3b4252"
          }}>
            <div style={{ fontSize: "11px", color: "#81a1c1", lineHeight: "1.4" }}>
              📍 鼠标拖拽平移 | 滚轮缩放<br/>
              ⌨️ 空格键：航迹中心 | F键：适应视图
            </div>
          </div>
        </div>
      </main>
    </div>
  );
}