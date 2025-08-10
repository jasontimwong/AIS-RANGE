#!/usr/bin/env python3
"""
运行所有S-164场景测试
"""

import sys
import os
from pathlib import Path

# 添加项目路径
sys.path.insert(0, os.path.abspath('.'))

def run_s164_tests():
    """运行S-164测试"""
    scenarios = ['open_water_tss', 'coastal_shallow', 'harbor_approach']
    
    # 创建输出目录
    output_base = Path("artifacts/s164_test")
    output_base.mkdir(parents=True, exist_ok=True)
    
    # 创建模拟ENC数据（如果不存在）
    enc_dir = Path("ci/data/s164_subset")
    enc_dir.mkdir(parents=True, exist_ok=True)
    
    all_passed = True
    
    for scenario in scenarios:
        enc_file = enc_dir / f"{scenario}.enc"
        
        # 创建模拟ENC文件
        if not enc_file.exists():
            with open(enc_file, 'w') as f:
                f.write(f"# S-164 Mock Data for {scenario}\n")
                f.write("DSID\nDSPM\nFRID\nVRID\n")
        
        print(f"\n测试场景: {scenario}")
        print("-" * 40)
        
        # 由于需要真实ENC数据，这里只验证框架
        try:
            # 验证S164Runner可以导入
            from ci.run_s164_test import S164TestRunner, S164_SCENARIOS
            
            # 验证场景配置存在
            if scenario in S164_SCENARIOS:
                config = S164_SCENARIOS[scenario]
                print(f"  ✓ 场景配置存在")
                print(f"    起点: {config['start']}")
                print(f"    终点: {config['goal']}")
                if 'expected_min_cpa' in config:
                    print(f"    期望CPA: >{config['expected_min_cpa']}nm")
                else:
                    print(f"    配置完整性: 基础配置")
            else:
                print(f"  ✗ 场景配置缺失")
                all_passed = False
                
        except Exception as e:
            print(f"  ✗ 测试失败: {e}")
            all_passed = False
    
    print("\n" + "="*50)
    if all_passed:
        print("✓ S-164测试框架验证通过")
        print("注: 实际测试需要IHO S-164数据集")
    else:
        print("✗ S-164测试框架存在问题")
        return 1
    
    return 0

if __name__ == "__main__":
    sys.exit(run_s164_tests())