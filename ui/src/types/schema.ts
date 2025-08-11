/**
 * ECDIS Route Planner UI - TypeScript Type Definitions
 * 从后端JSON Schema生成的类型定义
 */

// === 基础类型 ===

export type Position = {
  lon: number;
  lat: number;
  cog?: number; // Course over ground (度)
};

export type LonLat = [number, number];

export type BoundingBox = {
  min_lon: number;
  min_lat: number;
  max_lon: number;
  max_lat: number;
};

// === 规划请求类型 ===

export type PlanRequestV1 = {
  projection: "EPSG:3395" | "EPSG:4326";
  start: Position;
  goal: Position;
  safety_depth_m: number;
  min_turn_radius_nm: number;
  xtd_nm: number;
  max_speed_kn?: number;
  vessel_draft_m?: number;
  vessel_beam_m?: number;
  departure_time?: string; // ISO datetime
  eta_window_hours?: number;
};

// === 验证报告类型 ===

export type ClauseRef = {
  standard: string;          // 例: "IMO MSC.232(82)"
  clause: string;           // 例: "4.7.1"
  requirement?: string;     // 例: "安全深度检查"
  status: "COMPLIANT" | "WARN" | "FAIL";
  details?: string;
  evidence?: string;
};

export type AlertLevel = "A" | "B" | "C";

export type SystemAlert = {
  level: AlertLevel;
  msg: string;
  timestamp?: string;
  source?: string;
  acknowledged?: boolean;
};

export type ValidationReportV1 = {
  route_id?: string;
  timestamp?: string;
  clause_refs?: ClauseRef[];
  
  // 关键安全指标
  min_ukc_m?: number;           // 最小净空裕度
  min_water_depth_m?: number;   // 最小水深
  max_current_speed_kn?: number; // 最大流速
  
  // 告警系统
  alerts?: SystemAlert[];
  
  // 统计信息
  total_distance_nm?: number;
  estimated_duration_hours?: number;
  
  // 合规性汇总
  compliance_summary?: {
    total_checks: number;
    passed: number;
    warnings: number;
    failures: number;
  };
};

// === 路线几何类型 ===

export type RouteGeometry = {
  type: "LineString";
  coordinates: LonLat[];
};

export type Waypoint = {
  position: LonLat;
  name?: string;
  speed_kn?: number;
  turn_radius_nm?: number;
  eta?: string;
  special_maneuver?: string;
};

export type RouteSegment = {
  from_waypoint: number;
  to_waypoint: number;
  distance_nm: number;
  bearing_deg: number;
  speed_kn: number;
  duration_hours: number;
  safety_depth_m: number;
};

// === 4D规划类型（M7相关）===

export type TimeWindow = {
  start: string; // ISO datetime
  end: string;   // ISO datetime
};

export type TidalInfo = {
  station_id: string;
  water_level_m: number;
  tide_height_m: number;
  time: string;
};

export type FourDPlanRequest = PlanRequestV1 & {
  time_windows?: TimeWindow[];
  tide_stations?: string[];
  current_forecast?: boolean;
  eta_optimization?: boolean;
};

// === ENC数据类型 ===

export type EncLiteData = {
  // 基础地理要素
  coast?: LonLat[][][];      // 海岸线多边形
  shallow?: LonLat[][][];    // 浅水区域
  depths?: LonLat[][][];     // 等深线
  
  // 交通分离制
  tss?: {
    lanes?: LonLat[][][];    // 通航车道
    sep_zones?: LonLat[][][]; // 分隔带
    prohibited?: LonLat[][][]; // 禁航区
  };
  
  // 导航警告 (S-124)
  s124?: {
    speed_limits?: Array<{
      geometry: LonLat[][];
      max_speed_kn: number;
      time_window?: TimeWindow;
    }>;
    prohibited?: Array<{
      geometry: LonLat[][];
      reason: string;
      time_window?: TimeWindow;
    }>;
    construction?: Array<{
      geometry: LonLat[][];
      description: string;
      time_window?: TimeWindow;
    }>;
  };
  
  // 辅助信息
  bounds?: BoundingBox;
  chart_scale?: number;
  update_time?: string;
};

// === 交通目标类型 ===

export type TrafficTarget = {
  mmsi?: number;
  name?: string;
  position: LonLat;
  cog: number;      // Course over ground
  sog: number;      // Speed over ground
  heading?: number;
  length_m?: number;
  beam_m?: number;
  draft_m?: number;
  ship_type?: string;
  status?: "under_way" | "anchored" | "not_under_command" | "restricted_maneuver";
  timestamp: string;
};

export type CPAResult = {
  target_mmsi?: number;
  cpa_distance_nm: number;    // Closest Point of Approach distance
  tcpa_minutes: number;       // Time to CPA
  cpa_position: LonLat;      // CPA地理位置
  risk_level: "HIGH" | "MEDIUM" | "LOW" | "NONE";
  collision_risk: boolean;
  recommended_action?: string;
};

// === UI状态类型 ===

export type MapViewState = {
  center: LonLat;
  zoom: number;
  bearing?: number;
  pitch?: number;
};

export type LayerVisibility = {
  enc: boolean;
  route: boolean;
  tss: boolean;
  s124: boolean;
  traffic: boolean;
  currents: boolean;
  tides: boolean;
  debug: boolean;
};

export type UISettings = {
  theme: "dark" | "light";
  units: "metric" | "imperial" | "nautical";
  language: "zh" | "en";
  alerts_enabled: boolean;
  sound_enabled: boolean;
  auto_zoom: boolean;
};

// === API响应类型 ===

export type ApiResponse<T> = {
  success: boolean;
  data?: T;
  error?: string;
  timestamp: string;
};

export type PlanResponse = ApiResponse<{
  route_id: string;
  geometry: RouteGeometry;
  waypoints: Waypoint[];
  segments: RouteSegment[];
  validation_report: ValidationReportV1;
  metadata: {
    planner_version: string;
    planning_time_ms: number;
    total_distance_nm: number;
    estimated_duration_hours: number;
  };
}>;

export type ValidationResponse = ApiResponse<ValidationReportV1>;

export type ServiceStatus = {
  service: string;
  version: string;
  status: "healthy" | "degraded" | "down";
  uptime_seconds: number;
  features: {
    planning: boolean;
    validation: boolean;
    colreg: boolean;
    four_d: boolean;
    enc_data: boolean;
  };
  last_check: string;
};

// === 导出/导入类型 ===

export type RTZMetadata = {
  name: string;
  version: string;
  created: string;
  manufacturer: string;
  planning_speed_kn?: number;
  ecdis_route_id?: string;
};

export type RTZWaypoint = {
  id: string;
  name?: string;
  position: LonLat;
  radius_nm?: number;
  speed_kn?: number;
  eta?: string;
  notes?: string;
};

export type RTZRoute = {
  metadata: RTZMetadata;
  waypoints: RTZWaypoint[];
  route_info?: {
    total_distance_nm: number;
    estimated_duration_hours: number;
    departure_time?: string;
    arrival_time?: string;
  };
};