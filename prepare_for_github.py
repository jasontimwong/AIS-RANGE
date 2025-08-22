#!/usr/bin/env python3
"""
Prepare project for GitHub push - Clean up and organize files
"""

import os
import shutil
import json
from pathlib import Path

def prepare_project():
    """Prepare project for GitHub by cleaning up files"""
    
    project_root = Path(__file__).parent
    
    # Files/directories to exclude from GitHub
    exclude_patterns = [
        "测试结果/",
        "一键启动.sh",
        "cleanup_redundant_files.sh",
        "*.log",
        "nohup.out",
        "__pycache__/",
        "*.pyc",
        ".DS_Store",
        "node_modules/",
        ".env",
        "*.tmp",
        "route_*.json",  # Generated route files
        "test.s421",
        "test_*.py",
        "*.md.bak"
    ]
    
    # Create .gitignore if it doesn't exist
    gitignore_content = """# Python
__pycache__/
*.py[cod]
*$py.class
*.so
.Python
build/
develop-eggs/
dist/
downloads/
eggs/
.eggs/
lib/
lib64/
parts/
sdist/
var/
wheels/
*.egg-info/
.installed.cfg
*.egg

# Node.js
node_modules/
npm-debug.log*
yarn-debug.log*
yarn-error.log*
.npm

# Environment variables
.env
.env.local
.env.development.local
.env.test.local
.env.production.local

# IDE
.vscode/
.idea/
*.swp
*.swo

# OS
.DS_Store
.DS_Store?
._*
.Spotlight-V100
.Trashes
ehthumbs.db
Thumbs.db

# Project specific
nohup.out
*.log
route_*.json
test.s421
测试结果/
*.tmp

# Large data files (use Git LFS if needed)
data/enc/ENC_ROOT/
data/osm_tiles/
data/openseamap_tiles/
"""
    
    gitignore_path = project_root / ".gitignore"
    with open(gitignore_path, 'w', encoding='utf-8') as f:
        f.write(gitignore_content)
    
    print(f"✅ Created .gitignore")
    
    # Replace README.md with English version
    readme_path = project_root / "README.md"
    readme_en_path = project_root / "README_EN.md"
    
    if readme_en_path.exists():
        shutil.copy2(readme_en_path, readme_path)
        print(f"✅ Replaced README.md with English version")
    
    # Create a clean package.json for the root
    root_package_json = {
        "name": "ais-range",
        "version": "3.3.3",
        "description": "AIS RANGE - Maritime Route Planning & Collision Avoidance System",
        "main": "service/app.py",
        "scripts": {
            "setup": "python setup_environment.py",
            "start": "cd service && PYTHONPATH=.. python app.py",
            "dev": "cd ui && npm run dev",
            "build": "cd ui && npm run build",
            "test": "pytest tests/ -v"
        },
        "keywords": [
            "maritime",
            "ais",
            "route-planning",
            "collision-avoidance",
            "ecdis",
            "navigation",
            "colreg",
            "tss"
        ],
        "author": "AIS RANGE Team",
        "license": "MIT",
        "repository": {
            "type": "git",
            "url": "https://github.com/jasontimwong/ais-range.git"
        }
    }
    
    with open(project_root / "package.json", 'w', encoding='utf-8') as f:
        json.dump(root_package_json, f, indent=2)
    
    print(f"✅ Created root package.json")
    
    # Create LICENSE file
    license_content = """MIT License

Copyright (c) 2025 AIS RANGE Team

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.
"""
    
    with open(project_root / "LICENSE", 'w', encoding='utf-8') as f:
        f.write(license_content)
    
    print(f"✅ Created LICENSE file")
    
    # Update CHANGELOG to English
    changelog_en_content = """# Changelog

All notable changes to this project will be documented in this file.

## [3.3.3] - 2025-01-14

### 🐛 Fixed
- **Route Display Issues**: Fixed new planned routes showing incorrectly on map
- **Route Jump Back**: Resolved routes jumping back to initial state after clicks
- **Data Sync Issues**: Ensured correct route data synchronization through subscription pattern

### 🔧 Changed
- **RouteService Refactoring**: Implemented singleton pattern for unified route data management
  - Added localStorage persistence (24-hour cache)
  - Implemented subscription pattern for automatic component updates
  - Distinguished between user-planned and default routes
- **Component Updates**: 
  - App.tsx subscribes to RouteService for automatic route updates
  - RoutePlanner uses routeService.planRoute()
  - Removed dependency on fixed getRoute() function

### 🗑️ Removed
- Deleted redundant test files (test_route_display.html, test_route_service.html)
- Cleaned up temporary documentation (SOLUTION_DELIVERY.md, ISSUES_DIAGNOSIS.md)

## [3.3.2] - 2025-08-14

### 🎉 Major Updates
- **Dynamic Route Planning Refactoring** - Complete re-planning architecture with unified 50m path granularity

### ✨ Added
- HybridAStar dynamic motion_step configuration support
- Performance benchmark framework (tests/bench/)
- Refactored acceptance test suite
  
### ♻️ Reverted
- Reverted "Frontend core planning service integration (🧮 Planning(Core) button)", temporarily not directly integrating `/plan` in frontend
- Maintained `getEncLite` priority using backend `/enc/lite` strategy (non-breaking)

### 🔧 Changed
- **Path Granularity Optimization**: Reduced from 100m to 50m, 48% precision improvement
- **Architecture Improvement**: Replaced local patching with complete re-planning
- **Performance Optimization**: Single planning replaces dual-path comparison
- **Code Simplification**: Removed redundant _densify_latlon and _stitch_replanned_segments methods

### 📊 Performance Metrics
- Path granularity: 95.9m → 49.9m
- Planning time: <1 second (20 AIS targets)
- Test coverage: All 6 acceptance tests passed

---

**Version**: 3.3.3 - AIS RANGE Maritime Planning System  
**Status**: Production Ready 🚀  
**Updated**: 2025-01-14
"""
    
    with open(project_root / "CHANGELOG_EN.md", 'w', encoding='utf-8') as f:
        f.write(changelog_en_content)
    
    print(f"✅ Created English CHANGELOG")
    
    print("\n🚀 Project prepared for GitHub!")
    print("Ready to create repository and push to GitHub.")

if __name__ == "__main__":
    prepare_project()
