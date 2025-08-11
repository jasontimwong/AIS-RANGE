"""
Deployment and Release Management
Handles deployment scripts and release processes
"""

import os
import shutil
import subprocess
import tarfile
import zipfile
from dataclasses import dataclass
from typing import List, Dict, Any, Optional
from pathlib import Path
from datetime import datetime
import logging
import hashlib
import json

from lib.governance.version_manager import VersionManager, Version
from lib.governance.config_manager import ConfigManager, Environment

logger = logging.getLogger(__name__)


@dataclass
class DeploymentPackage:
    """Deployment package information"""
    version: Version
    environment: Environment
    created_at: datetime
    files: List[Path]
    checksums: Dict[str, str]
    metadata: Dict[str, Any]


class DeploymentManager:
    """Manages deployment and release processes"""
    
    def __init__(self, project_root: Optional[Path] = None):
        """
        Initialize deployment manager.
        
        Args:
            project_root: Project root directory
        """
        self.project_root = project_root or Path.cwd()
        self.dist_dir = self.project_root / "dist"
        self.build_dir = self.project_root / "build"
        
        self.version_manager = VersionManager(project_root)
        self.config_manager = ConfigManager()
        
        # Ensure directories exist
        self.dist_dir.mkdir(exist_ok=True)
        self.build_dir.mkdir(exist_ok=True)
        
        logger.info("Deployment manager initialized")
    
    def create_package(self,
                       environment: Environment = Environment.PRODUCTION,
                       include_tests: bool = False) -> DeploymentPackage:
        """
        Create deployment package.
        
        Args:
            environment: Target environment
            include_tests: Whether to include test files
            
        Returns:
            Deployment package info
        """
        logger.info(f"Creating deployment package for {environment.value}")
        
        # Clean build directory
        if self.build_dir.exists():
            shutil.rmtree(self.build_dir)
        self.build_dir.mkdir()
        
        # Collect files
        files = self._collect_files(include_tests)
        
        # Copy files to build directory
        for file_path in files:
            rel_path = file_path.relative_to(self.project_root)
            dest_path = self.build_dir / rel_path
            dest_path.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(file_path, dest_path)
        
        # Generate checksums
        checksums = self._generate_checksums(files)
        
        # Create package info
        package = DeploymentPackage(
            version=self.version_manager.current_version,
            environment=environment,
            created_at=datetime.now(),
            files=files,
            checksums=checksums,
            metadata={
                'python_version': '3.8+',
                'include_tests': include_tests,
                'total_files': len(files)
            }
        )
        
        # Save package manifest
        self._save_manifest(package)
        
        # Create archive
        archive_path = self._create_archive(package)
        logger.info(f"Package created: {archive_path}")
        
        return package
    
    def _collect_files(self, include_tests: bool) -> List[Path]:
        """Collect files for deployment"""
        files = []
        
        # Python files
        for pattern in ['lib/**/*.py', 'scripts/*.py']:
            files.extend(self.project_root.glob(pattern))
        
        # Configuration files
        files.extend(self.project_root.glob('config/*.json'))
        
        # Documentation
        files.extend([
            self.project_root / 'README.md',
            self.project_root / 'SYSTEM_ARCHITECTURE.md',
            self.project_root / 'DEVELOPMENT_LOG.md'
        ])
        
        # Scripts
        files.extend(self.project_root.glob('scripts/*.sh'))
        
        # Tests if requested
        if include_tests:
            files.extend(self.project_root.glob('tests/**/*.py'))
        
        # Filter out non-existent files
        files = [f for f in files if f.exists()]
        
        return files
    
    def _generate_checksums(self, files: List[Path]) -> Dict[str, str]:
        """Generate SHA256 checksums for files"""
        checksums = {}
        
        for file_path in files:
            if file_path.is_file():
                with open(file_path, 'rb') as f:
                    hash_obj = hashlib.sha256()
                    while chunk := f.read(8192):
                        hash_obj.update(chunk)
                    
                    rel_path = file_path.relative_to(self.project_root)
                    checksums[str(rel_path)] = hash_obj.hexdigest()
        
        return checksums
    
    def _save_manifest(self, package: DeploymentPackage):
        """Save package manifest"""
        manifest = {
            'version': str(package.version),
            'environment': package.environment.value,
            'created_at': package.created_at.isoformat(),
            'metadata': package.metadata,
            'checksums': package.checksums
        }
        
        manifest_path = self.build_dir / 'MANIFEST.json'
        with open(manifest_path, 'w') as f:
            json.dump(manifest, f, indent=2)
    
    def _create_archive(self, package: DeploymentPackage) -> Path:
        """Create deployment archive"""
        archive_name = f"ecdis-planner-{package.version}-{package.environment.value}.tar.gz"
        archive_path = self.dist_dir / archive_name
        
        with tarfile.open(archive_path, 'w:gz') as tar:
            tar.add(self.build_dir, arcname=f"ecdis-planner-{package.version}")
        
        return archive_path
    
    def deploy(self,
               package_path: Path,
               target_host: Optional[str] = None,
               target_dir: str = "/opt/ecdis-planner") -> bool:
        """
        Deploy package to target.
        
        Args:
            package_path: Path to deployment package
            target_host: Target host (None for local)
            target_dir: Target directory
            
        Returns:
            Success status
        """
        logger.info(f"Deploying {package_path} to {target_host or 'local'}:{target_dir}")
        
        if target_host:
            # Remote deployment
            return self._deploy_remote(package_path, target_host, target_dir)
        else:
            # Local deployment
            return self._deploy_local(package_path, target_dir)
    
    def _deploy_local(self, package_path: Path, target_dir: str) -> bool:
        """Deploy to local directory"""
        try:
            target_path = Path(target_dir)
            
            # Create target directory
            target_path.mkdir(parents=True, exist_ok=True)
            
            # Extract package
            with tarfile.open(package_path, 'r:gz') as tar:
                tar.extractall(target_path.parent)
            
            logger.info(f"Package deployed to {target_dir}")
            return True
            
        except Exception as e:
            logger.error(f"Deployment failed: {e}")
            return False
    
    def _deploy_remote(self, package_path: Path, target_host: str, target_dir: str) -> bool:
        """Deploy to remote host"""
        try:
            # Copy package to remote
            scp_cmd = f"scp {package_path} {target_host}:/tmp/"
            subprocess.run(scp_cmd, shell=True, check=True)
            
            # Extract on remote
            package_name = package_path.name
            ssh_cmd = f"ssh {target_host} 'cd /tmp && tar -xzf {package_name} -C {target_dir}'"
            subprocess.run(ssh_cmd, shell=True, check=True)
            
            logger.info(f"Package deployed to {target_host}:{target_dir}")
            return True
            
        except subprocess.CalledProcessError as e:
            logger.error(f"Remote deployment failed: {e}")
            return False
    
    def rollback(self, version: str, target_dir: str = "/opt/ecdis-planner") -> bool:
        """
        Rollback to previous version.
        
        Args:
            version: Version to rollback to
            target_dir: Target directory
            
        Returns:
            Success status
        """
        logger.info(f"Rolling back to version {version}")
        
        # Find package for version
        package_pattern = f"ecdis-planner-{version}-*.tar.gz"
        packages = list(self.dist_dir.glob(package_pattern))
        
        if not packages:
            logger.error(f"No package found for version {version}")
            return False
        
        # Deploy the package
        return self._deploy_local(packages[0], target_dir)
    
    def generate_deployment_script(self, environment: Environment) -> str:
        """Generate deployment script"""
        lines = []
        lines.append("#!/usr/bin/env bash\n")
        lines.append("# ECDIS Route Planner Deployment Script\n")
        lines.append(f"# Environment: {environment.value}\n")
        lines.append("set -euo pipefail\n\n")
        
        lines.append("# Configuration\n")
        lines.append(f"ENVIRONMENT={environment.value}\n")
        lines.append("TARGET_DIR=/opt/ecdis-planner\n")
        lines.append("SERVICE_NAME=ecdis-planner\n\n")
        
        lines.append("# Check prerequisites\n")
        lines.append("command -v python3 >/dev/null 2>&1 || { echo 'Python 3 required'; exit 1; }\n")
        lines.append("command -v pip3 >/dev/null 2>&1 || { echo 'pip3 required'; exit 1; }\n\n")
        
        lines.append("# Stop service if running\n")
        lines.append("if systemctl is-active --quiet $SERVICE_NAME; then\n")
        lines.append("    echo 'Stopping service...'\n")
        lines.append("    sudo systemctl stop $SERVICE_NAME\n")
        lines.append("fi\n\n")
        
        lines.append("# Backup current installation\n")
        lines.append("if [ -d $TARGET_DIR ]; then\n")
        lines.append("    echo 'Backing up current installation...'\n")
        lines.append("    sudo mv $TARGET_DIR ${TARGET_DIR}.backup.$(date +%Y%m%d_%H%M%S)\n")
        lines.append("fi\n\n")
        
        lines.append("# Extract package\n")
        lines.append("echo 'Extracting package...'\n")
        lines.append("sudo tar -xzf $1 -C /opt/\n\n")
        
        lines.append("# Install dependencies\n")
        lines.append("echo 'Installing dependencies...'\n")
        lines.append("cd $TARGET_DIR\n")
        lines.append("sudo pip3 install -r requirements.txt\n\n")
        
        lines.append("# Set up configuration\n")
        lines.append("echo 'Setting up configuration...'\n")
        lines.append("sudo cp config/${ENVIRONMENT}.json config/active.json\n\n")
        
        lines.append("# Run tests\n")
        lines.append("echo 'Running tests...'\n")
        lines.append("python3 -m pytest tests/ -q\n\n")
        
        lines.append("# Start service\n")
        lines.append("echo 'Starting service...'\n")
        lines.append("sudo systemctl start $SERVICE_NAME\n")
        lines.append("sudo systemctl enable $SERVICE_NAME\n\n")
        
        lines.append("echo 'Deployment complete!'\n")
        
        return "".join(lines)


class ServiceManager:
    """Manages system service configuration"""
    
    @staticmethod
    def generate_systemd_service() -> str:
        """Generate systemd service file"""
        lines = []
        lines.append("[Unit]\n")
        lines.append("Description=ECDIS Route Planner Service\n")
        lines.append("After=network.target\n\n")
        
        lines.append("[Service]\n")
        lines.append("Type=simple\n")
        lines.append("User=ecdis\n")
        lines.append("Group=ecdis\n")
        lines.append("WorkingDirectory=/opt/ecdis-planner\n")
        lines.append("ExecStart=/usr/bin/python3 -m lib.main\n")
        lines.append("Restart=always\n")
        lines.append("RestartSec=10\n\n")
        
        lines.append("# Security\n")
        lines.append("NoNewPrivileges=true\n")
        lines.append("PrivateTmp=true\n")
        lines.append("ProtectSystem=strict\n")
        lines.append("ProtectHome=true\n")
        lines.append("ReadWritePaths=/opt/ecdis-planner/logs /tmp/ecdis_cache\n\n")
        
        lines.append("[Install]\n")
        lines.append("WantedBy=multi-user.target\n")
        
        return "".join(lines)
    
    @staticmethod
    def generate_docker_compose() -> str:
        """Generate docker-compose.yml"""
        lines = []
        lines.append("version: '3.8'\n\n")
        
        lines.append("services:\n")
        lines.append("  ecdis-planner:\n")
        lines.append("    build: .\n")
        lines.append("    image: ecdis-planner:latest\n")
        lines.append("    container_name: ecdis-planner\n")
        lines.append("    restart: unless-stopped\n")
        lines.append("    environment:\n")
        lines.append("      - ECDIS_ENV=production\n")
        lines.append("      - ECDIS_DB_HOST=db\n")
        lines.append("    volumes:\n")
        lines.append("      - ./config:/app/config\n")
        lines.append("      - ./logs:/app/logs\n")
        lines.append("      - cache:/app/cache\n")
        lines.append("    ports:\n")
        lines.append("      - '8080:8080'\n")
        lines.append("    depends_on:\n")
        lines.append("      - db\n\n")
        
        lines.append("  db:\n")
        lines.append("    image: postgres:13\n")
        lines.append("    container_name: ecdis-db\n")
        lines.append("    restart: unless-stopped\n")
        lines.append("    environment:\n")
        lines.append("      - POSTGRES_DB=ecdis_planner\n")
        lines.append("      - POSTGRES_USER=ecdis_user\n")
        lines.append("      - POSTGRES_PASSWORD=changeme\n")
        lines.append("    volumes:\n")
        lines.append("      - db_data:/var/lib/postgresql/data\n\n")
        
        lines.append("volumes:\n")
        lines.append("  cache:\n")
        lines.append("  db_data:\n")
        
        return "".join(lines)