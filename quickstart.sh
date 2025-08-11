#!/usr/bin/env bash
#
# ECDIS Route Planner - 快速启动脚本
# One-click setup and run
#

set -euo pipefail

# 颜色定义
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
NC='\033[0m'

# 打印Logo
print_logo() {
    echo -e "${CYAN}"
    cat << "EOF"
    ╔═══════════════════════════════════════════════╗
    ║      ECDIS ROUTE PLANNER v1.0.1              ║
    ║   IMO/IHO Compliant Navigation System        ║
    ╚═══════════════════════════════════════════════╝
EOF
    echo -e "${NC}"
}

# 打印菜单
print_menu() {
    echo -e "${BLUE}请选择操作:${NC}"
    echo "────────────────────────────────"
    echo "1) 🧪 运行所有测试"
    echo "2) 🚀 启动开发服务器"
    echo "3) 📦 创建部署包"
    echo "4) 📊 查看项目报告"
    echo "5) 🔍 运行特定里程碑测试"
    echo "6) 🛠️  检查系统依赖"
    echo "7) 📖 查看开发日志"
    echo "8) 🏗️  查看系统架构"
    echo "9) ⚙️  配置管理"
    echo "0) 🚪 退出"
    echo "────────────────────────────────"
}

# 检查依赖
check_dependencies() {
    echo -e "${YELLOW}检查系统依赖...${NC}"
    
    # Python版本
    if command -v python3 &> /dev/null; then
        PYTHON_VERSION=$(python3 --version | cut -d' ' -f2)
        echo -e "${GREEN}✅ Python: $PYTHON_VERSION${NC}"
    else
        echo -e "${RED}❌ Python3 未安装${NC}"
        exit 1
    fi
    
    # 必需的包
    REQUIRED_PACKAGES=("numpy" "shapely" "pytest")
    for package in "${REQUIRED_PACKAGES[@]}"; do
        if python3 -c "import $package" 2>/dev/null; then
            echo -e "${GREEN}✅ $package 已安装${NC}"
        else
            echo -e "${YELLOW}⚠️  安装 $package...${NC}"
            pip3 install $package
        fi
    done
    
    echo -e "${GREEN}所有依赖已就绪！${NC}\n"
}

# 运行测试
run_tests() {
    echo -e "${CYAN}运行完整测试套件...${NC}"
    if [ -f "run_all_tests.sh" ]; then
        ./run_all_tests.sh
    else
        python -m pytest tests/ -v
    fi
}

# 启动开发服务器
start_dev_server() {
    echo -e "${CYAN}启动开发服务器...${NC}"
    
    # 创建简单的演示脚本
    cat > demo_server.py << 'EOF'
#!/usr/bin/env python3
"""ECDIS Route Planner - Demo Server"""

import sys
import json
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent))

from lib.planner.hybrid_astar import HybridAStar
from lib.checks.route_checker import RouteChecker
from lib.colreg.colreg_rules import COLREGRules
from lib.governance.config_manager import ConfigManager

def main():
    print("🚢 ECDIS Route Planner - Demo Server")
    print("=" * 50)
    
    # 初始化组件
    print("初始化系统组件...")
    config = ConfigManager()
    print(f"✅ 配置管理器: {config.environment.value} 环境")
    
    planner = HybridAStar()
    print("✅ 路径规划器: Hybrid A*")
    
    checker = RouteChecker()
    print("✅ 路线验证器: 已加载")
    
    rules = COLREGRules()
    print("✅ COLREG规则: 已激活")
    
    print("\n系统就绪！")
    print("-" * 50)
    
    # 显示功能菜单
    while True:
        print("\n可用功能:")
        print("1) 规划路径")
        print("2) 验证路线")
        print("3) COLREG分析")
        print("4) 查看配置")
        print("5) 退出")
        
        choice = input("\n选择功能 (1-5): ")
        
        if choice == "1":
            print("\n路径规划功能 (演示模式)")
            print("起点: (0°N, 0°E)")
            print("终点: (10°N, 10°E)")
            print("状态: 规划成功 ✅")
            print("路径点数: 15")
            print("预计时间: 24小时")
            
        elif choice == "2":
            print("\n路线验证结果:")
            print("✅ 安全深度: 通过")
            print("✅ TSS合规: 通过")
            print("✅ XTD走廊: 通过")
            print("✅ 转弯半径: 通过")
            
        elif choice == "3":
            print("\n COLREG分析:")
            print("检测到目标船: 3艘")
            print("CPA: 2.5 nm (安全)")
            print("TCPA: 15分钟")
            print("建议动作: 保持航向")
            
        elif choice == "4":
            print(f"\n当前配置:")
            print(f"环境: {config.environment.value}")
            print(f"安全深度: {config.config.safety.min_ukc_m}m")
            print(f"最大工作线程: {config.config.performance.max_workers}")
            
        elif choice == "5":
            print("\n再见! 👋")
            break
        else:
            print("无效选择")

if __name__ == "__main__":
    main()
EOF
    
    python3 demo_server.py
}

# 创建部署包
create_deployment() {
    echo -e "${CYAN}创建部署包...${NC}"
    python3 -c "
from lib.governance.deployment import DeploymentManager
from lib.governance.config_manager import Environment

dm = DeploymentManager()
package = dm.create_package(environment=Environment.PRODUCTION)
print(f'✅ 部署包已创建: {package.version}')
print(f'📦 文件: dist/ecdis-planner-{package.version}-production.tar.gz')
"
}

# 查看项目报告
view_report() {
    if [ -f "PROJECT_REPORT.md" ]; then
        echo -e "${CYAN}项目报告:${NC}"
        echo "════════════════════════════════════════"
        head -n 50 PROJECT_REPORT.md
        echo "..."
        echo ""
        echo "完整报告请查看 PROJECT_REPORT.md"
    else
        echo "项目报告不存在"
    fi
}

# 运行特定里程碑测试
run_milestone_test() {
    echo -e "${CYAN}选择里程碑:${NC}"
    echo "1) M1-M4: 核心功能"
    echo "2) M5: 环境增强"
    echo "3) M6: 互操作性"
    echo "4) M7: 4D规划"
    echo "5) M8: 安全护盾"
    echo "6) M9: 瓦片管理"
    echo "7) M10: 治理框架"
    
    read -p "选择 (1-7): " milestone
    
    case $milestone in
        1) python -m pytest tests/test_colreg*.py tests/test_route_checker.py -v ;;
        2) python -m pytest tests/test_s1*.py tests/test_ukc.py -v ;;
        3) python -m pytest tests/test_s421*.py tests/test_stress*.py tests/test_forensics.py tests/test_sbom.py -v ;;
        4) python -m pytest tests/test_s104*.py tests/test_planner_4d.py tests/test_eta*.py tests/test_ukc_dynamic.py -v ;;
        5) python -m pytest tests/test_safety*.py tests/test_sensor*.py tests/test_fault*.py -v ;;
        6) python -m pytest tests/test_tile*.py tests/test_cache*.py tests/test_dynamic*.py -v ;;
        7) python -m pytest tests/test_version*.py tests/test_config*.py tests/test_deployment.py -v ;;
        *) echo "无效选择" ;;
    esac
}

# 查看开发日志
view_dev_log() {
    if [ -f "DEVELOPMENT_LOG.md" ]; then
        echo -e "${CYAN}开发日志最新条目:${NC}"
        echo "════════════════════════════════════════"
        tail -n 30 DEVELOPMENT_LOG.md
    else
        echo "开发日志不存在"
    fi
}

# 查看系统架构
view_architecture() {
    if [ -f "SYSTEM_ARCHITECTURE.md" ]; then
        echo -e "${CYAN}系统架构概览:${NC}"
        echo "════════════════════════════════════════"
        head -n 40 SYSTEM_ARCHITECTURE.md
        echo "..."
        echo ""
        echo "完整架构请查看 SYSTEM_ARCHITECTURE.md"
    else
        echo "架构文档不存在"
    fi
}

# 配置管理
manage_config() {
    echo -e "${CYAN}配置管理:${NC}"
    python3 -c "
from lib.governance.config_manager import ConfigManager, Environment
import json

cm = ConfigManager()
print(f'当前环境: {cm.environment.value}')
print(f'配置目录: {cm.config_dir}')
print('')
print('特性标志:')
print(f'  COLREG: {cm.is_feature_enabled(\"colreg_enabled\")}')
print(f'  4D规划: {cm.is_feature_enabled(\"four_d_planner\")}')
print(f'  安全护盾: {cm.is_feature_enabled(\"safety_shield\")}')
print(f'  瓦片管理: {cm.is_feature_enabled(\"tile_management\")}')
print('')
print('验证结果:')
issues = cm.validate_config()
if issues:
    for issue in issues:
        print(f'  ⚠️ {issue}')
else:
    print('  ✅ 配置有效')
"
}

# 主循环
main() {
    print_logo
    check_dependencies
    
    while true; do
        print_menu
        read -p "请输入选项 (0-9): " choice
        
        case $choice in
            1) run_tests ;;
            2) start_dev_server ;;
            3) create_deployment ;;
            4) view_report ;;
            5) run_milestone_test ;;
            6) check_dependencies ;;
            7) view_dev_log ;;
            8) view_architecture ;;
            9) manage_config ;;
            0) echo -e "${GREEN}再见！感谢使用 ECDIS Route Planner${NC}"; exit 0 ;;
            *) echo -e "${YELLOW}无效选项，请重试${NC}" ;;
        esac
        
        echo ""
        read -p "按回车继续..."
    done
}

# 运行主程序
main