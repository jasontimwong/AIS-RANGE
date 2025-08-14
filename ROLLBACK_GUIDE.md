# 回退指南 - Port Configuration Update

## 当前版本信息
- **分支**: feature/dynamic-route-v2
- **版本**: v3.3.2
- **更新时间**: 2025-08-14
- **回退标签**: v3.3.2-before-port-update

## 端口配置变更

### 前端 (Vite)
- **原端口**: 3000
- **新端口**: 3001
- **配置文件**: `ui/vite.config.ts`

### 后端 (FastAPI)
- **原端口**: 8000
- **新端口**: 8001
- **配置文件**: `service/app.py`

## 变更内容

### 1. 前端配置 (`ui/vite.config.ts`)
```javascript
// 变更前
server: {
  port: 3000,
  proxy: {
    '/api/*': 'http://localhost:8000'
  }
}

// 变更后
server: {
  port: 3001,
  proxy: {
    '/api/*': 'http://localhost:8001'
  }
}
```

### 2. 后端CORS配置 (`service/app.py`)
```python
# 变更前
allow_origins=["http://localhost:3001", "http://127.0.0.1:3001"]

# 变更后 (兼容新旧端口)
allow_origins=["http://localhost:3001", "http://127.0.0.1:3001", "http://localhost:3000"]
```

### 3. 后端默认端口 (`service/app.py`)
```python
# 变更前
uvicorn.run(app, host="0.0.0.0", port=8000)

# 变更后
port = int(os.environ.get("PORT", 8001))
uvicorn.run(app, host="0.0.0.0", port=port)
```

## 回退步骤

### 方法1: 使用Git标签回退（推荐）
```bash
# 查看当前状态
git status

# 保存当前工作（如有未提交的更改）
git stash

# 回退到标签版本
git reset --hard v3.3.2-before-port-update

# 如需恢复stash的内容
git stash pop
```

### 方法2: 手动回退配置

#### 2.1 回退前端配置
编辑 `ui/vite.config.ts`:
```javascript
server: {
  port: 3000,  // 改回3000
  proxy: {
    // 将所有 http://localhost:8001 改回 http://localhost:8000
  }
}
```

#### 2.2 回退后端配置
编辑 `service/app.py`:
```python
# 第1430行附近
port = int(os.environ.get("PORT", 8000))  # 改回8000
```

#### 2.3 回退CORS配置（可选）
如果需要严格回退：
```python
# 第78行附近
allow_origins=["http://localhost:3001", "http://127.0.0.1:3001"]  # 移除3000
```

## 启动服务

### 新配置启动方式
```bash
# 后端 (端口8001)
cd service
python app.py

# 前端 (端口3001)
cd ui
npm run dev
```

### 回退后启动方式
```bash
# 后端 (端口8000)
cd service
PORT=8000 python app.py

# 前端 (端口3000)
cd ui
npm run dev
```

## 验证步骤

1. **检查后端服务**:
   ```bash
   curl http://localhost:8001/status  # 新配置
   curl http://localhost:8000/status  # 旧配置
   ```

2. **检查前端服务**:
   - 新配置: 访问 http://localhost:3001
   - 旧配置: 访问 http://localhost:3000

3. **检查WebSocket连接**:
   - 打开浏览器开发者工具
   - 查看Network标签中的WS连接
   - 确认连接到正确的后端端口

## 常见问题

### Q1: 端口已被占用
```bash
# 查找占用端口的进程
lsof -i :8000  # 或 8001
lsof -i :3000  # 或 3001

# 终止进程
kill -9 <PID>
```

### Q2: 前后端连接失败
- 检查防火墙设置
- 确认CORS配置正确
- 验证代理配置匹配

### Q3: 回退后测试数据无法加载
测试数据端点已配置，确保：
- 后端服务运行在正确端口
- `/api/test/*` 路径在代理配置中

## 紧急回退命令

如果需要立即回退所有更改：
```bash
# 一键回退到标签版本
git reset --hard v3.3.2-before-port-update

# 重启服务
pkill -f "python.*app.py"
cd service && PORT=8000 python app.py &
cd ../ui && npm run dev
```

## 联系支持

如遇到问题，请参考：
- Git历史: `git log --oneline -10`
- 标签列表: `git tag -l`
- 服务日志: `/tmp/planner_service*.log`

---
*文档创建: 2025-08-14*  
*最后更新: 2025-08-14*