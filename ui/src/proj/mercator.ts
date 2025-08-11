export type Viewport = { 
  center: [number, number]; // [lon, lat]
  zoom: number; 
  width: number; 
  height: number; 
  dpr: number; 
};

const DEG2RAD = Math.PI / 180;
const RAD2DEG = 180 / Math.PI;

/**
 * 经纬度转换为屏幕坐标（Web墨卡托投影）
 * @param lon 经度
 * @param lat 纬度  
 * @param cx 视窗中心经度
 * @param cy 视窗中心纬度
 * @param zoom 缩放级别
 * @param w 屏幕宽度
 * @param h 屏幕高度
 */
export function lonLatToXY(
  lon: number, 
  lat: number, 
  cx: number, 
  cy: number, 
  zoom: number, 
  w: number, 
  h: number
) {
  // 限制纬度范围避免墨卡托投影奇点
  lat = Math.max(-85.0511, Math.min(85.0511, lat));
  cy = Math.max(-85.0511, Math.min(85.0511, cy));
  
  const scale = Math.pow(2, zoom) * 256;
  
  // 标准Web墨卡托投影公式
  const x = (lon + 180) / 360 * scale;
  const y = (1 - Math.log(Math.tan(lat * DEG2RAD) + 1 / Math.cos(lat * DEG2RAD)) / Math.PI) / 2 * scale;
  
  // 计算视窗中心对应的投影坐标
  const cxp = (cx + 180) / 360 * scale;
  const cyp = (1 - Math.log(Math.tan(cy * DEG2RAD) + 1 / Math.cos(cy * DEG2RAD)) / Math.PI) / 2 * scale;
  
  // 转换为相对于屏幕中心的坐标
  return { 
    x: (x - cxp) + w / 2, 
    y: (y - cyp) + h / 2 
  };
}

/**
 * 屏幕坐标转换为经纬度（Web墨卡托反投影）
 * @param x 屏幕x坐标
 * @param y 屏幕y坐标
 * @param cx 视窗中心经度
 * @param cy 视窗中心纬度
 * @param zoom 缩放级别
 * @param w 屏幕宽度
 * @param h 屏幕高度
 */
export function xyToLonLat(
  x: number, 
  y: number, 
  cx: number, 
  cy: number, 
  zoom: number, 
  w: number, 
  h: number
) {
  const scale = Math.pow(2, zoom) * 256;
  
  // 计算视窗中心对应的投影坐标
  const cxp = (cx + 180) / 360 * scale;
  const cyp = (1 - Math.log(Math.tan(cy * DEG2RAD) + 1 / Math.cos(cy * DEG2RAD)) / Math.PI) / 2 * scale;
  
  // 转换为投影坐标
  const projX = (x - w / 2) + cxp;
  const projY = (y - h / 2) + cyp;
  
  // Web墨卡托反投影
  const lon = (projX / scale) * 360 - 180;
  const n = Math.PI - 2 * Math.PI * projY / scale;
  const lat = RAD2DEG * Math.atan(0.5 * (Math.exp(n) - Math.exp(-n)));
  
  return { lon, lat };
}

/**
 * 计算两点间的距离（球面距离，单位：米）
 * 使用Haversine公式
 */
export function distanceHaversine(
  lon1: number, lat1: number, 
  lon2: number, lat2: number
): number {
  const R = 6371000; // 地球半径（米）
  
  const dLat = (lat2 - lat1) * DEG2RAD;
  const dLon = (lon2 - lon1) * DEG2RAD;
  const lat1Rad = lat1 * DEG2RAD;
  const lat2Rad = lat2 * DEG2RAD;

  const a = Math.sin(dLat / 2) * Math.sin(dLat / 2) +
            Math.sin(dLon / 2) * Math.sin(dLon / 2) * 
            Math.cos(lat1Rad) * Math.cos(lat2Rad);
  
  const c = 2 * Math.atan2(Math.sqrt(a), Math.sqrt(1 - a));
  
  return R * c;
}

/**
 * 计算方位角（度数，0-360）
 */
export function bearing(
  lon1: number, lat1: number, 
  lon2: number, lat2: number
): number {
  const dLon = (lon2 - lon1) * DEG2RAD;
  const lat1Rad = lat1 * DEG2RAD;
  const lat2Rad = lat2 * DEG2RAD;

  const y = Math.sin(dLon) * Math.cos(lat2Rad);
  const x = Math.cos(lat1Rad) * Math.sin(lat2Rad) -
            Math.sin(lat1Rad) * Math.cos(lat2Rad) * Math.cos(dLon);

  const bearingRad = Math.atan2(y, x);
  return ((bearingRad * RAD2DEG) + 360) % 360;
}

/**
 * 根据边界框计算合适的缩放级别和中心点
 */
export function fitBounds(
  bounds: [[number, number], [number, number]], // [[minLon, minLat], [maxLon, maxLat]]
  width: number,
  height: number,
  padding: number = 50
): { center: [number, number], zoom: number } {
  const [[minLon, minLat], [maxLon, maxLat]] = bounds;
  
  const center: [number, number] = [
    (minLon + maxLon) / 2,
    (minLat + maxLat) / 2
  ];
  
  // 计算需要显示的范围
  const lonRange = maxLon - minLon;
  const latRange = maxLat - minLat;
  
  // 转换为墨卡托坐标系下的范围
  const scale256 = 256; // 缩放级别0时的瓦片大小
  
  // 考虑padding，计算可用的显示区域
  const availableWidth = width - padding * 2;
  const availableHeight = height - padding * 2;
  
  // 计算横向和纵向需要的缩放级别
  const zoomX = Math.log2(availableWidth * 360 / lonRange / scale256);
  const zoomY = Math.log2(availableHeight * 180 / latRange / scale256);
  
  // 取较小的缩放级别以确保所有内容都能显示
  const zoom = Math.max(2, Math.min(18, Math.floor(Math.min(zoomX, zoomY))));
  
  return { center, zoom };
}