"""
Tests for SBOM (Software Bill of Materials) Manager
"""

import pytest
import json
import tempfile
from pathlib import Path
import sys
import os

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from lib.sbom.sbom_manager import (
    Dependency,
    SBOM,
    SBOMManager
)


class TestDependency:
    """Test Dependency class"""
    
    def test_dependency_creation(self):
        """Test creating dependency"""
        dep = Dependency(
            name="numpy",
            version="1.24.0",
            license="BSD-3-Clause",
            source="pip"
        )
        
        assert dep.name == "numpy"
        assert dep.version == "1.24.0"
        assert dep.license == "BSD-3-Clause"
        assert dep.source == "pip"
        assert dep.vulnerabilities == []
    
    def test_dependency_with_vulnerabilities(self):
        """Test dependency with vulnerabilities"""
        dep = Dependency(
            name="vulnerable-package",
            version="1.0.0",
            vulnerabilities=[
                {'id': 'CVE-2025-0001', 'severity': 'high'}
            ]
        )
        
        assert len(dep.vulnerabilities) == 1
        assert dep.vulnerabilities[0]['id'] == 'CVE-2025-0001'


class TestSBOM:
    """Test SBOM class"""
    
    def test_sbom_creation(self):
        """Test creating SBOM"""
        sbom = SBOM(
            created="2025-01-01T10:00:00",
            version="1.0.0"
        )
        
        assert sbom.created == "2025-01-01T10:00:00"
        assert sbom.version == "1.0.0"
        assert sbom.format == "CycloneDX"
        assert sbom.components == []
        assert sbom.metadata == {}
    
    def test_sbom_to_dict(self):
        """Test converting SBOM to dict"""
        sbom = SBOM(
            created="2025-01-01T10:00:00",
            version="1.0.0",
            components=[
                Dependency(name="test-pkg", version="1.0")
            ],
            metadata={'test': 'data'}
        )
        
        sbom_dict = sbom.to_dict()
        
        assert sbom_dict['bomFormat'] == "CycloneDX"
        assert sbom_dict['specVersion'] == "1.4"
        assert 'serialNumber' in sbom_dict
        assert len(sbom_dict['components']) == 1
        assert sbom_dict['metadata']['test'] == 'data'


class TestSBOMManager:
    """Test SBOMManager class"""
    
    def test_manager_initialization(self):
        """Test manager initialization"""
        manager = SBOMManager()
        
        assert manager.sbom is None
        assert manager.vulnerability_db == {}
    
    def test_parse_requirements(self, tmp_path):
        """Test parsing requirements file"""
        manager = SBOMManager()
        
        # Create requirements file
        req_file = tmp_path / "requirements.txt"
        req_file.write_text("""
# Test requirements
numpy==1.24.0
pandas>=2.0.0
scipy
# Comment line
matplotlib==3.5.0
""")
        
        deps = manager._parse_requirements(str(req_file))
        
        assert len(deps) == 4
        
        # Check parsed dependencies
        dep_names = [d.name for d in deps]
        assert 'numpy' in dep_names
        assert 'pandas' in dep_names
        assert 'scipy' in dep_names
        assert 'matplotlib' in dep_names
        
        # Check versions
        numpy_dep = next(d for d in deps if d.name == 'numpy')
        assert numpy_dep.version == '1.24.0'
        
        pandas_dep = next(d for d in deps if d.name == 'pandas')
        assert pandas_dep.version == 'latest'
    
    def test_get_installed_packages(self):
        """Test getting installed packages"""
        manager = SBOMManager()
        
        # This test depends on the environment
        # Just check that it returns a list
        packages = manager._get_installed_packages()
        
        assert isinstance(packages, list)
        
        # Should have at least pytest installed
        pkg_names = [p.name for p in packages]
        assert any('pytest' in name.lower() for name in pkg_names)
    
    def test_generate_sbom_basic(self):
        """Test basic SBOM generation"""
        manager = SBOMManager()
        
        sbom = manager.generate_sbom(include_transitive=False)
        
        assert sbom is not None
        assert manager.sbom is not None
        assert len(sbom.components) > 0
        assert sbom.metadata['include_transitive'] == False
    
    def test_generate_sbom_with_requirements(self, tmp_path):
        """Test SBOM generation with requirements file"""
        manager = SBOMManager()
        
        # Create requirements file
        req_file = tmp_path / "requirements.txt"
        req_file.write_text("numpy==1.24.0\npandas==2.0.0")
        
        sbom = manager.generate_sbom(
            requirements_file=str(req_file),
            include_transitive=False
        )
        
        # Should include requirements
        comp_names = [c.name for c in sbom.components]
        assert 'numpy' in comp_names or 'pandas' in comp_names
    
    def test_check_vulnerabilities(self):
        """Test vulnerability checking"""
        manager = SBOMManager()
        
        # Create SBOM with known vulnerable packages
        manager.sbom = SBOM(
            created="2025-01-01T10:00:00",
            version="1.0.0",
            components=[
                Dependency(name="requests", version="2.20.0"),
                Dependency(name="urllib3", version="1.26.0"),
                Dependency(name="safe-package", version="1.0.0")
            ]
        )
        
        vulns = manager.check_vulnerabilities()
        
        # Should find vulnerabilities in older versions
        assert isinstance(vulns, dict)
        # Note: Actual vulnerabilities depend on the internal DB
    
    def test_generate_license_report(self):
        """Test license report generation"""
        manager = SBOMManager()
        
        # Create SBOM with various licenses
        manager.sbom = SBOM(
            created="2025-01-01T10:00:00",
            version="1.0.0",
            components=[
                Dependency(name="mit-pkg", version="1.0", license="MIT"),
                Dependency(name="gpl-pkg", version="1.0", license="GPL-3.0"),
                Dependency(name="apache-pkg", version="1.0", license="Apache-2.0"),
                Dependency(name="unknown-pkg", version="1.0", license=None)
            ]
        )
        
        report = manager.generate_license_report()
        
        assert report['total_components'] == 4
        assert 'MIT' in report['licenses']
        assert 'GPL-3.0' in report['licenses']
        assert len(report['unknown_licenses']) == 1
        assert len(report['copyleft_licenses']) == 1
        assert len(report['permissive_licenses']) == 2
    
    def test_export_sbom_cyclonedx(self, tmp_path):
        """Test exporting SBOM in CycloneDX format"""
        manager = SBOMManager()
        
        # Create simple SBOM
        manager.sbom = SBOM(
            created="2025-01-01T10:00:00",
            version="1.0.0",
            components=[
                Dependency(name="test-pkg", version="1.0.0")
            ]
        )
        
        output_file = tmp_path / "sbom_cyclonedx.json"
        result = manager.export_sbom(str(output_file), format='cyclonedx')
        
        assert output_file.exists()
        
        # Verify content
        with open(output_file, 'r') as f:
            sbom_data = json.load(f)
        
        assert sbom_data['bomFormat'] == 'CycloneDX'
        assert sbom_data['specVersion'] == '1.4'
        assert len(sbom_data['components']) == 1
    
    def test_export_sbom_spdx(self, tmp_path):
        """Test exporting SBOM in SPDX format"""
        manager = SBOMManager()
        
        # Create simple SBOM
        manager.sbom = SBOM(
            created="2025-01-01T10:00:00",
            version="1.0.0",
            components=[
                Dependency(name="spdx-test", version="2.0.0", license="MIT")
            ]
        )
        
        output_file = tmp_path / "sbom_spdx.json"
        result = manager.export_sbom(str(output_file), format='spdx')
        
        assert output_file.exists()
        
        # Verify content
        with open(output_file, 'r') as f:
            spdx_data = json.load(f)
        
        assert spdx_data['spdxVersion'] == 'SPDX-2.3'
        assert len(spdx_data['packages']) == 1
        assert spdx_data['packages'][0]['name'] == 'spdx-test'
    
    def test_verify_supply_chain(self):
        """Test supply chain verification"""
        manager = SBOMManager()
        
        # Create SBOM with various components
        manager.sbom = SBOM(
            created="2025-01-01T10:00:00",
            version="1.0.0",
            components=[
                Dependency(name="verified-pkg", version="1.0", hash="abc123"),
                Dependency(name="unverified-pkg", version="1.0", hash=None),
                Dependency(name="test-suspicious", version="1.0", hash="def456")
            ]
        )
        
        report = manager.verify_supply_chain()
        
        assert report['verified_components'] == 2
        assert report['unverified_components'] == 1
        assert len(report['suspicious_components']) == 1  # 'test' in name
        assert report['integrity_score'] > 0
    
    def test_compare_sboms(self, tmp_path):
        """Test comparing two SBOMs"""
        manager = SBOMManager()
        
        # Create current SBOM
        manager.sbom = SBOM(
            created="2025-01-01T10:00:00",
            version="1.0.0",
            components=[
                Dependency(name="pkg-a", version="1.0.0"),
                Dependency(name="pkg-b", version="2.0.0"),
                Dependency(name="pkg-c", version="3.0.0")
            ]
        )
        
        # Create other SBOM file
        other_sbom = {
            'components': [
                {'name': 'pkg-a', 'version': '1.0.0'},  # Same
                {'name': 'pkg-b', 'version': '1.5.0'},  # Updated
                {'name': 'pkg-d', 'version': '4.0.0'}   # Removed in current
            ]
        }
        
        other_file = tmp_path / "other_sbom.json"
        with open(other_file, 'w') as f:
            json.dump(other_sbom, f)
        
        # Compare
        report = manager.compare_sboms(str(other_file))
        
        assert len(report['added']) == 1  # pkg-c
        assert len(report['removed']) == 1  # pkg-d
        assert len(report['updated']) == 1  # pkg-b
        assert len(report['unchanged']) == 1  # pkg-a
        
        assert report['summary']['added_count'] == 1
        assert report['summary']['removed_count'] == 1
        assert report['summary']['updated_count'] == 1