#!/bin/bash

# ECDIS 航线规划系统 - 一键启动测试脚本
# 作者: 资深航海算法工程师
# 日期: 2025-08-10

set -e

# 颜色定义
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
BLUE='\033[0;34m'
NC='\033[0m' # 无颜色

# 配置
API_URL="http://localhost:8000"
OUTPUT_DIR="测试结果"

echo -e "${BLUE}╔════════════════════════════════════════════════╗${NC}"
echo -e "${BLUE}║     ECDIS 航线规划系统 - 一键启动测试         ║${NC}"
echo -e "${BLUE}║     符合 IMO MSC.232(82) 标准                 ║${NC}"
echo -e "${BLUE}╚════════════════════════════════════════════════╝${NC}"
echo ""

# 1. 检查Python环境
echo -e "${YELLOW}[1/5]${NC} 检查系统环境..."
if ! command -v python &> /dev/null; then
    echo -e "  ${RED}✗${NC} Python 未安装"
    exit 1
fi
PYTHON_VERSION=$(python --version 2>&1 | grep -oE '[0-9]+\.[0-9]+')
echo -e "  ${GREEN}✓${NC} Python $PYTHON_VERSION 已安装"

# 检查必要的Python包
echo -n "  检查依赖包... "
MISSING_DEPS=""
for pkg in shapely numpy fastapi uvicorn; do
    if ! python -c "import $pkg" 2>/dev/null; then
        MISSING_DEPS="$MISSING_DEPS $pkg"
    fi
done

if [ -n "$MISSING_DEPS" ]; then
    echo -e "${RED}缺少依赖${NC}"
    echo -e "  ${YELLOW}请运行: pip install$MISSING_DEPS${NC}"
    exit 1
else
    echo -e "${GREEN}✓${NC}"
fi

# 2. 清理旧进程
echo -e "\n${YELLOW}[2/5]${NC} 清理系统..."
echo -n "  停止旧服务... "
lsof -ti:8000 2>/dev/null | xargs kill -9 2>/dev/null || true
sleep 1
echo -e "${GREEN}✓${NC}"

echo -n "  清理测试结果... "
rm -rf "$OUTPUT_DIR" 2>/dev/null || true
mkdir -p "$OUTPUT_DIR"
echo -e "${GREEN}✓${NC}"

# 3. 启动API服务
echo -e "\n${YELLOW}[3/5]${NC} 启动API服务..."
PYTHONPATH=. python service/app.py > "$OUTPUT_DIR/服务日志.txt" 2>&1 &
API_PID=$!
echo "  服务进程ID: $API_PID"

# 等待服务启动
echo -n "  等待服务就绪"
for i in {1..10}; do
    if curl -s "$API_URL/health" | grep -q "healthy" 2>/dev/null; then
        echo -e " ${GREEN}✓${NC}"
        break
    fi
    echo -n "."
    sleep 1
done

# 验证服务状态
if ! curl -s "$API_URL/health" | grep -q "healthy" 2>/dev/null; then
    echo -e " ${RED}✗${NC}"
    echo -e "  ${RED}服务启动失败，请检查日志: $OUTPUT_DIR/服务日志.txt${NC}"
    exit 1
fi

# 4. 执行测试
echo -e "\n${YELLOW}[4/5]${NC} 执行功能测试..."

# 4.1 航线规划测试
echo "  测试航线规划..."
echo "    起点: 37.80°N, 122.50°W (金门大桥外)"
echo "    终点: 37.82°N, 122.40°W (旧金山湾)"

START_TIME=$(date +%s%N)
PLAN_RESPONSE=$(curl -s -X POST "$API_URL/plan" \
  -H "Content-Type: application/json" \
  -d '{
    "start": {"lat": 37.80, "lon": -122.50},
    "goal": {"lat": 37.82, "lon": -122.40},
    "vessel_draft": 8.0,
    "safety_depth": 15.0,
    "under_keel_clearance": 3.0,
    "vessel_speed": 12.0
  }')
END_TIME=$(date +%s%N)
PLAN_TIME=$(echo "scale=3; ($END_TIME - $START_TIME) / 1000000000" | bc)

if echo "$PLAN_RESPONSE" | grep -q '"success":true'; then
    ROUTE_ID=$(echo "$PLAN_RESPONSE" | grep -o '"route_id":"[^"]*' | cut -d'"' -f4)
    DISTANCE=$(echo "$PLAN_RESPONSE" | grep -o '"total_distance_nm":[0-9.]*' | cut -d':' -f2)
    TIME=$(echo "$PLAN_RESPONSE" | grep -o '"estimated_time_hours":[0-9.]*' | cut -d':' -f2)
    WP_COUNT=$(echo "$PLAN_RESPONSE" | grep -o '"lat":' | wc -l)
    
    echo -e "    ${GREEN}✓${NC} 航线规划成功"
    echo "      • 航线ID: $ROUTE_ID"
    echo "      • 航程: ${DISTANCE} 海里"
    echo "      • 预计时间: ${TIME} 小时"
    echo "      • 航点数: $WP_COUNT"
    echo "      • 规划耗时: ${PLAN_TIME} 秒"
    
    # 检查性能要求
    if (( $(echo "$PLAN_TIME < 2" | bc -l) )); then
        echo -e "      • 性能: ${GREEN}✓${NC} 满足 <2秒 要求"
    else
        echo -e "      • 性能: ${YELLOW}⚠${NC} 超过2秒要求"
    fi
    
    # 保存航线
    echo "$PLAN_RESPONSE" > "$OUTPUT_DIR/航线_${ROUTE_ID}.json"
else
    echo -e "    ${RED}✗${NC} 航线规划失败"
    echo "$PLAN_RESPONSE" > "$OUTPUT_DIR/错误日志.txt"
    ROUTE_ID=""
fi

# 4.2 航线验证测试
if [ -n "$ROUTE_ID" ]; then
    echo ""
    echo "  测试航线验证..."
    
    VALIDATE_RESPONSE=$(curl -s -X POST "$API_URL/validate" \
      -H "Content-Type: application/json" \
      -d '{
        "route_id": "'"$ROUTE_ID"'",
        "checks": ["safety", "tss", "geometry", "speed"]
      }')
    
    if echo "$VALIDATE_RESPONSE" | grep -q '"success":true'; then
        IS_VALID=$(echo "$VALIDATE_RESPONSE" | grep -o '"is_valid":[^,]*' | cut -d':' -f2)
        TOTAL=$(echo "$VALIDATE_RESPONSE" | grep -o '"total_checks":[0-9]*' | cut -d':' -f2)
        PASSED=$(echo "$VALIDATE_RESPONSE" | grep -o '"passed":[0-9]*' | cut -d':' -f2)
        
        echo -e "    ${GREEN}✓${NC} 验证完成"
        echo "      • 通过检查: $PASSED/$TOTAL"
        
        if [ "$IS_VALID" = "true" ]; then
            echo -e "      • 航线状态: ${GREEN}✓${NC} 安全可行"
        else
            echo -e "      • 航线状态: ${YELLOW}⚠${NC} 存在问题"
        fi
        
        echo "$VALIDATE_RESPONSE" > "$OUTPUT_DIR/验证报告_${ROUTE_ID}.json"
    else
        echo -e "    ${RED}✗${NC} 验证失败"
    fi
fi

# 4.3 RTZ导出测试
if [ -n "$ROUTE_ID" ]; then
    echo ""
    echo "  测试RTZ导出..."
    
    RTZ_FILE="$OUTPUT_DIR/航线_${ROUTE_ID}.rtz"
    curl -s "$API_URL/export/rtz?route_id=$ROUTE_ID" -o "$RTZ_FILE"
    
    if [ -f "$RTZ_FILE" ] && grep -q "<route" "$RTZ_FILE"; then
        WP_IN_RTZ=$(grep -c "<waypoint" "$RTZ_FILE")
        echo -e "    ${GREEN}✓${NC} RTZ导出成功"
        echo "      • 文件: $RTZ_FILE"
        echo "      • 航点数: $WP_IN_RTZ"
    else
        echo -e "    ${RED}✗${NC} RTZ导出失败"
    fi
fi

# 5. 测试总结
echo -e "\n${YELLOW}[5/5]${NC} 测试总结"
echo -e "${BLUE}╔════════════════════════════════════════════════╗${NC}"
echo -e "${BLUE}║                 测试结果汇总                   ║${NC}"
echo -e "${BLUE}╠════════════════════════════════════════════════╣${NC}"

# 统计结果
TEST_PASSED=0
TEST_TOTAL=3

if [ -n "$ROUTE_ID" ]; then
    echo -e "${BLUE}║${NC} 航线规划:    ${GREEN}✓ 成功${NC}                          ${BLUE}║${NC}"
    TEST_PASSED=$((TEST_PASSED + 1))
else
    echo -e "${BLUE}║${NC} 航线规划:    ${RED}✗ 失败${NC}                          ${BLUE}║${NC}"
fi

if [ "$IS_VALID" = "true" ]; then
    echo -e "${BLUE}║${NC} 航线验证:    ${GREEN}✓ 通过${NC}                          ${BLUE}║${NC}"
    TEST_PASSED=$((TEST_PASSED + 1))
else
    echo -e "${BLUE}║${NC} 航线验证:    ${YELLOW}⚠ 部分通过${NC}                      ${BLUE}║${NC}"
fi

if [ -f "$RTZ_FILE" ]; then
    echo -e "${BLUE}║${NC} RTZ导出:     ${GREEN}✓ 成功${NC}                          ${BLUE}║${NC}"
    TEST_PASSED=$((TEST_PASSED + 1))
else
    echo -e "${BLUE}║${NC} RTZ导出:     ${RED}✗ 失败${NC}                          ${BLUE}║${NC}"
fi

echo -e "${BLUE}╠════════════════════════════════════════════════╣${NC}"
echo -e "${BLUE}║${NC} 总体结果:    ${TEST_PASSED}/${TEST_TOTAL} 测试通过                     ${BLUE}║${NC}"

if (( $(echo "$PLAN_TIME < 2" | bc -l) )); then
    echo -e "${BLUE}║${NC} 性能要求:    ${GREEN}✓ 满足${NC} (<2秒)                   ${BLUE}║${NC}"
else
    echo -e "${BLUE}║${NC} 性能要求:    ${YELLOW}⚠ 需优化${NC}                        ${BLUE}║${NC}"
fi

echo -e "${BLUE}╚════════════════════════════════════════════════╝${NC}"

echo ""
echo -e "${YELLOW}输出文件:${NC}"
echo "  • 测试结果目录: $OUTPUT_DIR/"
if [ -n "$ROUTE_ID" ]; then
    echo "  • 航线文件: $OUTPUT_DIR/航线_${ROUTE_ID}.json"
    echo "  • 验证报告: $OUTPUT_DIR/验证报告_${ROUTE_ID}.json"
    [ -f "$RTZ_FILE" ] && echo "  • RTZ文件: $RTZ_FILE"
fi
echo "  • 服务日志: $OUTPUT_DIR/服务日志.txt"

echo ""
echo -e "${GREEN}测试完成！${NC}"
echo ""
echo "提示："
echo "  • 服务仍在运行中，端口: 8000"
echo "  • 停止服务请运行: kill $API_PID"
echo "  • 查看API文档: http://localhost:8000/docs"
echo ""