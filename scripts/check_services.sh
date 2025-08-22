#!/bin/bash
# 服务状态检查脚本

echo "======================================"
echo "        系统服务状态检查"
echo "======================================"

# 检查后端服务
echo -n "后端服务 (8000端口): "
if curl -s http://localhost:8000/status >/dev/null 2>&1; then
    echo "✅ 运行中"
    STATUS=$(curl -s http://localhost:8000/status)
    echo "  状态详情: $STATUS"
else
    echo "❌ 未运行"
fi

# 检查前端服务
echo -n "前端服务 (3001端口): "
if curl -s http://localhost:3001/ui/ >/dev/null 2>&1; then
    echo "✅ 运行中"
else
    echo "❌ 未运行"
fi

# 检查路径规划API
echo -n "路径规划API: "
if curl -s -X POST http://localhost:8000/api/route/plan_full \
    -H "Content-Type: application/json" \
    -d '{"start":{"lat":31.23,"lon":121.508},"goal":{"lat":31.0,"lon":122.0}}' \
    | grep -q "coords" 2>/dev/null; then
    echo "✅ 正常"
else
    echo "⚠️  需要初始化"
fi

echo ""
echo "访问地址:"
echo "  前端: http://localhost:3001/ui/"
echo "  API文档: http://localhost:8000/docs"
echo "======================================"
