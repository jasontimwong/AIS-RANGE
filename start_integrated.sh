#!/usr/bin/env bash
#
# ECDIS 集成系统启动脚本
# 整合核心规划功能到前端的统一启动器
#

set -euo pipefail

# 颜色定义
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
NC='\033[0m'

# 进程ID跟踪
BACKEND_PID=""
FRONTEND_PID=""

# 清理函数
cleanup() {
    echo -e "\n${YELLOW}正在停止所有服务...${NC}"
    
    if [ ! -z "$BACKEND_PID" ]; then
        kill $BACKEND_PID 2>/dev/null || true
        echo -e "${GREEN}✅ 后端服务已停止${NC}"
    fi
    
    if [ ! -z "$FRONTEND_PID" ]; then
        kill $FRONTEND_PID 2>/dev/null || true
        echo -e "${GREEN}✅ 前端服务已停止${NC}"
    fi
    
    # 清理可能的遗留进程
    pkill -f "python.*service/app.py" 2>/dev/null || true
    pkill -f "npm.*dev" 2>/dev/null || true
    
    exit 0
}

# 捕获退出信号
trap cleanup INT TERM EXIT

# Logo
print_logo() {
    echo -e "${CYAN}"
    cat << "EOF"
╔═══════════════════════════════════════════════════════╗
║        ECDIS 集成规划系统 v3.3.0                      ║
║     核心规划功能 + 动态避碰 + 前端集成                ║
╚═══════════════════════════════════════════════════════╝
EOF
    echo -e "${NC}"
}

# 检查依赖
check_dependencies() {
    echo -e "${YELLOW}🔍 检查系统依赖...${NC}"
    
    # Python检查
    if ! command -v python3 &> /dev/null; then
        echo -e "${RED}❌ Python3未安装${NC}"
        exit 1
    fi
    
    # Node.js检查
    if ! command -v node &> /dev/null; then
        echo -e "${RED}❌ Node.js未安装（前端需要）${NC}"
        exit 1
    fi
    
    # 检查Python包
    REQUIRED_PACKAGES=("numpy" "shapely" "fastapi" "uvicorn")
    for package in "${REQUIRED_PACKAGES[@]}"; do
        if ! python3 -c "import $package" 2>/dev/null; then
            echo -e "${YELLOW}安装 $package...${NC}"
            pip3 install $package
        fi
    done
    
    echo -e "${GREEN}✅ 依赖检查完成${NC}\n"
}

# 清理旧进程
cleanup_old_processes() {
    echo -e "${YELLOW}🧹 清理旧进程...${NC}"
    
    # 查找并停止旧的后端进程
    OLD_BACKEND_PIDS=$(lsof -ti:8000,8001 2>/dev/null || true)
    if [ ! -z "$OLD_BACKEND_PIDS" ]; then
        echo "停止端口8000/8001上的旧进程..."
        echo $OLD_BACKEND_PIDS | xargs kill 2>/dev/null || true
        sleep 2
    fi
    
    # 查找并停止旧的前端进程
    OLD_FRONTEND_PIDS=$(lsof -ti:3000,3001 2>/dev/null || true)
    if [ ! -z "$OLD_FRONTEND_PIDS" ]; then
        echo "停止端口3000/3001上的旧进程..."
        echo $OLD_FRONTEND_PIDS | xargs kill 2>/dev/null || true
        sleep 2
    fi
    
    echo -e "${GREEN}✅ 清理完成${NC}\n"
}

# 启动后端服务
start_backend() {
    echo -e "${CYAN}🚀 启动后端服务（端口8000）...${NC}"
    
    # 创建日志文件
    BACKEND_LOG="/tmp/backend_integrated.log"
    
    # 启动后端，使用nohup确保稳定运行
    nohup python3 service/app.py > $BACKEND_LOG 2>&1 &
    BACKEND_PID=$!
    
    echo "后端进程PID: $BACKEND_PID"
    echo "日志文件: $BACKEND_LOG"
    
    # 等待后端启动
    echo -n "等待后端启动"
    for i in {1..10}; do
        if curl -s http://localhost:8000/status >/dev/null 2>&1; then
            echo -e "\n${GREEN}✅ 后端服务已启动${NC}"
            
            # 验证核心端点
            echo -e "${YELLOW}验证核心端点...${NC}"
            
            # 检查plan_full端点
            if curl -s -X POST http://localhost:8000/api/route/plan_full \
                -H "Content-Type: application/json" \
                -d '{"start":{"lat":31.23,"lon":121.508},"goal":{"lat":1.27,"lon":103.85}}' \
                | grep -q "coords"; then
                echo -e "${GREEN}✅ /api/route/plan_full 端点正常${NC}"
            else
                echo -e "${YELLOW}⚠️  /api/route/plan_full 可能需要初始化${NC}"
            fi
            
            # 检查动态路径端点
            if curl -s "http://localhost:8000/api/route/dynamic?current_lat=31.23&current_lon=121.508" \
                | grep -q "route_comparison"; then
                echo -e "${GREEN}✅ /api/route/dynamic 端点正常${NC}"
            else
                echo -e "${YELLOW}⚠️  /api/route/dynamic 需要初始化${NC}"
            fi
            
            return 0
        fi
        echo -n "."
        sleep 2
    done
    
    echo -e "\n${RED}❌ 后端启动失败，查看日志: $BACKEND_LOG${NC}"
    tail -20 $BACKEND_LOG
    return 1
}

# 启动前端服务
start_frontend() {
    echo -e "\n${CYAN}🎨 启动前端服务（端口3000）...${NC}"
    
    # 进入UI目录
    cd ui
    
    # 检查npm依赖
    if [ ! -d "node_modules" ]; then
        echo "安装前端依赖..."
        npm install
    fi
    
    # 创建日志文件
    FRONTEND_LOG="/tmp/frontend_integrated.log"
    
    # 启动前端
    nohup npm run dev > $FRONTEND_LOG 2>&1 &
    FRONTEND_PID=$!
    
    echo "前端进程PID: $FRONTEND_PID"
    echo "日志文件: $FRONTEND_LOG"
    
    # 返回主目录
    cd ..
    
    # 等待前端启动
    echo -n "等待前端启动"
    for i in {1..10}; do
        if curl -s http://localhost:3000/ui/ >/dev/null 2>&1; then
            echo -e "\n${GREEN}✅ 前端服务已启动${NC}"
            return 0
        fi
        echo -n "."
        sleep 2
    done
    
    echo -e "\n${YELLOW}⚠️  前端可能需要更多时间启动${NC}"
}

# 显示功能菜单
show_features() {
    echo -e "\n${BLUE}═══ 集成功能列表 ═══${NC}"
    echo "────────────────────────────────────────"
    
    echo -e "${GREEN}✅ 已集成的核心功能:${NC}"
    echo "  • 混合A*路径规划（50m精度）"
    echo "  • 动态避碰系统（实时AIS）"
    echo "  • 全局重规划（/api/route/plan_full）"
    echo "  • 航线对比评估"
    echo "  • 油耗估算"
    echo "  • RTZ导入导出"
    
    echo -e "\n${CYAN}🎯 前端交互功能:${NC}"
    echo "  • 自由选择起点终点"
    echo "  • 实时路径展示"
    echo "  • 动态更新（5秒轮询）"
    echo "  • 双路径对比显示"
    echo "  • AIS目标可视化"
    echo "  • 评估面板"
    
    echo -e "\n${YELLOW}⚙️  系统配置:${NC}"
    echo "  • 后端: http://localhost:8000"
    echo "  • 前端: http://localhost:3000/ui/"
    echo "  • API文档: http://localhost:8000/docs"
    echo "  • WebSocket: ws://localhost:8000/ws/ais"
}

# 系统健康检查
health_check() {
    echo -e "\n${CYAN}🏥 系统健康检查...${NC}"
    echo "────────────────────────────────────────"
    
    # 检查后端
    if curl -s http://localhost:8000/status >/dev/null 2>&1; then
        echo -e "后端服务: ${GREEN}✅ 运行中${NC}"
    else
        echo -e "后端服务: ${RED}❌ 未响应${NC}"
    fi
    
    # 检查前端
    if curl -s http://localhost:3000/ui/ >/dev/null 2>&1; then
        echo -e "前端服务: ${GREEN}✅ 运行中${NC}"
    else
        echo -e "前端服务: ${YELLOW}⚠️  启动中${NC}"
    fi
    
    # 检查WebSocket
    if curl -s http://localhost:8000/ws/ais 2>&1 | grep -q "Upgrade"; then
        echo -e "WebSocket: ${GREEN}✅ 可用${NC}"
    else
        echo -e "WebSocket: ${YELLOW}⚠️  待初始化${NC}"
    fi
    
    # 检查核心规划功能
    echo -e "\n${BLUE}核心功能状态:${NC}"
    
    # 测试规划功能
    TEST_RESULT=$(curl -s -X POST http://localhost:8000/api/route/plan_full \
        -H "Content-Type: application/json" \
        -d '{"start":{"lat":31.23,"lon":121.508},"goal":{"lat":31.0,"lon":122.0}}' 2>&1)
    
    if echo "$TEST_RESULT" | grep -q "coords"; then
        echo -e "路径规划: ${GREEN}✅ 正常${NC}"
    else
        echo -e "路径规划: ${YELLOW}⚠️  需要初始化可行域${NC}"
    fi
}

# 主程序
main() {
    print_logo
    
    # 步骤1: 检查依赖
    check_dependencies
    
    # 步骤2: 清理旧进程
    cleanup_old_processes
    
    # 步骤3: 启动后端
    if ! start_backend; then
        echo -e "${RED}后端启动失败，退出${NC}"
        exit 1
    fi
    
    # 步骤4: 启动前端
    start_frontend
    
    # 步骤5: 显示功能列表
    show_features
    
    # 步骤6: 健康检查
    sleep 3
    health_check
    
    # 显示访问信息
    echo -e "\n${GREEN}════════════════════════════════════════${NC}"
    echo -e "${GREEN}✅ 系统已完全启动！${NC}"
    echo -e "${GREEN}════════════════════════════════════════${NC}"
    echo ""
    echo -e "${BLUE}访问地址:${NC}"
    echo -e "  🌐 前端界面: ${CYAN}http://localhost:3000/ui/${NC}"
    echo -e "  📊 API文档: ${CYAN}http://localhost:8000/docs${NC}"
    echo -e "  🔍 健康检查: ${CYAN}http://localhost:8000/status${NC}"
    echo ""
    echo -e "${YELLOW}使用说明:${NC}"
    echo -e "  1. 打开前端界面"
    echo -e "  2. 启用'动态路径规划'开关"
    echo -e "  3. 点击'重规划(全局)'按钮进行完整规划"
    echo -e "  4. 查看双路径对比和评估面板"
    echo ""
    echo -e "${YELLOW}按 Ctrl+C 停止所有服务${NC}"
    
    # 保持运行
    while true; do
        sleep 1
    done
}

# 运行主程序
main