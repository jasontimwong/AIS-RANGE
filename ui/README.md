# ECDIS UI - 研究级可视化界面

零外网依赖的海事导航可视化界面，支持路径规划、风险分析和合规展示。

## 快速开始

```bash
# 安装依赖
cd ui && npm install

# 启动开发服务器
npm run dev

# 构建生产版本
npm run build
```

## 特性

- ✅ Canvas自绘地图（零依赖）
- ✅ ENC-lite图层渲染
- ✅ 路径规划可视化
- ✅ 风险分析面板
- ✅ 合规条款展示
- ✅ 4D时域视图

## 架构原则

- 离线/内网运行，零外部CDN
- 不改后端v1 API，UI仅消费OpenAPI/JSON Schema
- 可回退：特性开关 + git tag
- 研究级标准（遵循IEC 62288思路）
