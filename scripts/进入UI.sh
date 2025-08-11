#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"; cd "$ROOT"

echo "🎨 进入UI开发阶段..."
echo "══════════════════════════════════════════════════════"

# 1) 打回退点
TAG="v1.0.1-pre-UI-$(date +%Y%m%d_%H%M)"
git add -A && git commit -m "chore: freeze before UI stage - M10 complete, entering UI phase" || true
git tag -a "$TAG" -m "Pre UI entrypoint - Production ready baseline"
echo "✅ 已打回退标签: $TAG"

# 2) 开启 UI 相关特性（其余保持既有策略）
python - <<'PY'
import yaml,os,json
os.makedirs("config",exist_ok=True)

# 创建或更新feature flags
flags = {
  "ui_ecdis": True,           # 新：ECDIS-like UI
  "ui_debug_layers": True,    # 新：调试图层
  "colreg_rules": True,       # 已有：建议保留展示
  "s101_adapter": True,       # S-101适配器
  "s102_adapter": True,       # S-102高分辨率水深
  "s111_currents": True,      # S-111表层流
  "s124_warnings": True,      # S-124航行警告
  "ukc_plugin": True,         # UKC插件
  "four_d_planner": True,     # M7已完成，启用4D规划
  "safety_shield": True,      # M8安全护盾
  "tile_management": True,    # M9瓦片管理
  "version_management": True, # M10版本管理
}

# 检查是否存在YAML文件，否则创建JSON
yaml_file = "config/feature_flags.yaml"
json_file = "config/feature_flags.json"

try:
    if os.path.exists(yaml_file):
        with open(yaml_file, "r", encoding="utf-8") as f:
            cur = yaml.safe_load(f) or {}
        cur.setdefault("feature_flags", {}).update(flags)
        with open(yaml_file, "w", encoding="utf-8") as f:
            yaml.safe_dump(cur, f, allow_unicode=True, sort_keys=False)
        print("✅ 更新feature flags (YAML):", cur["feature_flags"])
    else:
        # 使用JSON格式
        if os.path.exists(json_file):
            with open(json_file, "r", encoding="utf-8") as f:
                cur = json.load(f)
        else:
            cur = {}
        cur.setdefault("feature_flags", {}).update(flags)
        with open(json_file, "w", encoding="utf-8") as f:
            json.dump(cur, f, indent=2, ensure_ascii=False)
        print("✅ 更新feature flags (JSON):", cur["feature_flags"])
except ImportError:
    # 如果没有pyyaml，使用JSON
    if os.path.exists(json_file):
        with open(json_file, "r", encoding="utf-8") as f:
            cur = json.load(f)
    else:
        cur = {}
    cur.setdefault("feature_flags", {}).update(flags)
    with open(json_file, "w", encoding="utf-8") as f:
        json.dump(cur, f, indent=2, ensure_ascii=False)
    print("✅ 更新feature flags (JSON):", cur["feature_flags"])
PY

# 3) 生成 ui/ 目录（若不存在）
if [ ! -d ui ]; then
  mkdir -p ui/src/components ui/src/proj ui/src/api ui/src/types ui/src/layers ui/src/panels ui/src/styles
  mkdir -p ui/public ui/tests ui/scripts
  echo "✅ 创建 ui/ 目录骨架"
else
  echo "ℹ️  ui/ 目录已存在，跳过创建"
fi

# 4) 创建基础package.json（如果不存在）
if [ ! -f ui/package.json ]; then
  cat > ui/package.json << 'EOF'
{
  "name": "ecdis-ui",
  "version": "1.0.0",
  "type": "module",
  "scripts": {
    "dev": "vite",
    "build": "tsc && vite build",
    "preview": "vite preview"
  },
  "dependencies": {
    "react": "^18.2.0",
    "react-dom": "^18.2.0"
  },
  "devDependencies": {
    "@types/react": "^18.2.0",
    "@types/react-dom": "^18.2.0",
    "@vitejs/plugin-react": "^4.0.0",
    "typescript": "^5.0.0",
    "vite": "^4.0.0"
  }
}
EOF
  echo "✅ 创建 ui/package.json"
fi

# 5) 创建基础vite配置
if [ ! -f ui/vite.config.ts ]; then
  cat > ui/vite.config.ts << 'EOF'
import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

export default defineConfig({
  plugins: [react()],
  base: '/ui/',
  build: {
    outDir: 'dist'
  },
  server: {
    port: 3000,
    proxy: {
      '/plan': 'http://localhost:8000',
      '/validate': 'http://localhost:8000',
      '/export': 'http://localhost:8000',
      '/enc': 'http://localhost:8000'
    }
  }
})
EOF
  echo "✅ 创建 ui/vite.config.ts"
fi

# 6) 创建基础tsconfig.json
if [ ! -f ui/tsconfig.json ]; then
  cat > ui/tsconfig.json << 'EOF'
{
  "compilerOptions": {
    "target": "ES2020",
    "lib": ["ES2020", "DOM", "DOM.Iterable"],
    "module": "ESNext",
    "skipLibCheck": true,
    "moduleResolution": "bundler",
    "allowImportingTsExtensions": true,
    "resolveJsonModule": true,
    "isolatedModules": true,
    "noEmit": true,
    "jsx": "react-jsx",
    "strict": true,
    "noUnusedLocals": false,
    "noUnusedParameters": false,
    "noFallthroughCasesInSwitch": true
  },
  "include": ["src"],
  "references": [{ "path": "./tsconfig.node.json" }]
}
EOF
  echo "✅ 创建 ui/tsconfig.json"
fi

# 7) 创建README
if [ ! -f ui/README.md ]; then
  cat > ui/README.md << 'EOF'
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
EOF
  echo "✅ 创建 ui/README.md"
fi

echo ""
echo "🎯 下一步行动："
echo "1. cd ui && npm install  # 安装依赖"
echo "2. 按YAML任务清单实现UI组件 (U1.1→U1.2→U2.1→U2.2→U2.3)"
echo "3. 启动后端: uvicorn service.app:app --port 8000"
echo "4. 启动UI: cd ui && npm run dev"
echo ""
echo "✅ 进入UI阶段：骨架与开关就绪。按任务清单推进。"