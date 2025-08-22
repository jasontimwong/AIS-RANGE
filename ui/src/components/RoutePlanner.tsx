import React, { useState, useRef } from 'react';
import { routeService } from '../services/routeService';

interface RoutePoint {
  name: string;
  lat: number;
  lon: number;
}

// Predefined common ports (optimized for safe sea coordinates, avoiding land crossing)
const COMMON_PORTS: RoutePoint[] = [
  { name: "Shanghai Port", lat: 31.23, lon: 121.508 },
  { name: "Singapore Port", lat: 1.265, lon: 103.851 },     // Fixed: Correct Singapore coordinates
  { name: "Hong Kong", lat: 22.3, lon: 114.2 },
  { name: "Shenzhen Port", lat: 22.5, lon: 114.1 },
  { name: "Ningbo-Zhoushan Port", lat: 29.95, lon: 122.2 },
  { name: "Qingdao Port", lat: 36.0, lon: 120.6 },         // Fixed: Qingdao outer anchorage
  { name: "Tianjin Port", lat: 38.7, lon: 118.2 },         // Fixed: Bohai Bay outer anchorage
  { name: "Guangzhou Port", lat: 23.1, lon: 113.25 },
  { name: "Xiamen Port", lat: 24.48, lon: 118.08 },
  { name: "Dalian Port", lat: 38.92, lon: 121.65 },
  { name: "Malacca", lat: 1.0, lon: 99.0 },           // Fixed: Malacca southwest safe waters
  { name: "Port Klang", lat: 2.8, lon: 101.0 },          // Fixed: Port Klang southwest anchorage
  { name: "Jakarta", lat: -6.1, lon: 106.87 },
  { name: "Manila", lat: 14.4, lon: 120.7 },         // Fixed: Manila Bay outer anchorage
  { name: "Busan Port", lat: 35.1, lon: 129.04 },
  { name: "Yokohama Port", lat: 35.44, lon: 139.64 },
  { name: "Kobe Port", lat: 34.5, lon: 135.0 },         // Fixed: Osaka Bay outer anchorage
  { name: "Nagoya Port", lat: 34.8, lon: 136.6 }        // Fixed: Ise Bay outer anchorage
];

// Predefined classic routes (based on TSS traffic separation and actual channel optimization)
const CLASSIC_ROUTES = [
  { name: "Shanghai-Singapore (TSS)", start: "Shanghai Port", end: "Singapore Port", 
    description: "Via Taiwan Strait East Channel→South China Sea→Singapore Strait TSS" },
  { name: "Shanghai-Hong Kong", start: "Shanghai Port", end: "Hong Kong" },
  { name: "Shenzhen-Singapore (TSS)", start: "Shenzhen Port", end: "Singapore Port",
    description: "Via South China Sea Main Channel→Singapore Strait TSS Southbound Lane" },
  { name: "Ningbo-Malacca (TSS)", start: "Ningbo-Zhoushan Port", end: "Malacca",
    description: "Via East China Sea→South China Sea→Malacca Strait TSS Westbound Lane" },
  { name: "Qingdao-Busan (TSS)", start: "Qingdao Port", end: "Busan Port",
    description: "Via Yellow Sea TSS→Busan Port Approach Channel" },
  { name: "Tianjin-Yokohama (TSS)", start: "Tianjin Port", end: "Yokohama Port",
    description: "Via Bohai Sea→Yellow Sea→East China Sea→Tokyo Bay TSS" },
  { name: "Guangzhou-Jakarta", start: "Guangzhou Port", end: "Jakarta" },
  { name: "Xiamen-Manila", start: "Xiamen Port", end: "Manila" }
];

interface RoutePlannerProps {
  onRouteSelect: (route: [number, number][]) => void;
  onPlanningStart?: () => void;
  onPlanningComplete?: (route: [number, number][], time: number) => void;
  onPlanningError?: (error: string) => void;
}

export const RoutePlanner: React.FC<RoutePlannerProps> = ({
  onRouteSelect,
  onPlanningStart,
  onPlanningComplete,
  onPlanningError
}) => {
  const [startPort, setStartPort] = useState<RoutePoint | null>(null);
  const [endPort, setEndPort] = useState<RoutePoint | null>(null);
  const [customStart, setCustomStart] = useState({ lat: '', lon: '' });
  const [customEnd, setCustomEnd] = useState({ lat: '', lon: '' });
  const [isPlanning, setIsPlanning] = useState(false);
  const [planningMode, setPlanningMode] = useState<'preset' | 'custom'>('preset');
  const [lastPlanTime, setLastPlanTime] = useState<number | null>(null);

  // Execute route planning
  const executePlanning = async () => {
    let start: RoutePoint | null = null;
    let end: RoutePoint | null = null;

    if (planningMode === 'preset') {
      start = startPort;
      end = endPort;
    } else {
      // Custom coordinates
      if (customStart.lat && customStart.lon && customEnd.lat && customEnd.lon) {
        start = {
          name: 'Custom Start',
          lat: parseFloat(customStart.lat),
          lon: parseFloat(customStart.lon)
        };
        end = {
          name: 'Custom End',
          lat: parseFloat(customEnd.lat),
          lon: parseFloat(customEnd.lon)
        };
      }
    }

    if (!start || !end) {
      onPlanningError?.('Please select or enter start and end points');
      return;
    }

    setIsPlanning(true);
    onPlanningStart?.();

    try {
      const startTime = Date.now();
      // Use RouteService for route planning
      const coords = await routeService.planRoute(
        { lat: start.lat, lon: start.lon },
        { lat: end.lat, lon: end.lon }
      );
      
      const planTime = (Date.now() - startTime) / 1000;
      setLastPlanTime(planTime);
      
      if (coords && coords.length > 0) {
        onRouteSelect(coords);
        onPlanningComplete?.(coords, planTime);
        console.log(`Planning complete: ${start.name} → ${end.name}, took ${planTime.toFixed(2)} seconds`);
      } else {
        throw new Error('No valid route returned');
      }
    } catch (error) {
      console.error('Route planning failed:', error);
      onPlanningError?.(error instanceof Error ? error.message : 'Planning failed');
    } finally {
      setIsPlanning(false);
    }
  };

  // Quick select classic route
  const selectClassicRoute = (route: typeof CLASSIC_ROUTES[0]) => {
    const start = COMMON_PORTS.find(p => p.name === route.start);
    const end = COMMON_PORTS.find(p => p.name === route.end);
    if (start && end) {
      setStartPort(start);
      setEndPort(end);
      setPlanningMode('preset');
    }
  };

  return (
    <div style={{
      background: '#2e3440',
      padding: '16px',
      borderRadius: '8px',
      color: '#d8dee9'
    }}>
      <h3 style={{ margin: '0 0 16px 0', color: '#88c0d0', fontSize: '16px' }}>
        🧭 Route Planner
      </h3>

      {/* Mode Selection */}
      <div style={{ marginBottom: '16px' }}>
        <label style={{ marginRight: '16px' }}>
          <input
            type="radio"
            checked={planningMode === 'preset'}
            onChange={() => setPlanningMode('preset')}
            style={{ marginRight: '4px' }}
          />
          Preset Ports
        </label>
        <label>
          <input
            type="radio"
            checked={planningMode === 'custom'}
            onChange={() => setPlanningMode('custom')}
            style={{ marginRight: '4px' }}
          />
          Custom Coordinates
        </label>
      </div>

      {planningMode === 'preset' ? (
        <>
          {/* Classic Route Quick Selection */}
          <div style={{ marginBottom: '16px' }}>
            <div style={{ fontSize: '12px', color: '#81a1c1', marginBottom: '8px' }}>
              Quick Select:
            </div>
            <div style={{ display: 'flex', flexWrap: 'wrap', gap: '4px' }}>
              {CLASSIC_ROUTES.map(route => (
                <button
                  key={route.name}
                  onClick={() => selectClassicRoute(route)}
                  style={{
                    padding: '4px 8px',
                    background: '#3b4252',
                    color: '#d8dee9',
                    border: '1px solid #4c566a',
                    borderRadius: '4px',
                    fontSize: '11px',
                    cursor: 'pointer'
                  }}
                  onMouseOver={e => e.currentTarget.style.background = '#434c5e'}
                  onMouseOut={e => e.currentTarget.style.background = '#3b4252'}
                >
                  {route.name}
                </button>
              ))}
            </div>
          </div>

          {/* Start Point Selection */}
          <div style={{ marginBottom: '12px' }}>
            <label style={{ display: 'block', fontSize: '12px', color: '#81a1c1', marginBottom: '4px' }}>
              Start Port:
            </label>
            <select
              value={startPort?.name || ''}
              onChange={e => {
                const port = COMMON_PORTS.find(p => p.name === e.target.value);
                setStartPort(port || null);
              }}
              style={{
                width: '100%',
                padding: '6px',
                background: '#3b4252',
                color: '#d8dee9',
                border: '1px solid #4c566a',
                borderRadius: '4px',
                fontSize: '12px'
              }}
            >
              <option value="">Select start...</option>
              {COMMON_PORTS.map(port => (
                <option key={port.name} value={port.name}>
                  {port.name} ({port.lat.toFixed(2)}, {port.lon.toFixed(2)})
                </option>
              ))}
            </select>
          </div>

          {/* End Point Selection */}
          <div style={{ marginBottom: '12px' }}>
            <label style={{ display: 'block', fontSize: '12px', color: '#81a1c1', marginBottom: '4px' }}>
              End Port:
            </label>
            <select
              value={endPort?.name || ''}
              onChange={e => {
                const port = COMMON_PORTS.find(p => p.name === e.target.value);
                setEndPort(port || null);
              }}
              style={{
                width: '100%',
                padding: '6px',
                background: '#3b4252',
                color: '#d8dee9',
                border: '1px solid #4c566a',
                borderRadius: '4px',
                fontSize: '12px'
              }}
            >
              <option value="">Select end...</option>
              {COMMON_PORTS.map(port => (
                <option key={port.name} value={port.name}>
                  {port.name} ({port.lat.toFixed(2)}, {port.lon.toFixed(2)})
                </option>
              ))}
            </select>
          </div>
        </>
      ) : (
        <>
          {/* Custom Coordinate Input */}
          <div style={{ marginBottom: '12px' }}>
            <label style={{ display: 'block', fontSize: '12px', color: '#81a1c1', marginBottom: '4px' }}>
              Start Coordinates:
            </label>
            <div style={{ display: 'flex', gap: '8px' }}>
              <input
                type="number"
                placeholder="Latitude"
                value={customStart.lat}
                onChange={e => setCustomStart({ ...customStart, lat: e.target.value })}
                style={{
                  flex: 1,
                  padding: '6px',
                  background: '#3b4252',
                  color: '#d8dee9',
                  border: '1px solid #4c566a',
                  borderRadius: '4px',
                  fontSize: '12px'
                }}
              />
              <input
                type="number"
                placeholder="Longitude"
                value={customStart.lon}
                onChange={e => setCustomStart({ ...customStart, lon: e.target.value })}
                style={{
                  flex: 1,
                  padding: '6px',
                  background: '#3b4252',
                  color: '#d8dee9',
                  border: '1px solid #4c566a',
                  borderRadius: '4px',
                  fontSize: '12px'
                }}
              />
            </div>
          </div>

          <div style={{ marginBottom: '12px' }}>
            <label style={{ display: 'block', fontSize: '12px', color: '#81a1c1', marginBottom: '4px' }}>
              End Coordinates:
            </label>
            <div style={{ display: 'flex', gap: '8px' }}>
              <input
                type="number"
                placeholder="Latitude"
                value={customEnd.lat}
                onChange={e => setCustomEnd({ ...customEnd, lat: e.target.value })}
                style={{
                  flex: 1,
                  padding: '6px',
                  background: '#3b4252',
                  color: '#d8dee9',
                  border: '1px solid #4c566a',
                  borderRadius: '4px',
                  fontSize: '12px'
                }}
              />
              <input
                type="number"
                placeholder="Longitude"
                value={customEnd.lon}
                onChange={e => setCustomEnd({ ...customEnd, lon: e.target.value })}
                style={{
                  flex: 1,
                  padding: '6px',
                  background: '#3b4252',
                  color: '#d8dee9',
                  border: '1px solid #4c566a',
                  borderRadius: '4px',
                  fontSize: '12px'
                }}
              />
            </div>
          </div>
        </>
      )}

      {/* Planning Button */}
      <button
        onClick={executePlanning}
        disabled={isPlanning}
        style={{
          width: '100%',
          padding: '8px',
          background: isPlanning ? '#4c566a' : '#5e81ac',
          color: 'white',
          border: 'none',
          borderRadius: '4px',
          cursor: isPlanning ? 'not-allowed' : 'pointer',
          fontSize: '14px',
          fontWeight: 'bold'
        }}
      >
        {isPlanning ? '⏳ Planning...' : '🚀 Start Planning'}
      </button>

      {/* Show Last Planning Time */}
      {lastPlanTime !== null && (
        <div style={{
          marginTop: '8px',
          fontSize: '11px',
          color: '#a3be8c',
          textAlign: 'center'
        }}>
          ✅ Last planning took: {lastPlanTime.toFixed(2)} seconds
        </div>
      )}

      {/* Tips */}
      <div style={{
        marginTop: '12px',
        padding: '8px',
        background: '#3b4252',
        borderRadius: '4px',
        fontSize: '11px',
        color: '#81a1c1',
        lineHeight: '1.4'
      }}>
        💡 Tips:
        <br />• Use preset ports for quick planning of common routes
        <br />• Custom coordinates support any start/end points
        <br />• Planning considers current AIS targets for collision avoidance
        <br />• Uses 50m precision Hybrid A* algorithm
      </div>
    </div>
  );
};