#!/bin/bash
# Cleanup script for removing redundant test files and logs
# Date: 2025-08-19

echo "=== Maritime Route Planning System - Cleanup Script ==="
echo "Removing redundant test files and logs..."

# Remove redundant test files (keeping only the final comprehensive test)
TEST_FILES=(
    "test_actual_route.py"
    "test_and_visualize_route.py"
    "test_final_route.py"
    "test_quick_select_routes.py"
    "test_route_safety.py"
    "verify_fixed_routes.py"
    "verify_integration.py"
    "check_shanghai_route.py"
    "check_singapore_route.py"
    "check_shipping_routes.py"
    "debug_shenzhen_singapore.py"
    "final_shenzhen_singapore_test.py"
    "analyze_route_problems.py"
    "comprehensive_test.py"
    "debug_route_matching.py"
    "debug_api_flow.py"
    "direct_function_test.py"
    "add_debug_logging.py"
    "final_integration_test.py"
    "test_historical_routes.py"
)

for file in "${TEST_FILES[@]}"; do
    if [ -f "$file" ]; then
        echo "Removing $file"
        rm "$file"
    fi
done

# Remove old log files
LOG_FILES=(
    "service_restart.log"
    "service_restart2.log"
    "frontend.log"
    "service.log"
)

for file in "${LOG_FILES[@]}"; do
    if [ -f "$file" ]; then
        echo "Removing $file"
        rm "$file"
    fi
done

# Remove temporary test data files
if [ -f "test.s421" ]; then
    echo "Removing test.s421"
    rm "test.s421"
fi

if [ -f "test_dynamic_route.py" ]; then
    echo "Removing test_dynamic_route.py"
    rm "test_dynamic_route.py"
fi

# Clean up outdated documentation (will be consolidated)
OLD_DOCS=(
    "AIS_COLREG_INTEGRATION.md"
    "AIS_MODULE_LOG.md"
    "REFACTOR_SUMMARY.md"
    "ROLLBACK_GUIDE.md"
)

for file in "${OLD_DOCS[@]}"; do
    if [ -f "$file" ]; then
        echo "Removing $file"
        rm "$file"
    fi
done

# Remove old route JSON files
if [ -f "route_SGSIN_AEJEA_20250811_162637.json" ]; then
    echo "Removing old route JSON file"
    rm "route_SGSIN_AEJEA_20250811_162637.json"
fi

echo ""
echo "=== Cleanup Complete ==="
echo "Kept files:"
echo "  - final_comprehensive_test.py (main test suite)"
echo "  - final_test.sh (integration test script)"
echo "  - start_integrated.sh (system startup script)"
echo "  - Core documentation (README.md, CHANGELOG.md, etc.)"
echo ""
echo "Next steps:"
echo "1. Review COST_CALCULATION_DOCUMENTATION.md for cost model details"
echo "2. Check consolidated TECHNICAL_DOCUMENTATION.md"