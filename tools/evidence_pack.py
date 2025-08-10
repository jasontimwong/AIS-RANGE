#!/usr/bin/env python3
"""
证据包生成器：生成可审计的完整证据包
"""
import json
import hashlib
import zipfile
import datetime
import sys
import os
import shutil
from pathlib import Path

class EvidencePackGenerator:
    """证据包生成器"""
    
    def __init__(self, output_dir="artifacts"):
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(exist_ok=True)
        self.timestamp = datetime.datetime.now().strftime("%Y%m%d-%H%M%S")
        
    def generate(self, route_id=None, include_logs=True):
        """
        生成证据包
        
        Args:
            route_id: 航线ID（可选）
            include_logs: 是否包含日志
        
        Returns:
            证据包文件路径
        """
        pack_name = f"EVIDENCE-{self.timestamp}.zip"
        pack_path = self.output_dir / pack_name
        
        manifest = {
            "version": "1.0.0",
            "timestamp": datetime.datetime.now().isoformat(),
            "system": {
                "name": "ECDIS-PLANNER",
                "version": self._get_system_version(),
                "python": sys.version
            },
            "contents": [],
            "checksums": {}
        }
        
        with zipfile.ZipFile(pack_path, 'w', zipfile.ZIP_DEFLATED) as zf:
            # 1. 添加配置文件
            if Path("config.yaml").exists():
                zf.write("config.yaml", "config/config.yaml")
                manifest["contents"].append("config/config.yaml")
                manifest["checksums"]["config.yaml"] = self._file_hash("config.yaml")
            
            # 2. 添加测试结果
            test_dir = Path("测试结果")
            if test_dir.exists():
                for file in test_dir.glob("*"):
                    if file.is_file():
                        arc_name = f"results/{file.name}"
                        zf.write(file, arc_name)
                        manifest["contents"].append(arc_name)
                        manifest["checksums"][file.name] = self._file_hash(file)
            
            # 3. 添加特定航线文件
            if route_id:
                route_files = [
                    f"测试结果/航线_{route_id}.json",
                    f"测试结果/验证报告_{route_id}.json",
                    f"测试结果/航线_{route_id}.rtz"
                ]
                for file_path in route_files:
                    if Path(file_path).exists():
                        arc_name = f"route/{Path(file_path).name}"
                        zf.write(file_path, arc_name)
                        manifest["contents"].append(arc_name)
            
            # 4. 添加日志
            if include_logs:
                log_file = test_dir / "服务日志.txt"
                if log_file.exists():
                    zf.write(log_file, "logs/service.log")
                    manifest["contents"].append("logs/service.log")
                    manifest["checksums"]["service.log"] = self._file_hash(log_file)
            
            # 5. 添加系统快照
            snapshot = self._create_system_snapshot()
            zf.writestr("system/snapshot.json", json.dumps(snapshot, indent=2))
            manifest["contents"].append("system/snapshot.json")
            
            # 6. 添加schema文件
            schema_dir = Path("schemas")
            if schema_dir.exists():
                for schema in schema_dir.glob("*.json"):
                    arc_name = f"schemas/{schema.name}"
                    zf.write(schema, arc_name)
                    manifest["contents"].append(arc_name)
            
            # 7. 添加manifest
            zf.writestr("MANIFEST.json", json.dumps(manifest, indent=2))
        
        # 计算整个包的SHA256
        pack_hash = self._file_hash(pack_path)
        
        # 生成外部验证文件
        verify_file = self.output_dir / f"{pack_name}.sha256"
        verify_file.write_text(f"{pack_hash}  {pack_name}\n")
        
        print(f"✓ 证据包已生成: {pack_path}")
        print(f"  大小: {pack_path.stat().st_size / 1024:.1f} KB")
        print(f"  SHA256: {pack_hash[:32]}...")
        print(f"  包含: {len(manifest['contents'])} 个文件")
        
        return str(pack_path)
    
    def _file_hash(self, filepath):
        """计算文件SHA256"""
        sha256 = hashlib.sha256()
        with open(filepath, 'rb') as f:
            for chunk in iter(lambda: f.read(4096), b""):
                sha256.update(chunk)
        return sha256.hexdigest()
    
    def _get_system_version(self):
        """获取系统版本"""
        try:
            with open("ROADMAP_V2.yaml", "r") as f:
                for line in f:
                    if line.startswith("version:"):
                        return line.split(":")[1].strip()
        except:
            pass
        return "1.0.0"
    
    def _create_system_snapshot(self):
        """创建系统快照"""
        snapshot = {
            "modules": {},
            "environment": {
                "python_path": sys.path,
                "cwd": os.getcwd()
            }
        }
        
        # 收集模块信息
        lib_dir = Path("lib")
        if lib_dir.exists():
            for py_file in lib_dir.rglob("*.py"):
                rel_path = py_file.relative_to(lib_dir)
                snapshot["modules"][str(rel_path)] = {
                    "size": py_file.stat().st_size,
                    "lines": len(py_file.read_text().splitlines())
                }
        
        return snapshot

def main():
    """主函数"""
    import argparse
    parser = argparse.ArgumentParser(description="生成证据包")
    parser.add_argument("--route-id", help="指定航线ID")
    parser.add_argument("--no-logs", action="store_true", help="不包含日志")
    parser.add_argument("--output", default="artifacts", help="输出目录")
    
    args = parser.parse_args()
    
    generator = EvidencePackGenerator(args.output)
    pack_path = generator.generate(
        route_id=args.route_id,
        include_logs=not args.no_logs
    )
    
    return 0

if __name__ == "__main__":
    sys.exit(main())