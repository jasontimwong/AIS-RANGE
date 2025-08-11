import React, { useEffect, useState, useRef } from "react";
import { CanvasMap, MapRef, LonLat } from "./components/CanvasMap";
import { getRoute, getEncLite, ValidationReportV1, exportRTZ, importRTZ } from "./api/client";

export function App() {
  const mapRef = useRef<MapRef>(null);
  const [route, setRoute] = useState<LonLat[]>([]);
  const [enc, setEnc] = useState<any>(null);
  const [report, setReport] = useState<ValidationReportV1 | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);

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
      } catch (err) {
        console.error('Failed to load data:', err);
        setError(`加载失败: ${err instanceof Error ? err.message : 'Unknown error'}`);
        
        // 设置默认示例数据
        setRoute([
          [0.0, 0.0],
          [0.01, 0.005], 
          [0.02, 0.01],
          [0.03, 0.015]
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
        
        {/* 图层控制 */}
        <div style={{ marginBottom: "24px" }}>
          <h3 style={{ fontSize: "14px", marginBottom: "8px", color: "#81a1c1" }}>基础图层</h3>
          <ul style={{ listStyle: "none" }}>
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
          style={{ width: "100%", height: "100%", display: "block" }}
        />
        
        {/* 地图控制按钮 */}
        <div style={{
          position: "absolute",
          top: "16px",
          right: "16px",
          background: "rgba(46, 52, 64, 0.9)",
          padding: "8px",
          borderRadius: "4px",
          border: "1px solid #3b4252"
        }}>
          <div style={{ fontSize: "12px", color: "#81a1c1" }}>
            📍 鼠标拖拽平移 | 滚轮缩放
          </div>
        </div>
      </main>
    </div>
  );
}