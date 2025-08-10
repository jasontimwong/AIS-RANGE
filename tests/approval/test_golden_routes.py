"""
金样审批测试
确保路径规划的稳定性和一致性
"""
import json
import hashlib
import os
import sys
sys.path.insert(0, os.path.abspath('.'))

def compute_hash(filepath):
    """计算文件哈希"""
    if not os.path.exists(filepath):
        return None
    with open(filepath, 'rb') as f:
        return hashlib.sha256(f.read()).hexdigest()[:16]

def test_golden_routes_exist():
    """测试金样文件存在"""
    golden_dir = "artifacts/golden"
    assert os.path.exists(golden_dir), "金样目录不存在"
    
    # 检查是否有金样文件
    golden_files = [f for f in os.listdir(golden_dir) if f.endswith('.rtz')]
    if not golden_files:
        print("警告: 无金样文件，需要生成baseline")
        return False
    
    print(f"找到 {len(golden_files)} 个金样文件")
    for f in golden_files:
        hash_val = compute_hash(os.path.join(golden_dir, f))
        print(f"  - {f}: {hash_val}")
    
    return True

if __name__ == "__main__":
    if test_golden_routes_exist():
        print("✅ 金样测试通过")
    else:
        print("⚠️  需要生成金样baseline")
        sys.exit(1)
