import React, { useEffect, useState, useRef } from "react";
import { CanvasMap, MapRef, LonLat } from "./components/CanvasMap";
import { getEncLite, ValidationReportV1, exportRTZ, importRTZ } from "./api/client";
import { planFullRoute } from "./api/client";
import { routeService } from "./services/routeService";
import { ColorScheme } from "./utils/ecdisColors";
import { useAISData } from "./hooks/useAISData";
import { EvaluationPanel } from "./components/EvaluationPanel";
import { AdvancedAvoidanceEvaluationPanel } from "./components/AdvancedAvoidanceEvaluationPanel";
import { RoutePlanner } from "./components/RoutePlanner";

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
  const [shipPosition, setShipPosition] = useState<LonLat>([121.508, 31.23]); // Actual ship position
  const [dynamicRoute, setDynamicRoute] = useState<LonLat[]>([]);
  const [routeComparison, setRouteComparison] = useState<any>(null);
  // Manual replan result temporary override window (prevent being overridden by 5-second polling)
  const manualOverrideUntilRef = useRef<number>(0);
  
  const { targets, connected } = useAISData(aisEnabled);

  // Subscribe to RouteService path updates
  useEffect(() => {
    const unsubscribe = routeService.subscribe((newRoute) => {
      console.log('RouteService path update:', newRoute.length, 'points');
      // Only update when path actually changes
      const updated = setRoute(prevRoute => {
        // Avoid unnecessary updates
        if (prevRoute.length === newRoute.length && 
            prevRoute.length > 0 && 
            prevRoute[0][0] === newRoute[0][0] && 
            prevRoute[0][1] === newRoute[0][1]) {
          return prevRoute;
        }
        return newRoute;
      });
      // Auto-fit view after path update (avoid interrupting user manual interaction)
      try {
        const now = Date.now();
        const recentUserChange = now - lastUserViewChangeAt.current < 1500;
        if (!recentUserChange && newRoute && newRoute.length > 1) {
          setTimeout(() => mapRef.current?.zoomToFit(), 50);
        }
      } catch {}
    });

    return () => {
      unsubscribe();
    };
  }, []);

  // Initial loading
  useEffect(() => {
    (async () => {
      try {
        setLoading(true);
        
        // Load ENC data
        const encLite = await getEncLite();
        setEnc(encLite);
        
         // Load saved route or default route from RouteService
        const savedRoute = routeService.getCurrentRoute();
        if (savedRoute && savedRoute.length > 0) {
          console.log('Loading saved route:', savedRoute.length, 'points');
          setRoute(savedRoute);
          // Set initial ship position to route start
          if (savedRoute.length > 0) {
            setShipPosition(savedRoute[0]);
          }
        } else {
          // If no saved route, set default route (Shanghai-Singapore)
          const defaultRoute: LonLat[] = [
            [121.508, 31.23],   // Shanghai Port
            [122.0, 31.0],      // Yangtze River Estuary
            [122.5, 30.5],      // East China Sea
            [123.0, 29.5],      // Continue South
            [122.8, 28.0],      // East of Zhejiang
            [122.0, 26.5],      // East of Fujian
            [121.0, 25.0],      // North Taiwan Strait
            [119.5, 23.5],      // Central Taiwan Strait
            [118.0, 22.0],      // South Taiwan Strait
            [116.5, 20.5],      // North South China Sea
            [114.5, 18.0],      // Central South China Sea
            [112.0, 15.0],      // South-Central South China Sea
            [110.0, 12.0],      // Continue South
            [108.0, 9.0],       // Approaching Malay Peninsula
            [106.0, 6.0],       // East Coast of Malay Peninsula
            [104.5, 3.5],       // North Entrance of Malacca Strait
            [103.9, 2.0],       // Malacca Strait
            [103.85, 1.27]      // Singapore Port
          ];
           routeService.setDefaultRoute(defaultRoute);
           // Auto-fit view after initial setup
           setTimeout(() => mapRef.current?.zoomToFit(), 80);
        }
        
        setError(null);
        
        // Auto-locate to track
        setTimeout(() => {
          mapRef.current?.zoomToFit();
        }, 100);
      } catch (err) {
        console.error('Failed to load data:', err);
        setError(`Loading failed: ${err instanceof Error ? err.message : 'Unknown error'}`);
        
        // Set default Shanghai-Singapore route
        const defaultRouteData: LonLat[] = [
          [121.508, 31.23],   // Shanghai Port
          [122.0, 31.0],      // Yangtze River Estuary
          [122.5, 30.5],      // East China Sea
          [123.0, 29.5],      // Continue South
          [122.8, 28.0],      // East of Zhejiang
          [122.0, 26.5],      // East of Fujian
          [121.0, 25.0],      // North Taiwan Strait
          [119.5, 23.5],      // Central Taiwan Strait
          [118.0, 22.0],      // South Taiwan Strait
          [116.5, 20.5],      // North South China Sea
          [114.5, 18.0],      // Central South China Sea
          [112.0, 15.0],      // South-Central South China Sea
          [110.0, 12.0],      // Continue South
          [108.0, 9.0],       // Approaching Malay Peninsula
          [106.0, 6.0],       // East Coast of Malay Peninsula
          [104.5, 3.5],       // North Entrance of Malacca Strait
          [103.9, 2.0],       // Malacca Strait
          [103.85, 1.27]      // Singapore Port
        ];
        setRoute(defaultRouteData);
        setShipPosition(defaultRouteData[0] as LonLat);
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

  // Dynamic route management
  useEffect(() => {
    if (!dynamicRouteEnabled) {
      setDynamicRoute([]);
      setRouteComparison(null);
      return;
    }

    // Check if route is valid
    if (!route || route.length === 0) {
      console.warn('Warning: No base route, cannot initialize dynamic route planning');
      return;
    }

    console.log('Enabling dynamic route planning, base route points:', route.length);

    // If dynamic route enabled but AIS not enabled, auto-enable AIS
    if (!aisEnabled) {
      console.log('Auto-enabling AIS to support dynamic route planning');
      setAisEnabled(true);
      return; // Wait for next render to reinitialize
    }

    // Initialize dynamic route (ensure backend is ready and AIS is enabled)
    const initializeDynamicRoute = async () => {
      try {
        // Simple health check to avoid getting stuck when backend is not ready
        const status = await fetch('/status').then(r => r.ok ? r.json() : null).catch(() => null);
        if (!status) {
          console.warn('Backend not ready, delaying dynamic route initialization');
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
          console.log('Dynamic route initialized:', data);
          
          // Get dynamic route data
          fetchDynamicRoute();
        }
      } catch (error) {
        console.error('Failed to initialize dynamic route:', error);
      }
    };

    initializeDynamicRoute();

    // Periodically update dynamic route
    const updateInterval = setInterval(fetchDynamicRoute, 5000);
    return () => clearInterval(updateInterval);
  }, [dynamicRouteEnabled, route, aisEnabled, shipPosition]);  // Add shipPosition dependency

  // Fetch dynamic route data
  const fetchDynamicRoute = async () => {
    try {
      // Skip auto-polling update if within manual override window to avoid overriding "Replan (Global)" results
      if (Date.now() < manualOverrideUntilRef.current) {
        return;
      }
      // Use actual ship position instead of map center
      console.log('Fetching dynamic route, ship position:', shipPosition);
      const response = await fetch(`/api/route/dynamic?current_lat=${shipPosition[1]}&current_lon=${shipPosition[0]}`);
      if (response.ok) {
        const data = await response.json();
        console.log('Retrieved dynamic route data:', data);
          if (data.route_comparison) {
          setRouteComparison(data.route_comparison);
          const dynamicWaypoints = data.route_comparison.dynamic_route || [];
          console.log('Dynamic waypoints:', dynamicWaypoints);
          // Backend now returns (lat, lon); frontend uses [lon, lat]
          const convertedRoute = dynamicWaypoints.map(([lat, lon]: [number, number]) => [lon, lat] as LonLat);
          setDynamicRoute(convertedRoute);
            // Sync avoidance points to CanvasMap as highlight markers
            const avoidance = (data.route_comparison.avoidance_points || []).map(([lat, lon]: [number, number]) => [lon, lat] as LonLat);
            // To pass to CanvasMap, store in enc's temporary field or pass via props
            setEnc((prev: any) => ({ ...(prev || {}), __avoidance_points: avoidance }));
          console.log('Dynamic route set, points:', convertedRoute.length);

          // View auto-fit: Only trigger on first dynamic route ready and no recent user interaction
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
            console.warn('Auto view fit failed:', e);
          }
        }
      } else {
        console.error('Failed to fetch dynamic route, status code:', response.status);
      }
    } catch (error) {
      console.error('Failed to fetch dynamic route:', error);
    }
  };

  // Switch AIS scenario (default/aggressive), and reinitialize dynamic route if needed
  const handleScenarioChange = async (scenario: 'default' | 'aggressive') => {
    try {
      const res = await fetch('/api/ais/scenario', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ scenario })
      });
      if (!res.ok) throw new Error(`Failed to switch AIS scenario: ${res.status}`);
      setAisScenario(scenario);

      // If dynamic route is enabled, reinitialize to immediately reflect differences
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

  // Add keyboard shortcut support
  useEffect(() => {
    const handleKeyPress = (e: KeyboardEvent) => {
      if (e.target instanceof HTMLInputElement || e.target instanceof HTMLTextAreaElement) {
        return; // Ignore key presses in input fields
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

  // RTZ export handler
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
      console.error('RTZ export failed:', err);
    }
  };

  // RTZ import handler
  const handleImportRTZ = async (event: React.ChangeEvent<HTMLInputElement>) => {
    const file = event.target.files?.[0];
    if (!file) return;

    try {
      const result = await importRTZ(file);
      console.log('RTZ import successful:', result);
      
      // Reload ENC data and get imported route from service
      const encLite = await getEncLite();
      setEnc(encLite);
      
      // RTZ import creates new route, get from RouteService
      const importedRoute = routeService.getCurrentRoute();
      if (importedRoute) {
        setRoute(importedRoute);
        // Set ship position to imported route start
        if (importedRoute.length > 0) {
          setShipPosition(importedRoute[0]);
        }
        setReport(null); // Temporarily clear report after RTZ import
      }
      setError(null);
      

    } catch (err) {
      console.error('RTZ import failed:', err);
      setError(`RTZ import failed: ${err instanceof Error ? err.message : 'Unknown error'}`);
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
      {/* Left Panel */}
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
          🗺️ ECDIS Layers
        </h2>
        
        {/* ECDIS Color Scheme */}
        <div style={{ marginBottom: "24px" }}>
          <h3 style={{ fontSize: "14px", marginBottom: "8px", color: "#81a1c1" }}>ECDIS Display Mode</h3>
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
            <option value="DAY">☀️ Day Mode</option>
            <option value="DUSK">🌅 Dusk Mode</option>
            <option value="NIGHT">🌙 Night Mode</option>
          </select>
          <div style={{ 
            marginTop: "8px", 
            fontSize: "12px", 
            color: "#5e81ac" 
          }}>
            {colorScheme === 'NIGHT' && "Red tones preserve night vision"}
            {colorScheme === 'DUSK' && "Low contrast reduces glare"}
            {colorScheme === 'DAY' && "High contrast for daylight readability"}
          </div>
        </div>
        
        {/* Layer Controls */}
        <div style={{ marginBottom: "24px" }}>
          <h3 style={{ fontSize: "14px", marginBottom: "8px", color: "#81a1c1" }}>Base Layers</h3>
          <ul style={{ listStyle: "none" }}>
            <li style={{ margin: "4px 0" }}>
              <label style={{ display: "flex", alignItems: "center", cursor: "pointer" }}>
                <input 
                  type="checkbox" 
                  defaultChecked
                  onChange={e => mapRef.current?.toggle("geography", e.target.checked)}
                  style={{ marginRight: "8px" }}
                /> 
                🌍 Real Geography (Asia-Pacific Coastline)
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
                📊 Bathymetry Contours (5m-200m)
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
                🔦 Navigation Aids (Lighthouses, Buoys, Hazards)
              </label>
            </li>
            <li style={{ margin: "4px 0" }}>
              <label style={{ display: "flex", alignItems: "center", cursor: "pointer" }}>
                <input 
                  type="checkbox" 
                  onChange={e => mapRef.current?.toggle("localbase", e.target.checked)}
                  style={{ marginRight: "8px" }}
                /> 
                Local Offline Basemap (Procedural Texture + Grid)
              </label>
            </li>
            <li style={{ margin: "4px 0" }}>
              <label style={{ display: "flex", alignItems: "center", cursor: "pointer" }}>
                <input 
                  type="checkbox" 
                  onChange={e => mapRef.current?.toggle("basemap", e.target.checked)}
                  style={{ marginRight: "8px" }}
                /> 
                Enhanced Chart Basemap (Deep Sea + Contours)
              </label>
            </li>
            <li style={{ margin: "4px 0" }}>
              <label style={{ display: "flex", alignItems: "center", cursor: "pointer" }}>
                <input 
                  type="checkbox" 
                  onChange={e => mapRef.current?.toggle("seamarks", e.target.checked)}
                  style={{ marginRight: "8px" }}
                /> 
                Navigation System (Buoys + Lighthouses + Beacons)
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
                ENC Coastline
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
                Planned Route
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
                TSS Traffic Separation
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
                S-124 Warnings
              </label>
            </li>
          </ul>
        </div>

        {/* AIS Controls */}
        <div style={{ marginBottom: "24px" }}>
          <h3 style={{ fontSize: "14px", marginBottom: "8px", color: "#81a1c1" }}>AIS System</h3>
          <label style={{ display: "flex", alignItems: "center", cursor: "pointer" }}>
            <input 
              type="checkbox" 
              checked={aisEnabled}
              onChange={e => setAisEnabled(e.target.checked)}
              style={{ marginRight: "8px" }}
            /> 
            🚢 Enable AIS Display
          </label>
          {aisEnabled && (
            <div style={{ marginTop: "8px", fontSize: "12px", color: "#5e81ac" }}>
              {connected ? `✅ Connected - ${targets.length} targets` : '⏳ Connecting...'}
            </div>
          )}

          {/* AIS Scenario Switch */}
          <div style={{ marginTop: "8px" }}>
            <label style={{ display: 'block', fontSize: '12px', color: '#81a1c1', marginBottom: '4px' }}>Attack Scenario</label>
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
              <option value="default">Default (Normal Environment)</option>
              <option value="aggressive">Aggressive (High-Risk Barrier)</option>
            </select>
          </div>
        </div>

        {/* Route Planner */}
        <div style={{ marginBottom: "24px" }}>
          <RoutePlanner
            onRouteSelect={(newRoute) => {
              console.log('User planned new route:', newRoute.length, 'points');
              // Save user-planned route using RouteService (will trigger subscription update)
              routeService.setPlannedRoute(newRoute);
              // Set ship position to new route start
              if (newRoute.length > 0) {
                setShipPosition(newRoute[0]);
              }
              setDynamicRoute([]);  // Clear dynamic route
              setDynamicRouteEnabled(false);  // Disable dynamic planning first
              
              // Delay enabling dynamic planning to let route display first
              setTimeout(() => {
                setDynamicRouteEnabled(true);
                mapRef.current?.zoomToFit();
              }, 500);
            }}
            onPlanningStart={() => {
              console.log('Starting route planning...');
            }}
            onPlanningComplete={(route, time) => {
              console.log(`Route planning complete, ${route.length} points, took ${time}s`);
              setError(null);
            }}
            onPlanningError={(err) => {
              setError(`Route planning failed: ${err}`);
            }}
          />
        </div>

        {/* Dynamic Avoidance Control */}
        <div style={{ marginBottom: "24px" }}>
          <h3 style={{ fontSize: "14px", marginBottom: "8px", color: "#81a1c1" }}>Dynamic Avoidance</h3>
          <label style={{ display: "flex", alignItems: "center", cursor: "pointer" }}>
            <input 
              type="checkbox" 
              checked={dynamicRouteEnabled}
              onChange={e => setDynamicRouteEnabled(e.target.checked)}
              style={{ marginRight: "8px" }}
              disabled={false}
            /> 
            🧭 Enable Dynamic Route Planning
          </label>
          {dynamicRouteEnabled && (
            <div style={{ marginTop: "8px", fontSize: "12px" }}>
              {routeComparison ? (
                <div>
                  <div style={{ color: "#a3be8c" }}>
                    ✅ Route planning active - {routeComparison.active_threats?.length || 0} threats
                  </div>
                  <div style={{ color: "#88c0d0", marginTop: "4px" }}>
                    🔵 Original({routeComparison.original_route?.length || 0} pts) / 🟢 Dynamic({routeComparison.dynamic_route?.length || 0} pts)
                  </div>
                  {routeComparison.avoidance_points?.length > 0 && (
                    <div style={{ color: "#d08770", marginTop: "4px" }}>
                      🔄 Generated {routeComparison.avoidance_points.length} avoidance points
                    </div>
                  )}
                  {routeComparison.active_threats?.length > 0 && (
                    <div style={{ color: "#ebcb8b", marginTop: "4px" }}>
                      ⚠️ Threats: {routeComparison.active_threats.join(', ')}
                    </div>
                  )}
                </div>
              ) : route.length === 0 ? (
                <div style={{ color: "#bf616a" }}>❌ Base route required first</div>
              ) : !aisEnabled ? (
                <div style={{ color: "#ebcb8b" }}>⏳ Enabling AIS...</div>
              ) : (
                <div style={{ color: "#5e81ac" }}>⏳ Initializing dynamic route...</div>
              )}
            </div>
          )}
        </div>

        {/* Compliance Check */}
        <div style={{ marginBottom: "24px" }}>
          <h3 style={{ fontSize: "14px", marginBottom: "8px", color: "#81a1c1" }}>Compliance Check</h3>
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
                <div style={{ marginBottom: "8px", fontWeight: "bold" }}>Standard Clauses:</div>
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
                    Min UKC: <span style={{ color: "#88c0d0" }}>{report.min_ukc_m}m</span>
                  </div>
                )}
              </div>
            ) : (
              "Loading..."
            )}
          </div>
        </div>

        {/* RTZ Route Management */}
        <div style={{ marginBottom: "24px" }}>
          <h3 style={{ fontSize: "14px", marginBottom: "8px", color: "#81a1c1" }}>RTZ Route Management</h3>
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
              📥 Export RTZ
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
                📤 Import RTZ
              </button>
            </div>
          </div>
        </div>

        {/* Alerts Panel */}
        {report?.alerts && report.alerts.length > 0 && (
          <div>
            <h3 style={{ fontSize: "14px", marginBottom: "8px", color: "#81a1c1" }}>System Alerts</h3>
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

      {/* Main Map Area */}
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

        
          {/* Map Control Buttons */}
        <div style={{
          position: "absolute",
          top: "16px",
          right: "16px",
          display: "flex",
          flexDirection: "column",
          gap: "8px"
        }}>
            {/* Top-right evaluation panel (shown when comparison data available) */}
            {routeComparison && (
              <div style={{ alignSelf: "flex-end" }}>
                <EvaluationPanel 
                  routeComparison={routeComparison}
                  originalRouteLonLat={route}
                  dynamicRouteLonLat={dynamicRoute}
                />
              </div>
            )}
            {/* Optional advanced evaluation panel (segment-level alignment + real parameters), shown below evaluation card by default */}
            {routeComparison && (
              <div style={{ alignSelf: "flex-end" }}>
                <div style={{ height: 8 }} />
                <AdvancedAvoidanceEvaluationPanel 
                  originalRoute={route}
                  dynamicRoute={dynamicRoute}
                />
              </div>
            )}
          {/* Track Location Controls */}
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
              title="Center on track"
            >
              🎯 Track Center
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
              title="Auto-zoom to show full track"
            >
              🔍 Fit to View
            </button>
            {/* Rollback: Remove 🧮 Plan(Core) button */}
            <button
              onClick={async () => {
                try {
                  if (!route || route.length < 2) return;
                  const start = { lon: route[0][0], lat: route[0][1] };
                  const goal = { lon: route[route.length - 1][0], lat: route[route.length - 1][1] };
                  console.log('Executing global replan...');
                  // Use RouteService for route planning (will auto-trigger subscription update)
                  await routeService.planRoute(
                    { lat: route[0][1], lon: route[0][0] },
                    { lat: route[route.length - 1][1], lon: route[route.length - 1][0] }
                  );
                  
                  // Route will auto-update via subscription, no need to manually setRoute
                  setDynamicRoute([]);
                  
                  // Set manual override window
                  manualOverrideUntilRef.current = Date.now() + 30000;
                  console.log('Route planning complete, will auto-update via subscription');
                  
                  // Re-enable dynamic planning
                  setTimeout(() => {
                    setDynamicRouteEnabled(true);
                    mapRef.current?.zoomToFit();
                  }, 500);
                } catch (e) { console.error(e); }
              }}
              style={{
                padding: "4px 8px",
                background: "#d08770",
                color: "white",
                border: "none",
                borderRadius: "3px",
                cursor: "pointer",
                fontSize: "12px",
                display: "flex",
                alignItems: "center",
                gap: "4px"
              }}
              title="Complete replan under AIS constraints"
            >
              ♻️ Replan (Global)
            </button>
          </div>
          
          {/* Operation Tips */}
          <div style={{
            background: "rgba(46, 52, 64, 0.9)",
            padding: "8px",
            borderRadius: "4px",
            border: "1px solid #3b4252"
          }}>
            <div style={{ fontSize: "11px", color: "#81a1c1", lineHeight: "1.4" }}>
              📍 Mouse drag to pan | Scroll to zoom<br/>
              ⌨️ Space: Track center | F: Fit to view
            </div>
            
          </div>
        </div>
      </main>
    </div>
  );
}