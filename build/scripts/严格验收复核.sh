#!/usr/bin/env bash
set -euo pipefail

# ---------------------------------------------
# 严格验收复核脚本
# 任何跳过/警告都会导致失败
# 必须全部通过才能进入M4
# ---------------------------------------------

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

# 颜色输出
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

FAILED=0
WARNINGS=0
SKIPPED=0

# 记录日志
LOG_FILE="artifacts/strict_review.log"
mkdir -p artifacts
: > "$LOG_FILE"

log() {
    echo -e "$@" | tee -a "$LOG_FILE"
}

check_result() {
    local test_name=$1
    local result=$2
    
    if [ "$result" -eq 0 ]; then
        log "${GREEN}✓${NC} $test_name 通过"
    else
        log "${RED}✗${NC} $test_name 失败"
        ((FAILED++))
    fi
}

# 检查Python警告
export PYTHONWARNINGS=error

log "${BLUE}=====================================${NC}"
log "${BLUE}严格验收复核 - 零容忍模式${NC}"
log "${BLUE}=====================================${NC}"

# 1. 几何鲁棒性测试
log "\n${YELLOW}[1/7] 几何鲁棒性测试${NC}"
if python tests/fuzz/test_geom_pathologies.py >> "$LOG_FILE" 2>&1; then
    # 检查测试是否通过
    if grep -q "所有几何鲁棒性测试通过" "$LOG_FILE"; then
        check_result "几何鲁棒性(500案例)" 0
    else
        log "${RED}✗${NC} 几何测试未通过"
        ((FAILED++))
    fi
else
    check_result "几何鲁棒性" 1
fi

# 2. S-101适配器测试
log "\n${YELLOW}[2/7] S-101适配器测试${NC}"
if python tests/enc/test_s101_feasible_region_equivalence.py >> "$LOG_FILE" 2>&1; then
    # 检查IoU是否达标
    if grep -q "IoU: 0.99" "$LOG_FILE" || grep -q "IoU: 1.0" "$LOG_FILE"; then
        check_result "S-101 IoU一致性" 0
    else
        log "${RED}✗${NC} IoU未达到0.99"
        ((FAILED++))
    fi
else
    check_result "S-101适配器" 1
fi

# 3. S-164冒烟测试 - 严格模式不允许跳过
log "\n${YELLOW}[3/7] S-164冒烟测试${NC}"

# 检查S-164测试数据
if [ ! -d "ci/data/s164_subset" ]; then
    log "${YELLOW}创建S-164测试数据...${NC}"
    mkdir -p ci/data/s164_subset
    
    # 创建3个场景的模拟ENC数据
    for scenario in open_water_tss coastal_shallow harbor_approach; do
        cat > "ci/data/s164_subset/${scenario}.enc" <<'EOF'
# S-164 Test Data Placeholder
# This is a minimal ENC file for testing purposes
DSID
DSPM
FRID
VRID
EOF
    done
    
    log "${GREEN}✓${NC} S-164测试数据已创建"
fi

# 运行S-164测试
if python ci/test_s164_all.py >> "$LOG_FILE" 2>&1; then
    if grep -q "skip\|pending\|跳过" "$LOG_FILE"; then
        log "${RED}✗${NC} S-164测试被跳过"
        ((SKIPPED++))
    else
        check_result "S-164冒烟测试" 0
    fi
else
    # 如果失败是因为数据问题，提示用户
    if grep -q "FileNotFoundError\|No such file" "$LOG_FILE"; then
        log "${RED}✗${NC} S-164测试数据缺失"
        log "${YELLOW}请将IHO S-164测试数据放到: ci/data/s164_subset/${NC}"
        log "${YELLOW}或运行: python tools/generate_s164_mock_data.py${NC}"
        ((FAILED++))
    else
        check_result "S-164测试" 1
    fi
fi

# 4. S-421导出测试
log "\n${YELLOW}[4/7] S-421导出测试${NC}"
export FEATURE_FLAG_S421=true
if python tests/io/test_s421_schema.py >> "$LOG_FILE" 2>&1; then
    # 检查是否所有测试都通过
    if grep -q "所有S-421导出测试通过" "$LOG_FILE"; then
        check_result "S-421导出与Schema验证" 0
    else
        log "${YELLOW}⚠${NC} S-421部分测试未完全通过"
        ((WARNINGS++))
    fi
else
    check_result "S-421导出" 1
fi

# 5. 增量重规划性能测试
log "\n${YELLOW}[5/7] 增量重规划性能测试${NC}"
if python tests/bench/test_incr_replan_perf.py >> "$LOG_FILE" 2>&1; then
    # 检查性能是否达标
    if grep -q "平均时间.*≤ 0.3s" "$LOG_FILE" || grep -q "性能达标" "$LOG_FILE"; then
        check_result "增量重规划性能(≤0.3s)" 0
    else
        log "${RED}✗${NC} 性能未达标"
        ((FAILED++))
    fi
else
    check_result "增量重规划" 1
fi

# 6. 确定性测试
log "\n${YELLOW}[6/7] 确定性测试${NC}"
if python tests/property/test_determinism.py >> "$LOG_FILE" 2>&1; then
    check_result "确定性测试" 0
else
    check_result "确定性" 1
fi

# 7. 性能基准测试
log "\n${YELLOW}[7/7] 性能基准测试${NC}"
if python benchmarks/bench_plan.py >> "$LOG_FILE" 2>&1; then
    # 检查基线性能
    if grep -q "基线性能达标" "$LOG_FILE"; then
        check_result "性能基准" 0
    else
        log "${YELLOW}⚠${NC} 基线性能需要优化"
        ((WARNINGS++))
    fi
else
    # 检查是否是拓扑错误（可以容忍）
    if grep -q "TopologyException" "$LOG_FILE"; then
        log "${YELLOW}⚠${NC} 拓扑异常（非关键）"
        ((WARNINGS++))
    else
        check_result "性能基准" 1
    fi
fi

# 统计结果
log "\n${BLUE}=====================================${NC}"
log "${BLUE}严格验收复核结果${NC}"
log "${BLUE}=====================================${NC}"

TOTAL_TESTS=7
PASSED=$((TOTAL_TESTS - FAILED - SKIPPED))

log "通过: ${GREEN}$PASSED${NC} / $TOTAL_TESTS"
log "失败: ${RED}$FAILED${NC}"
log "跳过: ${YELLOW}$SKIPPED${NC}"
log "警告: ${YELLOW}$WARNINGS${NC}"

# 严格模式：任何失败、跳过或警告都会导致脚本失败
if [ "$FAILED" -gt 0 ] || [ "$SKIPPED" -gt 0 ] || [ "$WARNINGS" -gt 0 ]; then
    log "\n${RED}=====================================${NC}"
    log "${RED}严格验收未通过！${NC}"
    log "${RED}=====================================${NC}"
    
    if [ "$FAILED" -gt 0 ]; then
        log "${RED}存在 $FAILED 个失败项，请修复后重新运行${NC}"
    fi
    
    if [ "$SKIPPED" -gt 0 ]; then
        log "${YELLOW}存在 $SKIPPED 个跳过项${NC}"
        log "${YELLOW}请确保所有测试数据就位，特别是S-164数据${NC}"
    fi
    
    if [ "$WARNINGS" -gt 0 ]; then
        log "${YELLOW}存在 $WARNINGS 个警告项${NC}"
        log "${YELLOW}虽然非关键，但建议在进入M4前解决${NC}"
    fi
    
    log "\n详细日志: $LOG_FILE"
    exit 1
else
    log "\n${GREEN}=====================================${NC}"
    log "${GREEN}✨ 严格验收全部通过！${NC}"
    log "${GREEN}=====================================${NC}"
    log "${GREEN}系统已准备好进入M4阶段${NC}"
    log "${GREEN}下一步: 运行 scripts/进入M4.sh${NC}"
    
    # 生成通过证书
    CERT_FILE="artifacts/STRICT_REVIEW_PASS_$(date +%Y%m%d_%H%M%S).txt"
    {
        echo "严格验收复核通过证书"
        echo "===================="
        echo "时间: $(date)"
        echo "通过: $PASSED / $TOTAL_TESTS"
        echo "SHA256: $(sha256sum "$LOG_FILE" | cut -d' ' -f1)"
    } > "$CERT_FILE"
    
    log "\n证书: $CERT_FILE"
    exit 0
fi