/**
 * Route Service - Unified management for route data fetching, storage and synchronization
 */

import { planFullRoute } from '../api/client';

export type RoutePoint = [number, number]; // [lon, lat]
export type Route = RoutePoint[];

interface RouteData {
  route: Route;
  timestamp: number;
  source: 'user' | 'default' | 'planned';
  metadata?: {
    start?: { lat: number; lon: number };
    goal?: { lat: number; lon: number };
    planningTime?: number;
    pointCount?: number;
  };
}

const STORAGE_KEY = 'ecdis_current_route';
const CACHE_DURATION = 24 * 60 * 60 * 1000; // 24 hours

/**
 * Route Service Class - Singleton Pattern
 */
class RouteService {
  private static instance: RouteService;
  private currentRoute: RouteData | null = null;
  private listeners: Set<(route: Route) => void> = new Set();

  private constructor() {
    this.loadFromStorage();
  }

  static getInstance(): RouteService {
    if (!RouteService.instance) {
      RouteService.instance = new RouteService();
    }
    return RouteService.instance;
  }

  /**
   * Get current route
   */
  getCurrentRoute(): Route | null {
    // Priority: return route from memory
    if (this.currentRoute) {
      return this.currentRoute.route;
    }

    // Try to load from localStorage
    this.loadFromStorage();
    return this.currentRoute?.route || null;
  }

  /**
   * Set new route (user planned)
   */
  setPlannedRoute(route: Route, metadata?: RouteData['metadata']): void {
    this.currentRoute = {
      route,
      timestamp: Date.now(),
      source: 'planned',
      metadata
    };
    
    this.saveToStorage();
    this.notifyListeners(route);
    console.log('Route Service: Saved planned route with', route.length, 'points');
  }

  /**
   * Set default route (system provided example)
   */
  setDefaultRoute(route: Route): void {
    // Only set default route when there's no user planned route
    if (!this.currentRoute || this.currentRoute.source === 'default') {
      this.currentRoute = {
        route,
        timestamp: Date.now(),
        source: 'default'
      };
      
      this.saveToStorage();
      this.notifyListeners(route);
      console.log('Route Service: Default route set');
    }
  }

  /**
   * Plan new route
   */
  async planRoute(start: { lat: number; lon: number }, goal: { lat: number; lon: number }): Promise<Route> {
    try {
      console.log('Route Service: Starting route planning...');
      const t0 = Date.now();

      // 1) Preferred: After initializing with dynamic planner, get "baseline" from comparison endpoint (complete route consistent with system standard)
      let baselineLonLat: Route = [];
      try {
        const initRes = await fetch('/api/route/initialize', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ waypoints: [{ lat: start.lat, lon: start.lon }, { lat: goal.lat, lon: goal.lon }] })
        });
        if (initRes.ok) {
          const dynRes = await fetch(`/api/route/dynamic?current_lat=${start.lat}&current_lon=${start.lon}`);
          if (dynRes.ok) {
            const dynData = await dynRes.json();
            const cmp = dynData?.route_comparison || {};
            const baselineLL: Array<[number, number]> = Array.isArray(cmp.original_route) ? cmp.original_route : [];
            baselineLonLat = baselineLL.map(([lat, lon]) => [lon, lat]);
          }
        }
      } catch (e) {
        console.warn('Dynamic initialization/baseline fetch failed (will fallback to plan_full)', e);
      }

      // 2) Fallback: Call standard complete planner directly
      if (baselineLonLat.length <= 2) {
        try {
          const fullPlan = await planFullRoute(start, goal);
          baselineLonLat = Array.isArray(fullPlan?.coords) ? fullPlan.coords : [];
        } catch (e) {
          console.warn('plan_full fallback failed', e);
        }
      }

      // 3) Last resort: Frontend simple great circle interpolation to avoid only two straight points
      if (baselineLonLat.length <= 2) {
        const n = 200;
        const lon0 = start.lon, lat0 = start.lat;
        const lon1 = goal.lon, lat1 = goal.lat;
        const toRad = (d: number) => d * Math.PI / 180;
        const toDeg = (r: number) => r * 180 / Math.PI;
        const φ1 = toRad(lat0), λ1 = toRad(lon0);
        const φ2 = toRad(lat1), λ2 = toRad(lon1);
        const Δ = 2 * Math.asin(Math.sqrt(Math.sin((φ2-φ1)/2)**2 + Math.cos(φ1)*Math.cos(φ2)*Math.sin((λ2-λ1)/2)**2));
        const coords: Route = [];
        for (let i = 0; i < n; i++) {
          const f = i / (n - 1);
          const A = Math.sin((1-f)*Δ) / Math.sin(Δ);
          const B = Math.sin(f*Δ) / Math.sin(Δ);
          const x = A * Math.cos(φ1) * Math.cos(λ1) + B * Math.cos(φ2) * Math.cos(λ2);
          const y = A * Math.cos(φ1) * Math.sin(λ1) + B * Math.cos(φ2) * Math.sin(λ2);
          const z = A * Math.sin(φ1) + B * Math.sin(φ2);
          const φ = Math.atan2(z, Math.sqrt(x*x + y*y));
          const λ = Math.atan2(y, x);
          coords.push([toDeg(λ), toDeg(φ)]);
        }
        baselineLonLat = coords;
      }

      if (baselineLonLat.length < 2) throw new Error('Planning returned empty route');
      const baseline = this.downsample(baselineLonLat, 800);
      const planningTime = (Date.now() - t0) / 1000;

      // 2) Save baseline as main track (consistent with initial route style)
      this.setPlannedRoute(baseline, {
        start,
        goal,
        planningTime,
        pointCount: baseline.length
      });

      // 4) Notify backend to initialize dynamic planning (using complete baseline as original route) for red dynamic route comparison
      try {
        const waypoints = baseline.map(([lon, lat]) => ({ lat, lon }));
        await fetch('/api/route/initialize', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ waypoints })
        });
      } catch (e) {
        console.warn('Dynamic route initialization failed (ignored, does not affect baseline display)', e);
      }

      console.log('Route Service: Planning successful,', baseline.length, 'points, took', planningTime, 'seconds');
      return baseline;
    } catch (error) {
      console.error('Route Service: Planning failed', error);
      throw error;
    }
  }

  /**
   * Simple bidirectional uniform downsampling, limit points to maxPoints
   */
  private downsample(route: Route, maxPoints: number): Route {
    if (!route || route.length <= maxPoints) return route;
    const stride = Math.max(1, Math.floor(route.length / maxPoints));
    const out: Route = [];
    for (let i = 0; i < route.length; i += stride) out.push(route[i]);
    if (out[out.length - 1] !== route[route.length - 1]) out.push(route[route.length - 1]);
    return out;
  }

  /**
   * Clear current route
   */
  clearRoute(): void {
    this.currentRoute = null;
    localStorage.removeItem(STORAGE_KEY);
    this.notifyListeners([]);
    console.log('Route Service: Route cleared');
  }

  /**
   * Check if there is a user planned route
   */
  hasUserPlannedRoute(): boolean {
    return this.currentRoute?.source === 'planned' || this.currentRoute?.source === 'user';
  }

  /**
   * Get route metadata
   */
  getRouteMetadata(): RouteData['metadata'] | null {
    return this.currentRoute?.metadata || null;
  }

  /**
   * Subscribe to route changes
   */
  subscribe(listener: (route: Route) => void): () => void {
    this.listeners.add(listener);
    // Return unsubscribe function
    return () => {
      this.listeners.delete(listener);
    };
  }

  /**
   * Load route from localStorage
   */
  private loadFromStorage(): void {
    try {
      const stored = localStorage.getItem(STORAGE_KEY);
      if (stored) {
        const data = JSON.parse(stored) as RouteData;
        
        // Check if cache is expired
        if (Date.now() - data.timestamp < CACHE_DURATION) {
          this.currentRoute = data;
          console.log('Route Service: Loaded route from cache,', data.route.length, 'points, source:', data.source);
        } else {
          console.log('Route Service: Cache expired');
          localStorage.removeItem(STORAGE_KEY);
        }
      }
    } catch (error) {
      console.error('Route Service: Failed to load cache', error);
      localStorage.removeItem(STORAGE_KEY);
    }
  }

  /**
   * Save route to localStorage
   */
  private saveToStorage(): void {
    if (this.currentRoute) {
      try {
        localStorage.setItem(STORAGE_KEY, JSON.stringify(this.currentRoute));
        console.log('Route Service: Saved to cache');
      } catch (error) {
        console.error('Route Service: Failed to save cache', error);
      }
    }
  }

  /**
   * Notify all listeners
   */
  private notifyListeners(route: Route): void {
    this.listeners.forEach(listener => {
      try {
        listener(route);
      } catch (error) {
        console.error('Route Service: Listener error', error);
      }
    });
  }

  /**
   * Export route as JSON
   */
  exportRoute(): string {
    if (!this.currentRoute) {
      throw new Error('No route to export');
    }
    
    return JSON.stringify({
      ...this.currentRoute,
      exportTime: new Date().toISOString(),
      version: '1.0.0'
    }, null, 2);
  }

  /**
   * Import route from JSON
   */
  importRoute(json: string): void {
    try {
      const data = JSON.parse(json);
      if (!data.route || !Array.isArray(data.route)) {
        throw new Error('Invalid route data');
      }
      
      this.currentRoute = {
        route: data.route,
        timestamp: Date.now(),
        source: 'user',
        metadata: data.metadata
      };
      
      this.saveToStorage();
      this.notifyListeners(this.currentRoute.route);
      console.log('Route Service: Imported route with', this.currentRoute.route.length, 'points');
    } catch (error) {
      console.error('Route Service: Import failed', error);
      throw error;
    }
  }
}

// Export singleton instance
export const routeService = RouteService.getInstance();

// Export convenience functions
export const getCurrentRoute = () => routeService.getCurrentRoute();
export const setPlannedRoute = (route: Route, metadata?: RouteData['metadata']) => 
  routeService.setPlannedRoute(route, metadata);
export const planRoute = (start: { lat: number; lon: number }, goal: { lat: number; lon: number }) => 
  routeService.planRoute(start, goal);
export const clearRoute = () => routeService.clearRoute();
export const hasUserPlannedRoute = () => routeService.hasUserPlannedRoute();