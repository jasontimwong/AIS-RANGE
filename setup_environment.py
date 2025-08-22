#!/usr/bin/env python3
"""
Environment Setup for AIS RANGE Maritime Planning System
"""

import sys
import os
from pathlib import Path

# Add project root to Python path
project_root = Path(__file__).parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

# Set environment variables
os.environ['PYTHONPATH'] = str(project_root)

def setup_paths():
    """Setup Python paths for the project"""
    paths_to_add = [
        str(project_root),
        str(project_root / "lib"),
        str(project_root / "service"),
    ]
    
    for path in paths_to_add:
        if path not in sys.path:
            sys.path.insert(0, path)
    
    print(f"Python paths configured:")
    for path in sys.path[:5]:
        print(f"  - {path}")

if __name__ == "__main__":
    setup_paths()
