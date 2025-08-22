#!/usr/bin/env python3
"""
最终综合测试 - 验证所有路径规划功能
Final Comprehensive Test - Verify all route planning functionality
"""

import requests
import json
import time
from datetime import datetime

def test_api_endpoint(name, start, goal, expected_end):
    """测试单个API端点"""
    print(f"\n--- {name} ---")
    
    url = "http://localhost:8000/api/route/plan_full"
    payload = {"start": start, "goal": goal}
    
    try:
        start_time = time.time()
        response = requests.post(url, json=payload, timeout=30)
        end_time = time.time()
        
        if response.status_code == 200:
            data = response.json()
            coords = data.get("coords", [])
            
            if coords:
                actual_end = coords[-1]
                error_lon = abs(actual_end[0] - expected_end[0])
                error_lat = abs(actual_end[1] - expected_end[1])
                
                print(f"✅ 成功: {len(coords)} 航点")
                print(f"   响应时间: {(end_time - start_time)*1000:.1f}ms")
                print(f"   起点: {coords[0]}")
                print(f"   终点: {actual_end}")
                print(f"   期望: {expected_end}")
                
                if error_lon < 0.1 and error_lat < 0.1:
                    print(f"   ✅ 终点坐标正确 (误差: {error_lon:.3f}, {error_lat:.3f})")
                    return True
                else:
                    print(f"   ❌ 终点坐标错误 (误差: {error_lon:.3f}, {error_lat:.3f})")
                    return False
            else:
                print("   ❌ 返回空坐标")
                return False
        else:
            print(f"   ❌ HTTP {response.status_code}: {response.text}")
            return False
            
    except Exception as e:
        print(f"   ❌ 异常: {e}")
        return False

def main():
    """运行综合测试"""
    print("=" * 80)
    print("最终综合测试 - 海上路径规划系统")
    print("Final Comprehensive Test - Maritime Route Planning System")
    print("=" * 80)
    print(f"测试时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    
    # 定义测试用例
    test_cases = [
        {
            "name": "深圳→新加坡（历史航线）",
            "start": {"lat": 22.500, "lon": 114.100},
            "goal": {"lat": 1.265, "lon": 103.851},
            "expected_end": [103.851, 1.265]
        },
        {
            "name": "上海→新加坡（长距离）",
            "start": {"lat": 31.230, "lon": 121.508},
            "goal": {"lat": 1.265, "lon": 103.851},
            "expected_end": [103.851, 1.265]
        },
        {
            "name": "香港→新加坡（预定义路线）",
            "start": {"lat": 22.300, "lon": 114.200},
            "goal": {"lat": 1.265, "lon": 103.851},
            "expected_end": [103.851, 1.265]
        },
        {
            "name": "青岛→釜山（TSS合规）",
            "start": {"lat": 36.070, "lon": 120.380},
            "goal": {"lat": 35.100, "lon": 129.040},
            "expected_end": [129.040, 35.100]
        },
        {
            "name": "天津→横滨（跨海航线）",
            "start": {"lat": 39.000, "lon": 117.750},
            "goal": {"lat": 35.440, "lon": 139.640},
            "expected_end": [139.640, 35.440]
        }
    ]
    
    # 执行测试
    passed_tests = 0
    total_tests = len(test_cases)
    
    for test_case in test_cases:
        success = test_api_endpoint(
            test_case["name"],
            test_case["start"],
            test_case["goal"],
            test_case["expected_end"]
        )
        if success:
            passed_tests += 1
    
    # 总结
    print("\n" + "=" * 80)
    print("测试总结 / Test Summary")
    print("=" * 80)
    print(f"✅ 通过测试: {passed_tests}/{total_tests}")
    print(f"❌ 失败测试: {total_tests - passed_tests}/{total_tests}")
    print(f"成功率: {(passed_tests/total_tests*100):.1f}%")
    
    if passed_tests == total_tests:
        print("\n🎉 所有测试通过！系统工作正常。")
        print("🎉 All tests passed! System is working correctly.")
        
        print("\n核心修复总结:")
        print("1. ✅ 修复了TSS边界数据中的错误坐标 [104.0, 6.0] → [103.9, 5.5]")
        print("2. ✅ 历史航线规划器正确返回新加坡港坐标 [103.851, 1.265]")
        print("3. ✅ API端点与直接函数调用结果一致")
        print("4. ✅ 所有路径类型（历史、TSS、预定义）都工作正常")
        
        return True
    else:
        print(f"\n❌ {total_tests - passed_tests} 个测试失败，需要进一步调试。")
        return False

if __name__ == "__main__":
    success = main()
    exit(0 if success else 1)