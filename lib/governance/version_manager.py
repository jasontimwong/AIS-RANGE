"""
Version Management System
Handles semantic versioning and release tracking
"""

import json
import re
from dataclasses import dataclass, asdict
from typing import Dict, List, Optional, Any
from datetime import datetime
from pathlib import Path
import logging

logger = logging.getLogger(__name__)


@dataclass
class Version:
    """Semantic version representation"""
    major: int
    minor: int
    patch: int
    prerelease: Optional[str] = None
    build: Optional[str] = None
    
    def __str__(self) -> str:
        """Convert to version string"""
        version = f"{self.major}.{self.minor}.{self.patch}"
        if self.prerelease:
            version += f"-{self.prerelease}"
        if self.build:
            version += f"+{self.build}"
        return version
    
    @classmethod
    def from_string(cls, version_str: str) -> 'Version':
        """Parse version from string"""
        # Semantic versioning regex
        pattern = r'^(\d+)\.(\d+)\.(\d+)(?:-([a-zA-Z0-9.]+))?(?:\+([a-zA-Z0-9.]+))?$'
        match = re.match(pattern, version_str)
        
        if not match:
            raise ValueError(f"Invalid version string: {version_str}")
        
        major, minor, patch, prerelease, build = match.groups()
        
        return cls(
            major=int(major),
            minor=int(minor),
            patch=int(patch),
            prerelease=prerelease,
            build=build
        )
    
    def bump_major(self) -> 'Version':
        """Increment major version"""
        return Version(self.major + 1, 0, 0)
    
    def bump_minor(self) -> 'Version':
        """Increment minor version"""
        return Version(self.major, self.minor + 1, 0)
    
    def bump_patch(self) -> 'Version':
        """Increment patch version"""
        return Version(self.major, self.minor, self.patch + 1)
    
    def is_compatible(self, other: 'Version') -> bool:
        """Check if versions are compatible (same major)"""
        return self.major == other.major
    
    def __lt__(self, other: 'Version') -> bool:
        """Compare versions"""
        if self.major != other.major:
            return self.major < other.major
        if self.minor != other.minor:
            return self.minor < other.minor
        if self.patch != other.patch:
            return self.patch < other.patch
        
        # Handle prerelease comparison
        if self.prerelease and not other.prerelease:
            return True  # Prerelease < release
        if not self.prerelease and other.prerelease:
            return False  # Release > prerelease
        
        return False


@dataclass
class ReleaseInfo:
    """Release information"""
    version: Version
    release_date: datetime
    features: List[str]
    bug_fixes: List[str]
    breaking_changes: List[str]
    dependencies: Dict[str, str]
    metadata: Dict[str, Any]
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary"""
        return {
            'version': str(self.version),
            'release_date': self.release_date.isoformat(),
            'features': self.features,
            'bug_fixes': self.bug_fixes,
            'breaking_changes': self.breaking_changes,
            'dependencies': self.dependencies,
            'metadata': self.metadata
        }


class VersionManager:
    """Manages project versioning"""
    
    def __init__(self, project_root: Optional[Path] = None):
        """
        Initialize version manager.
        
        Args:
            project_root: Project root directory
        """
        self.project_root = project_root or Path.cwd()
        self.version_file = self.project_root / "VERSION"
        self.changelog_file = self.project_root / "CHANGELOG.json"
        
        self.current_version = self._load_current_version()
        self.release_history = self._load_release_history()
        
        logger.info(f"Version manager initialized: {self.current_version}")
    
    def _load_current_version(self) -> Version:
        """Load current version from file"""
        if self.version_file.exists():
            version_str = self.version_file.read_text().strip()
            return Version.from_string(version_str)
        else:
            # Default version
            return Version(1, 0, 0)
    
    def _save_current_version(self):
        """Save current version to file"""
        self.version_file.write_text(str(self.current_version))
        logger.info(f"Version saved: {self.current_version}")
    
    def _load_release_history(self) -> List[ReleaseInfo]:
        """Load release history from changelog"""
        if self.changelog_file.exists():
            try:
                with open(self.changelog_file, 'r') as f:
                    data = json.load(f)
                    
                releases = []
                for entry in data.get('releases', []):
                    release = ReleaseInfo(
                        version=Version.from_string(entry['version']),
                        release_date=datetime.fromisoformat(entry['release_date']),
                        features=entry.get('features', []),
                        bug_fixes=entry.get('bug_fixes', []),
                        breaking_changes=entry.get('breaking_changes', []),
                        dependencies=entry.get('dependencies', {}),
                        metadata=entry.get('metadata', {})
                    )
                    releases.append(release)
                
                return releases
            except Exception as e:
                logger.error(f"Failed to load release history: {e}")
                return []
        else:
            return []
    
    def _save_release_history(self):
        """Save release history to changelog"""
        data = {
            'releases': [release.to_dict() for release in self.release_history]
        }
        
        with open(self.changelog_file, 'w') as f:
            json.dump(data, f, indent=2)
        
        logger.info("Release history saved")
    
    def create_release(self,
                      version_type: str = 'patch',
                      features: Optional[List[str]] = None,
                      bug_fixes: Optional[List[str]] = None,
                      breaking_changes: Optional[List[str]] = None,
                      dependencies: Optional[Dict[str, str]] = None,
                      metadata: Optional[Dict[str, Any]] = None) -> ReleaseInfo:
        """
        Create a new release.
        
        Args:
            version_type: Type of version bump ('major', 'minor', 'patch')
            features: List of new features
            bug_fixes: List of bug fixes
            breaking_changes: List of breaking changes
            dependencies: Dependency updates
            metadata: Additional metadata
            
        Returns:
            Release information
        """
        # Bump version
        if version_type == 'major':
            new_version = self.current_version.bump_major()
        elif version_type == 'minor':
            new_version = self.current_version.bump_minor()
        else:
            new_version = self.current_version.bump_patch()
        
        # Create release info
        release = ReleaseInfo(
            version=new_version,
            release_date=datetime.now(),
            features=features or [],
            bug_fixes=bug_fixes or [],
            breaking_changes=breaking_changes or [],
            dependencies=dependencies or {},
            metadata=metadata or {}
        )
        
        # Update version and history
        self.current_version = new_version
        self.release_history.append(release)
        
        # Save changes
        self._save_current_version()
        self._save_release_history()
        
        logger.info(f"Created release: {new_version}")
        return release
    
    def get_latest_release(self) -> Optional[ReleaseInfo]:
        """Get latest release info"""
        if self.release_history:
            return self.release_history[-1]
        return None
    
    def get_release_by_version(self, version_str: str) -> Optional[ReleaseInfo]:
        """Get release by version string"""
        version = Version.from_string(version_str)
        
        for release in self.release_history:
            if release.version == version:
                return release
        
        return None
    
    def check_compatibility(self, required_version: str) -> bool:
        """Check if current version is compatible with requirement"""
        required = Version.from_string(required_version)
        return self.current_version.is_compatible(required)
    
    def generate_changelog_markdown(self) -> str:
        """Generate markdown changelog"""
        lines = []
        lines.append("# Changelog\n")
        lines.append("All notable changes to this project will be documented in this file.\n")
        lines.append("The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),\n")
        lines.append("and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).\n")
        
        # Sort releases by version (newest first)
        sorted_releases = sorted(self.release_history, key=lambda r: r.version, reverse=True)
        
        for release in sorted_releases:
            lines.append(f"\n## [{release.version}] - {release.release_date.strftime('%Y-%m-%d')}\n")
            
            if release.breaking_changes:
                lines.append("\n### ⚠️ Breaking Changes\n")
                for change in release.breaking_changes:
                    lines.append(f"- {change}\n")
            
            if release.features:
                lines.append("\n### Added\n")
                for feature in release.features:
                    lines.append(f"- {feature}\n")
            
            if release.bug_fixes:
                lines.append("\n### Fixed\n")
                for fix in release.bug_fixes:
                    lines.append(f"- {fix}\n")
            
            if release.dependencies:
                lines.append("\n### Dependencies\n")
                for dep, version in release.dependencies.items():
                    lines.append(f"- {dep}: {version}\n")
        
        return "".join(lines)


class DependencyManager:
    """Manages project dependencies"""
    
    def __init__(self, project_root: Optional[Path] = None):
        """
        Initialize dependency manager.
        
        Args:
            project_root: Project root directory
        """
        self.project_root = project_root or Path.cwd()
        self.requirements_file = self.project_root / "requirements.txt"
        self.requirements_dev_file = self.project_root / "requirements-dev.txt"
        
    def get_dependencies(self) -> Dict[str, str]:
        """Get production dependencies"""
        deps = {}
        
        if self.requirements_file.exists():
            for line in self.requirements_file.read_text().splitlines():
                line = line.strip()
                if line and not line.startswith('#'):
                    # Parse requirement
                    match = re.match(r'^([a-zA-Z0-9\-_]+)([><=!]+)(.+)$', line)
                    if match:
                        package, op, version = match.groups()
                        deps[package] = f"{op}{version}"
                    else:
                        # No version specified
                        deps[line] = "*"
        
        return deps
    
    def check_compatibility(self, dependencies: Dict[str, str]) -> List[str]:
        """Check dependency compatibility"""
        current_deps = self.get_dependencies()
        issues = []
        
        for package, required_version in dependencies.items():
            if package in current_deps:
                current = current_deps[package]
                if current != required_version and required_version != "*":
                    issues.append(f"{package}: requires {required_version}, found {current}")
            else:
                issues.append(f"{package}: not found")
        
        return issues
    
    def generate_requirements(self) -> str:
        """Generate requirements.txt content"""
        lines = []
        lines.append("# ECDIS Route Planner Requirements\n")
        lines.append("# Generated by version manager\n\n")
        
        # Core dependencies
        lines.append("# Core\n")
        lines.append("numpy>=1.19.0\n")
        lines.append("shapely>=1.7.0\n")
        lines.append("pandas>=1.2.0\n\n")
        
        # Optional dependencies
        lines.append("# Optional\n")
        lines.append("gdal>=3.0.0  # For S-57 support\n")
        lines.append("lz4>=3.1.0  # For compression\n\n")
        
        # Testing
        lines.append("# Testing\n")
        lines.append("pytest>=6.0.0\n")
        lines.append("pytest-cov>=2.10.0\n")
        
        return "".join(lines)