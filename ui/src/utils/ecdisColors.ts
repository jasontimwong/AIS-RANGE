// ECDIS S-52 标准颜色方案
export type ColorScheme = 'DAY' | 'DUSK' | 'NIGHT';

export interface ECDISColors {
  // 水深区域
  NODTA: string;  // 无数据区
  DEPVS: string;  // 极浅水域 (0-2m)
  DEPSH: string;  // 浅水域 (2m-安全等深线)
  DEPMD: string;  // 中等深度 (安全等深线-2倍)
  DEPDW: string;  // 深水域 (>2倍安全等深线)
  
  // 陆地
  LANDA: string;  // 陆地区域
  LANDF: string;  // 前景陆地
  CSTLN: string;  // 海岸线
  
  // 危险和障碍
  SNDG1: string;  // 浅滩
  OBSTRN: string; // 障碍物
  WRECKS: string; // 沉船
  RESARE: string; // 限制区域
  
  // 助航标志
  LIGHTS: string; // 灯光
  BUOYAR: string; // 红色浮标
  BUOYAG: string; // 绿色浮标
  BUOYAY: string; // 黄色浮标
  
  // 航道和交通
  TSSCRS: string; // 分道通航制
  TSSLPT: string; // 分隔线/带
  RECTRC: string; // 推荐航线
  NAVLNE: string; // 导航线
  
  // 文字和符号
  CHBLK: string;  // 黑色字符
  CHGRD: string;  // 灰色字符
  CHGRF: string;  // 灰色填充
  CHRED: string;  // 红色字符
  CHGRN: string;  // 绿色字符
  CHYLW: string;  // 黄色字符
  CHMGD: string;  // 品红色字符
  
  // UI元素
  UINFD: string;  // UI信息
  UINFF: string;  // UI前景
  UINFB: string;  // UI背景
  UIAFD: string;  // UI区域
  
  // 雷达
  RADHI: string;  // 雷达高亮
  RADLO: string;  // 雷达低亮
}

export const ECDIS_PALETTE: Record<ColorScheme, ECDISColors> = {
  DAY: {
    // 水深 - 蓝色系
    NODTA: '#c0c0c0',
    DEPVS: '#b0e0e6',
    DEPSH: '#dbeef7',
    DEPMD: '#c6def7',
    DEPDW: '#acccef',
    
    // 陆地 - 沙色系
    LANDA: '#f5e9d3',
    LANDF: '#dec8a5',
    CSTLN: '#8b7355',
    
    // 危险 - 高对比
    SNDG1: '#84ada5',
    OBSTRN: '#0000ff',
    WRECKS: '#000000',
    RESARE: '#ff0000',
    
    // 助航标志
    LIGHTS: '#ffff00',
    BUOYAR: '#ff0000',
    BUOYAG: '#00ff00',
    BUOYAY: '#ffff00',
    
    // 航道
    TSSCRS: '#ff6eb4',
    TSSLPT: '#ff00ff',
    RECTRC: '#8b4513',
    NAVLNE: '#0000ff',
    
    // 文字
    CHBLK: '#000000',
    CHGRD: '#808080',
    CHGRF: '#808080',
    CHRED: '#ff0000',
    CHGRN: '#00ff00',
    CHYLW: '#ffff00',
    CHMGD: '#ff00ff',
    
    // UI
    UINFD: '#000000',
    UINFF: '#ffffff',
    UINFB: '#ffffff',
    UIAFD: '#000080',
    
    // 雷达
    RADHI: '#00ff00',
    RADLO: '#008000',
  },
  
  DUSK: {
    // 水深 - 低对比度蓝色
    NODTA: '#9c9c9c',
    DEPVS: '#8fb5bd',
    DEPSH: '#a5c6ce',
    DEPMD: '#94b5bd',
    DEPDW: '#8ca5ad',
    
    // 陆地 - 低对比度
    LANDA: '#c6b594',
    LANDF: '#b5a584',
    CSTLN: '#7b6b52',
    
    // 危险 - 中等对比
    SNDG1: '#738c84',
    OBSTRN: '#4a4aad',
    WRECKS: '#424242',
    RESARE: '#ce6363',
    
    // 助航标志
    LIGHTS: '#d6d652',
    BUOYAR: '#ce6363',
    BUOYAG: '#63ce63',
    BUOYAY: '#d6d652',
    
    // 航道
    TSSCRS: '#ce5a9c',
    TSSLPT: '#ce63ce',
    RECTRC: '#7b5a42',
    NAVLNE: '#4a4aad',
    
    // 文字
    CHBLK: '#424242',
    CHGRD: '#6b6b6b',
    CHGRF: '#6b6b6b',
    CHRED: '#ce6363',
    CHGRN: '#63ce63',
    CHYLW: '#d6d652',
    CHMGD: '#ce63ce',
    
    // UI
    UINFD: '#424242',
    UINFF: '#d6d6d6',
    UINFB: '#d6d6d6',
    UIAFD: '#4a4a7b',
    
    // 雷达
    RADHI: '#63ce63',
    RADLO: '#426342',
  },
  
  NIGHT: {
    // 水深 - 深色调
    NODTA: '#3f3f3f',
    DEPVS: '#2b4247',
    DEPSH: '#213139',
    DEPMD: '#182931',
    DEPDW: '#101821',
    
    // 陆地 - 深色
    LANDA: '#3f3919',
    LANDF: '#524a29',
    CSTLN: '#5a5a3a',
    
    // 危险 - 夜间可见（偏红保护夜视）
    SNDG1: '#394239',
    OBSTRN: '#8b0000',
    WRECKS: '#4a0000',
    RESARE: '#8b0000',
    
    // 助航标志 - 红色系
    LIGHTS: '#ff4500',
    BUOYAR: '#8b0000',
    BUOYAG: '#006400',
    BUOYAY: '#8b8b00',
    
    // 航道
    TSSCRS: '#8b1a1a',
    TSSLPT: '#8b008b',
    RECTRC: '#4a2908',
    NAVLNE: '#00008b',
    
    // 文字 - 红色系保护夜视
    CHBLK: '#8b0000',
    CHGRD: '#4a4a4a',
    CHGRF: '#4a4a4a',
    CHRED: '#8b0000',
    CHGRN: '#006400',
    CHYLW: '#8b8b00',
    CHMGD: '#8b008b',
    
    // UI
    UINFD: '#8b0000',
    UINFF: '#4a0000',
    UINFB: '#000000',
    UIAFD: '#00004a',
    
    // 雷达
    RADHI: '#00ff00',
    RADLO: '#004000',
  }
};

// 安全等深线配置
export interface SafetySettings {
  safetyDepth: number;      // 安全水深 (米)
  safetyContour: number;    // 安全等深线
  shallowContour: number;   // 浅水等深线  
  deepContour: number;      // 深水等深线
}

// 默认安全设置
export const DEFAULT_SAFETY_SETTINGS: SafetySettings = {
  safetyDepth: 10,         // 10米安全水深
  safetyContour: 10,       // 10米等深线
  shallowContour: 5,       // 5米浅水线
  deepContour: 20,         // 20米深水线
};

// 根据水深获取颜色
export function getDepthColor(
  depth: number, 
  settings: SafetySettings, 
  scheme: ColorScheme
): string {
  const colors = ECDIS_PALETTE[scheme];
  
  if (depth < 0) return colors.LANDA;  // 陆地
  if (depth < settings.shallowContour) return colors.DEPVS;  // 极浅
  if (depth < settings.safetyContour) return colors.DEPSH;   // 浅水
  if (depth < settings.deepContour) return colors.DEPMD;     // 中等
  return colors.DEPDW;  // 深水
}

// 获取UI文字颜色
export function getTextColor(scheme: ColorScheme, priority: 'primary' | 'secondary' | 'danger'): string {
  const colors = ECDIS_PALETTE[scheme];
  
  switch (priority) {
    case 'danger':
      return colors.CHRED;
    case 'primary':
      return scheme === 'NIGHT' ? colors.CHRED : colors.CHBLK;
    case 'secondary':
      return colors.CHGRD;
    default:
      return colors.CHBLK;
  }
}