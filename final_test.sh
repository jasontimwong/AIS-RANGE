#!/bin/bash

# ECDIS System Complete Test Script
# Verify all core functions are working properly

set -e

echo "================================================"
echo "       ECDIS System Complete Function Test"
echo "================================================"

# Color definitions
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

# Test counters
PASSED=0
FAILED=0

# Test function
test_feature() {
    local name=$1
    local cmd=$2
    echo -n "Testing: $name ... "
    
    if eval $cmd > /dev/null 2>&1; then
        echo -e "${GREEN}✅ Passed${NC}"
        ((PASSED++))
    else
        echo -e "${RED}❌ Failed${NC}"
        ((FAILED++))
    fi
}

echo ""
echo "1. Check Service Status"
echo "----------------------------------------"

# Check backend
test_feature "Backend Service" "curl -s http://localhost:8000/status | grep operational"

# Check frontend
test_feature "Frontend Service" "curl -s http://localhost:3001/ui/ | grep ECDIS"

echo ""
echo "2. Test Route Planning Function"
echo "----------------------------------------"

# Short distance planning
test_feature "Short Distance Route Planning" "curl -s -X POST http://localhost:8000/api/route/plan_full \
    -H 'Content-Type: application/json' \
    -d '{\"start\":{\"lat\":31.23,\"lon\":121.508},\"goal\":{\"lat\":22.3,\"lon\":114.2}}' \
    | grep coords"

# Long distance planning
test_feature "Long Distance Route Planning" "curl -s -X POST http://localhost:8000/api/route/plan_full \
    -H 'Content-Type: application/json' \
    -d '{\"start\":{\"lat\":31.23,\"lon\":121.508},\"goal\":{\"lat\":1.27,\"lon\":103.85}}' \
    | grep coords"

echo ""
echo "3. Test AIS System"
echo "----------------------------------------"

# AIS scenario switching
test_feature "AIS Default Scenario" "curl -s -X POST http://localhost:8000/api/ais/scenario \
    -H 'Content-Type: application/json' \
    -d '{\"scenario\":\"default\"}' | grep ok"

test_feature "AIS Strong Attack Scenario" "curl -s -X POST http://localhost:8000/api/ais/scenario \
    -H 'Content-Type: application/json' \
    -d '{\"scenario\":\"aggressive\"}' | grep aggressive"

echo ""
echo "4. Test Dynamic Collision Avoidance"
echo "----------------------------------------"

# Initialize dynamic route
test_feature "Dynamic Route Initialization" "curl -s -X POST http://localhost:8000/api/route/initialize \
    -H 'Content-Type: application/json' \
    -d '{\"waypoints\":[{\"lat\":31.23,\"lon\":121.508},{\"lat\":1.27,\"lon\":103.85}]}' \
    | grep status"

# Get dynamic route
test_feature "Dynamic Route Retrieval" "curl -s 'http://localhost:8000/api/route/dynamic?current_lat=31.23&current_lon=121.508' \
    | grep route_comparison"

echo ""
echo "5. Test Data Loading"
echo "----------------------------------------"

# ENC data
test_feature "ENC Data Loading" "curl -s http://localhost:8000/enc/lite | grep -E '(coast|coastline)'"

echo ""
echo "================================================"
echo "                Test Report"
echo "================================================"
echo -e "${GREEN}✅ Passed: $PASSED${NC}"
echo -e "${RED}❌ Failed: $FAILED${NC}"

TOTAL=$((PASSED + FAILED))
if [ $TOTAL -gt 0 ]; then
    RATE=$((PASSED * 100 / TOTAL))
    echo "Pass Rate: ${RATE}%"
    
    if [ $RATE -ge 80 ]; then
        echo -e "\n${GREEN}✅ System Functions Basically Normal${NC}"
        echo "You can access the system at the following addresses:"
        echo "  - Frontend Interface: http://localhost:3001/ui/"
        echo "  - API Documentation: http://localhost:8000/docs"
    elif [ $RATE -ge 60 ]; then
        echo -e "\n${YELLOW}⚠️ System has some issues but is basically usable${NC}"
    else
        echo -e "\n${RED}❌ System has serious issues, needs to be fixed${NC}"
    fi
fi

echo ""
echo "Test Completion Time: $(date '+%Y-%m-%d %H:%M:%S')"
echo "================================================"

exit $([ $FAILED -eq 0 ] && echo 0 || echo 1)