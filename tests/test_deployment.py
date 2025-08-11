"""
Tests for Deployment and Release Management
"""

import os
import json
import tarfile
import pytest
from pathlib import Path
from datetime import datetime
from unittest.mock import MagicMock, patch, call

from lib.governance.deployment import (
    DeploymentPackage, DeploymentManager, ServiceManager
)
from lib.governance.version_manager import Version
from lib.governance.config_manager import Environment


class TestDeploymentPackage:
    """Test DeploymentPackage dataclass"""
    
    def test_package_creation(self):
        """Test deployment package creation"""
        package = DeploymentPackage(
            version=Version(1, 0, 0),
            environment=Environment.PRODUCTION,
            created_at=datetime.now(),
            files=[Path("file1.py"), Path("file2.py")],
            checksums={"file1.py": "hash1", "file2.py": "hash2"},
            metadata={"author": "test"}
        )
        
        assert str(package.version) == "1.0.0"
        assert package.environment == Environment.PRODUCTION
        assert len(package.files) == 2
        assert len(package.checksums) == 2


class TestDeploymentManager:
    """Test DeploymentManager class"""
    
    @pytest.fixture
    def temp_project(self, tmp_path):
        """Create temporary project structure"""
        # Create directories
        (tmp_path / "lib").mkdir()
        (tmp_path / "lib" / "planner").mkdir()
        (tmp_path / "scripts").mkdir()
        (tmp_path / "config").mkdir()
        (tmp_path / "tests").mkdir()
        
        # Create sample files
        (tmp_path / "lib" / "planner" / "planner.py").write_text("# Planner code")
        (tmp_path / "scripts" / "run.py").write_text("# Run script")
        (tmp_path / "scripts" / "deploy.sh").write_text("#!/bin/bash")
        (tmp_path / "config" / "default.json").write_text("{}")
        (tmp_path / "tests" / "test_sample.py").write_text("# Test")
        (tmp_path / "README.md").write_text("# README")
        (tmp_path / "SYSTEM_ARCHITECTURE.md").write_text("# Architecture")
        (tmp_path / "DEVELOPMENT_LOG.md").write_text("# Log")
        
        return tmp_path
    
    def test_deployment_manager_init(self, temp_project):
        """Test deployment manager initialization"""
        dm = DeploymentManager(temp_project)
        
        assert dm.project_root == temp_project
        assert dm.dist_dir.exists()
        assert dm.build_dir.exists()
    
    def test_collect_files(self, temp_project):
        """Test file collection"""
        dm = DeploymentManager(temp_project)
        
        # Collect without tests
        files = dm._collect_files(include_tests=False)
        file_paths = [f.relative_to(temp_project) for f in files]
        
        assert any("planner.py" in str(p) for p in file_paths)
        assert any("run.py" in str(p) for p in file_paths)
        assert any("README.md" in str(p) for p in file_paths)
        assert not any("test_sample.py" in str(p) for p in file_paths)
        
        # Collect with tests
        files = dm._collect_files(include_tests=True)
        file_paths = [f.relative_to(temp_project) for f in files]
        assert any("test_sample.py" in str(p) for p in file_paths)
    
    def test_generate_checksums(self, temp_project):
        """Test checksum generation"""
        dm = DeploymentManager(temp_project)
        
        files = [
            temp_project / "lib" / "planner" / "planner.py",
            temp_project / "README.md"
        ]
        
        checksums = dm._generate_checksums(files)
        
        assert "lib/planner/planner.py" in checksums
        assert "README.md" in checksums
        assert all(len(h) == 64 for h in checksums.values())  # SHA256
    
    def test_create_package(self, temp_project):
        """Test package creation"""
        dm = DeploymentManager(temp_project)
        
        package = dm.create_package(
            environment=Environment.STAGING,
            include_tests=False
        )
        
        assert package.environment == Environment.STAGING
        assert package.version == dm.version_manager.current_version
        assert len(package.files) > 0
        assert len(package.checksums) > 0
        
        # Check manifest was created
        manifest_file = dm.build_dir / "MANIFEST.json"
        assert manifest_file.exists()
        
        # Check archive was created
        archive_name = f"ecdis-planner-{package.version}-staging.tar.gz"
        archive_path = dm.dist_dir / archive_name
        assert archive_path.exists()
    
    def test_save_manifest(self, temp_project):
        """Test manifest saving"""
        dm = DeploymentManager(temp_project)
        
        package = DeploymentPackage(
            version=Version(1, 2, 3),
            environment=Environment.PRODUCTION,
            created_at=datetime.now(),
            files=[],
            checksums={"file.py": "hash123"},
            metadata={"test": True}
        )
        
        dm._save_manifest(package)
        
        manifest_file = dm.build_dir / "MANIFEST.json"
        assert manifest_file.exists()
        
        with open(manifest_file, 'r') as f:
            data = json.load(f)
            assert data['version'] == "1.2.3"
            assert data['environment'] == "production"
            assert data['checksums']['file.py'] == "hash123"
    
    def test_create_archive(self, temp_project):
        """Test archive creation"""
        dm = DeploymentManager(temp_project)
        
        # Create some content in build dir
        (dm.build_dir / "test.txt").write_text("test content")
        
        package = DeploymentPackage(
            version=Version(1, 0, 0),
            environment=Environment.TESTING,
            created_at=datetime.now(),
            files=[],
            checksums={},
            metadata={}
        )
        
        archive_path = dm._create_archive(package)
        
        assert archive_path.exists()
        assert archive_path.name == "ecdis-planner-1.0.0-testing.tar.gz"
        
        # Verify archive contents
        with tarfile.open(archive_path, 'r:gz') as tar:
            names = tar.getnames()
            assert any("test.txt" in name for name in names)
    
    @patch('subprocess.run')
    def test_deploy_local(self, mock_run, temp_project):
        """Test local deployment"""
        dm = DeploymentManager(temp_project)
        
        # Create a test package
        package_path = dm.dist_dir / "test-package.tar.gz"
        with tarfile.open(package_path, 'w:gz') as tar:
            tar.add(dm.build_dir, arcname="ecdis-planner")
        
        target_dir = temp_project / "deployed"
        
        result = dm._deploy_local(package_path, str(target_dir))
        
        assert result == True
    
    @patch('subprocess.run')
    def test_deploy_remote(self, mock_run, temp_project):
        """Test remote deployment"""
        dm = DeploymentManager(temp_project)
        
        package_path = dm.dist_dir / "test-package.tar.gz"
        package_path.touch()
        
        result = dm._deploy_remote(
            package_path,
            "user@host",
            "/opt/ecdis"
        )
        
        assert result == True
        assert mock_run.call_count == 2  # scp and ssh
    
    def test_rollback(self, temp_project):
        """Test rollback to previous version"""
        dm = DeploymentManager(temp_project)
        
        # Create package for version
        package_path = dm.dist_dir / "ecdis-planner-0.9.0-production.tar.gz"
        with tarfile.open(package_path, 'w:gz') as tar:
            tar.add(dm.build_dir, arcname="ecdis-planner")
        
        with patch.object(dm, '_deploy_local', return_value=True) as mock_deploy:
            result = dm.rollback("0.9.0")
            
            assert result == True
            mock_deploy.assert_called_once()
    
    def test_generate_deployment_script(self, temp_project):
        """Test deployment script generation"""
        dm = DeploymentManager(temp_project)
        
        script = dm.generate_deployment_script(Environment.PRODUCTION)
        
        assert "#!/usr/bin/env bash" in script
        assert "ENVIRONMENT=production" in script
        assert "systemctl stop" in script
        assert "tar -xzf" in script
        assert "pip3 install" in script
        assert "systemctl start" in script


class TestServiceManager:
    """Test ServiceManager class"""
    
    def test_generate_systemd_service(self):
        """Test systemd service file generation"""
        service = ServiceManager.generate_systemd_service()
        
        assert "[Unit]" in service
        assert "Description=ECDIS Route Planner Service" in service
        assert "[Service]" in service
        assert "ExecStart=/usr/bin/python3 -m lib.main" in service
        assert "Restart=always" in service
        assert "[Install]" in service
        assert "WantedBy=multi-user.target" in service
        
        # Security settings
        assert "NoNewPrivileges=true" in service
        assert "PrivateTmp=true" in service
        assert "ProtectSystem=strict" in service
    
    def test_generate_docker_compose(self):
        """Test docker-compose.yml generation"""
        compose = ServiceManager.generate_docker_compose()
        
        assert "version: '3.8'" in compose
        assert "services:" in compose
        assert "ecdis-planner:" in compose
        assert "image: ecdis-planner:latest" in compose
        assert "restart: unless-stopped" in compose
        
        # Database service
        assert "db:" in compose
        assert "image: postgres:13" in compose
        assert "POSTGRES_DB=ecdis_planner" in compose
        
        # Volumes
        assert "volumes:" in compose
        assert "cache:" in compose
        assert "db_data:" in compose


class TestIntegration:
    """Integration tests for deployment workflow"""
    
    @pytest.fixture
    def full_project(self, tmp_path):
        """Create full project structure"""
        # Create complete directory structure
        dirs = [
            "lib/planner", "lib/checks", "lib/enc",
            "scripts", "config", "tests", "logs"
        ]
        
        for dir_path in dirs:
            (tmp_path / dir_path).mkdir(parents=True)
        
        # Create various files
        files = {
            "lib/planner/planner.py": "# Planner",
            "lib/checks/checker.py": "# Checker",
            "scripts/run.py": "# Run",
            "config/production.json": "{}",
            "tests/test_all.py": "# Tests",
            "README.md": "# Project",
            "VERSION": "1.0.0"
        }
        
        for file_path, content in files.items():
            (tmp_path / file_path).write_text(content)
        
        return tmp_path
    
    def test_full_deployment_workflow(self, full_project):
        """Test complete deployment workflow"""
        dm = DeploymentManager(full_project)
        
        # 1. Create deployment package
        package = dm.create_package(
            environment=Environment.PRODUCTION,
            include_tests=False
        )
        
        assert package is not None
        assert package.environment == Environment.PRODUCTION
        
        # 2. Verify package contents
        archive_name = f"ecdis-planner-{package.version}-production.tar.gz"
        archive_path = dm.dist_dir / archive_name
        
        with tarfile.open(archive_path, 'r:gz') as tar:
            names = tar.getnames()
            assert any("planner.py" in name for name in names)
            assert any("MANIFEST.json" in name for name in names)
        
        # 3. Generate deployment script
        script = dm.generate_deployment_script(Environment.PRODUCTION)
        assert "ENVIRONMENT=production" in script
        
        # 4. Generate service files
        systemd = ServiceManager.generate_systemd_service()
        assert "Type=simple" in systemd
        
        docker = ServiceManager.generate_docker_compose()
        assert "container_name: ecdis-planner" in docker
    
    def test_environment_specific_deployment(self, full_project):
        """Test deployment for different environments"""
        dm = DeploymentManager(full_project)
        
        environments = [
            Environment.DEVELOPMENT,
            Environment.STAGING,
            Environment.PRODUCTION
        ]
        
        for env in environments:
            package = dm.create_package(
                environment=env,
                include_tests=(env == Environment.DEVELOPMENT)
            )
            
            archive_name = f"ecdis-planner-{package.version}-{env.value}.tar.gz"
            archive_path = dm.dist_dir / archive_name
            
            assert archive_path.exists()
            
            # Verify environment-specific script
            script = dm.generate_deployment_script(env)
            assert f"ENVIRONMENT={env.value}" in script