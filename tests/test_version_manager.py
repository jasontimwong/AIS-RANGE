"""
Tests for Version Management System
"""

import json
import pytest
from pathlib import Path
from datetime import datetime
from unittest.mock import MagicMock, patch

from lib.governance.version_manager import (
    Version, ReleaseInfo, VersionManager, DependencyManager
)


class TestVersion:
    """Test Version class"""
    
    def test_version_creation(self):
        """Test version creation"""
        v = Version(1, 2, 3)
        assert v.major == 1
        assert v.minor == 2
        assert v.patch == 3
        assert str(v) == "1.2.3"
    
    def test_version_with_prerelease(self):
        """Test version with prerelease"""
        v = Version(1, 0, 0, prerelease="alpha.1")
        assert str(v) == "1.0.0-alpha.1"
    
    def test_version_with_build(self):
        """Test version with build metadata"""
        v = Version(1, 0, 0, build="20250810")
        assert str(v) == "1.0.0+20250810"
    
    def test_version_from_string(self):
        """Test parsing version from string"""
        v = Version.from_string("2.1.3-beta.2+build.123")
        assert v.major == 2
        assert v.minor == 1
        assert v.patch == 3
        assert v.prerelease == "beta.2"
        assert v.build == "build.123"
    
    def test_version_bump_major(self):
        """Test major version bump"""
        v1 = Version(1, 2, 3)
        v2 = v1.bump_major()
        assert str(v2) == "2.0.0"
    
    def test_version_bump_minor(self):
        """Test minor version bump"""
        v1 = Version(1, 2, 3)
        v2 = v1.bump_minor()
        assert str(v2) == "1.3.0"
    
    def test_version_bump_patch(self):
        """Test patch version bump"""
        v1 = Version(1, 2, 3)
        v2 = v1.bump_patch()
        assert str(v2) == "1.2.4"
    
    def test_version_compatibility(self):
        """Test version compatibility check"""
        v1 = Version(1, 2, 3)
        v2 = Version(1, 5, 0)
        v3 = Version(2, 0, 0)
        
        assert v1.is_compatible(v2)  # Same major
        assert not v1.is_compatible(v3)  # Different major
    
    def test_version_comparison(self):
        """Test version comparison"""
        v1 = Version(1, 2, 3)
        v2 = Version(1, 2, 4)
        v3 = Version(1, 3, 0)
        v4 = Version(2, 0, 0)
        
        assert v1 < v2
        assert v2 < v3
        assert v3 < v4
        
        # Prerelease comparison
        v5 = Version(1, 0, 0)
        v6 = Version(1, 0, 0, prerelease="alpha")
        assert v6 < v5  # Prerelease < release


class TestReleaseInfo:
    """Test ReleaseInfo class"""
    
    def test_release_info_creation(self):
        """Test release info creation"""
        version = Version(1, 0, 0)
        release = ReleaseInfo(
            version=version,
            release_date=datetime.now(),
            features=["Feature 1", "Feature 2"],
            bug_fixes=["Fix 1"],
            breaking_changes=[],
            dependencies={"numpy": ">=1.19.0"},
            metadata={"author": "test"}
        )
        
        assert release.version == version
        assert len(release.features) == 2
        assert len(release.bug_fixes) == 1
        assert len(release.breaking_changes) == 0
    
    def test_release_to_dict(self):
        """Test release serialization"""
        version = Version(1, 0, 0)
        now = datetime.now()
        release = ReleaseInfo(
            version=version,
            release_date=now,
            features=["Feature 1"],
            bug_fixes=[],
            breaking_changes=[],
            dependencies={},
            metadata={}
        )
        
        data = release.to_dict()
        assert data['version'] == "1.0.0"
        assert data['release_date'] == now.isoformat()
        assert len(data['features']) == 1


class TestVersionManager:
    """Test VersionManager class"""
    
    @pytest.fixture
    def temp_dir(self, tmp_path):
        """Create temporary directory"""
        return tmp_path
    
    def test_version_manager_init(self, temp_dir):
        """Test version manager initialization"""
        vm = VersionManager(temp_dir)
        
        # Default version should be 1.0.0
        assert str(vm.current_version) == "1.0.0"
        assert len(vm.release_history) == 0
    
    def test_version_manager_load_existing(self, temp_dir):
        """Test loading existing version"""
        # Create version file
        version_file = temp_dir / "VERSION"
        version_file.write_text("2.3.4")
        
        vm = VersionManager(temp_dir)
        assert str(vm.current_version) == "2.3.4"
    
    def test_create_release(self, temp_dir):
        """Test creating a release"""
        vm = VersionManager(temp_dir)
        
        release = vm.create_release(
            version_type='minor',
            features=["New feature"],
            bug_fixes=["Bug fix"]
        )
        
        assert str(release.version) == "1.1.0"
        assert str(vm.current_version) == "1.1.0"
        assert len(vm.release_history) == 1
        
        # Check files were saved
        assert (temp_dir / "VERSION").exists()
        assert (temp_dir / "CHANGELOG.json").exists()
    
    def test_create_major_release(self, temp_dir):
        """Test creating major release"""
        vm = VersionManager(temp_dir)
        
        release = vm.create_release(
            version_type='major',
            breaking_changes=["Breaking change"]
        )
        
        assert str(release.version) == "2.0.0"
    
    def test_get_latest_release(self, temp_dir):
        """Test getting latest release"""
        vm = VersionManager(temp_dir)
        
        # No releases yet
        assert vm.get_latest_release() is None
        
        # Create releases
        vm.create_release(version_type='patch')
        vm.create_release(version_type='minor')
        
        latest = vm.get_latest_release()
        assert str(latest.version) == "1.1.0"
    
    def test_get_release_by_version(self, temp_dir):
        """Test getting release by version"""
        vm = VersionManager(temp_dir)
        
        vm.create_release(version_type='patch')  # 1.0.1
        vm.create_release(version_type='minor')  # 1.1.0
        
        release = vm.get_release_by_version("1.0.1")
        assert release is not None
        assert str(release.version) == "1.0.1"
        
        # Non-existent version
        assert vm.get_release_by_version("2.0.0") is None
    
    def test_check_compatibility(self, temp_dir):
        """Test compatibility checking"""
        vm = VersionManager(temp_dir)
        
        # Current version is 1.0.0
        assert vm.check_compatibility("1.5.0")  # Compatible
        assert not vm.check_compatibility("2.0.0")  # Not compatible
    
    def test_generate_changelog_markdown(self, temp_dir):
        """Test changelog generation"""
        vm = VersionManager(temp_dir)
        
        # Create some releases
        vm.create_release(
            version_type='minor',
            features=["Feature A", "Feature B"],
            bug_fixes=["Fix 1"]
        )
        
        vm.create_release(
            version_type='major',
            breaking_changes=["Breaking API change"],
            features=["Feature C"]
        )
        
        changelog = vm.generate_changelog_markdown()
        
        assert "# Changelog" in changelog
        assert "[2.0.0]" in changelog
        assert "[1.1.0]" in changelog
        assert "Breaking Changes" in changelog
        assert "Feature A" in changelog


class TestDependencyManager:
    """Test DependencyManager class"""
    
    @pytest.fixture
    def temp_dir(self, tmp_path):
        """Create temporary directory"""
        return tmp_path
    
    def test_dependency_manager_init(self, temp_dir):
        """Test dependency manager initialization"""
        dm = DependencyManager(temp_dir)
        
        assert dm.requirements_file == temp_dir / "requirements.txt"
        assert dm.requirements_dev_file == temp_dir / "requirements-dev.txt"
    
    def test_get_dependencies(self, temp_dir):
        """Test getting dependencies"""
        # Create requirements file
        req_file = temp_dir / "requirements.txt"
        req_file.write_text("""
# Comment
numpy>=1.19.0
shapely==1.7.0
pandas
""")
        
        dm = DependencyManager(temp_dir)
        deps = dm.get_dependencies()
        
        assert deps['numpy'] == ">=1.19.0"
        assert deps['shapely'] == "==1.7.0"
        assert deps['pandas'] == "*"
    
    def test_check_compatibility(self, temp_dir):
        """Test dependency compatibility check"""
        # Create requirements file
        req_file = temp_dir / "requirements.txt"
        req_file.write_text("numpy>=1.19.0\nshapely==1.7.0")
        
        dm = DependencyManager(temp_dir)
        
        # Check compatible dependencies
        issues = dm.check_compatibility({
            'numpy': '>=1.19.0',
            'shapely': '==1.7.0'
        })
        assert len(issues) == 0
        
        # Check incompatible dependencies
        issues = dm.check_compatibility({
            'numpy': '>=2.0.0',  # Different version
            'missing_pkg': '1.0.0'  # Missing package
        })
        assert len(issues) == 2
    
    def test_generate_requirements(self, temp_dir):
        """Test requirements generation"""
        dm = DependencyManager(temp_dir)
        
        content = dm.generate_requirements()
        
        assert "numpy>=1.19.0" in content
        assert "shapely>=1.7.0" in content
        assert "pytest>=6.0.0" in content