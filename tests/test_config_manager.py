"""
Tests for Configuration Management System
"""

import os
import json
import pytest
from pathlib import Path
from unittest.mock import patch

from lib.governance.config_manager import (
    Environment, DatabaseConfig, CacheConfig, PerformanceConfig,
    SafetyConfig, LoggingConfig, FeatureFlags, AppConfig, ConfigManager
)


class TestEnvironment:
    """Test Environment enum"""
    
    def test_environment_values(self):
        """Test environment enum values"""
        assert Environment.DEVELOPMENT.value == "development"
        assert Environment.TESTING.value == "testing"
        assert Environment.STAGING.value == "staging"
        assert Environment.PRODUCTION.value == "production"


class TestDatabaseConfig:
    """Test DatabaseConfig dataclass"""
    
    def test_default_values(self):
        """Test default database config values"""
        config = DatabaseConfig()
        assert config.host == "localhost"
        assert config.port == 5432
        assert config.database == "ecdis_planner"
        assert config.pool_size == 10
    
    def test_custom_values(self):
        """Test custom database config values"""
        config = DatabaseConfig(
            host="db.example.com",
            port=5433,
            password="secret"
        )
        assert config.host == "db.example.com"
        assert config.port == 5433
        assert config.password == "secret"


class TestCacheConfig:
    """Test CacheConfig dataclass"""
    
    def test_default_values(self):
        """Test default cache config values"""
        config = CacheConfig()
        assert config.enabled == True
        assert config.type == "tiered"
        assert config.memory_size_mb == 500.0
        assert config.disk_size_mb == 2000.0
        assert config.compression == True


class TestPerformanceConfig:
    """Test PerformanceConfig dataclass"""
    
    def test_default_values(self):
        """Test default performance config values"""
        config = PerformanceConfig()
        assert config.max_workers == 4
        assert config.batch_size == 100
        assert config.tile_size_deg == 1.0
        assert config.enable_profiling == False


class TestSafetyConfig:
    """Test SafetyConfig dataclass"""
    
    def test_default_values(self):
        """Test default safety config values"""
        config = SafetyConfig()
        assert config.min_ukc_m == 2.0
        assert config.safety_margin == 0.2
        assert config.failover_enabled == True
        assert config.emergency_stop_enabled == True


class TestFeatureFlags:
    """Test FeatureFlags dataclass"""
    
    def test_default_values(self):
        """Test default feature flags"""
        flags = FeatureFlags()
        assert flags.colreg_enabled == True
        assert flags.four_d_planner == True
        assert flags.fault_injection == False  # Disabled by default
        assert flags.tile_management == True


class TestAppConfig:
    """Test AppConfig dataclass"""
    
    def test_creation(self):
        """Test app config creation"""
        config = AppConfig(environment=Environment.PRODUCTION)
        
        assert config.environment == Environment.PRODUCTION
        assert isinstance(config.database, DatabaseConfig)
        assert isinstance(config.cache, CacheConfig)
        assert isinstance(config.feature_flags, FeatureFlags)
    
    def test_to_dict(self):
        """Test conversion to dictionary"""
        config = AppConfig(environment=Environment.STAGING)
        data = config.to_dict()
        
        assert data['environment'] == 'staging'
        assert 'database' in data
        assert 'cache' in data
        assert 'feature_flags' in data
    
    def test_from_dict(self):
        """Test creation from dictionary"""
        data = {
            'environment': 'production',
            'database': {'host': 'prod.db', 'port': 5432},
            'cache': {'memory_size_mb': 1000},
            'feature_flags': {'fault_injection': True}
        }
        
        config = AppConfig.from_dict(data)
        
        assert config.environment == Environment.PRODUCTION
        assert config.database.host == 'prod.db'
        assert config.cache.memory_size_mb == 1000
        assert config.feature_flags.fault_injection == True


class TestConfigManager:
    """Test ConfigManager class"""
    
    @pytest.fixture
    def temp_config_dir(self, tmp_path):
        """Create temporary config directory"""
        config_dir = tmp_path / "config"
        config_dir.mkdir()
        return config_dir
    
    def test_init_default(self, temp_config_dir):
        """Test initialization with defaults"""
        with patch.dict(os.environ, {}, clear=True):
            cm = ConfigManager(config_dir=temp_config_dir)
            
            assert cm.environment == Environment.DEVELOPMENT
            assert cm.config.environment == Environment.DEVELOPMENT
    
    def test_init_with_env_var(self, temp_config_dir):
        """Test initialization with environment variable"""
        with patch.dict(os.environ, {'ECDIS_ENV': 'production'}):
            cm = ConfigManager(config_dir=temp_config_dir)
            
            assert cm.environment == Environment.PRODUCTION
    
    def test_load_default_config(self, temp_config_dir):
        """Test loading default config file"""
        # Create default config
        default_config = {
            'database': {'host': 'default.db'},
            'cache': {'memory_size_mb': 100}
        }
        
        with open(temp_config_dir / "default.json", 'w') as f:
            json.dump(default_config, f)
        
        cm = ConfigManager(config_dir=temp_config_dir)
        
        assert cm.config.database.host == 'default.db'
        assert cm.config.cache.memory_size_mb == 100
    
    def test_load_env_specific_config(self, temp_config_dir):
        """Test loading environment-specific config"""
        # Create staging config
        staging_config = {
            'database': {'host': 'staging.db'},
            'performance': {'max_workers': 8}
        }
        
        with open(temp_config_dir / "staging.json", 'w') as f:
            json.dump(staging_config, f)
        
        cm = ConfigManager(config_dir=temp_config_dir, environment='staging')
        
        assert cm.config.database.host == 'staging.db'
        assert cm.config.performance.max_workers == 8
    
    def test_env_overrides(self, temp_config_dir):
        """Test environment variable overrides"""
        env_vars = {
            'ECDIS_DB_HOST': 'env.db',
            'ECDIS_DB_PORT': '5433',
            'ECDIS_CACHE_SIZE': '750',
            'ECDIS_MAX_WORKERS': '16',
            'ECDIS_FEATURE_FAULT_INJECTION': 'true'
        }
        
        with patch.dict(os.environ, env_vars):
            cm = ConfigManager(config_dir=temp_config_dir)
            
            assert cm.config.database.host == 'env.db'
            assert cm.config.database.port == 5433
            assert cm.config.cache.memory_size_mb == 750
            assert cm.config.performance.max_workers == 16
            assert cm.config.feature_flags.fault_injection == True
    
    def test_get_value(self, temp_config_dir):
        """Test getting config value by key"""
        cm = ConfigManager(config_dir=temp_config_dir)
        
        # Test dot notation
        assert cm.get('database.host') == 'localhost'
        assert cm.get('cache.enabled') == True
        assert cm.get('non.existent', 'default') == 'default'
    
    def test_set_value(self, temp_config_dir):
        """Test setting config value by key"""
        cm = ConfigManager(config_dir=temp_config_dir)
        
        cm.set('database.host', 'new.db')
        cm.set('cache.memory_size_mb', 1500)
        
        assert cm.config.database.host == 'new.db'
        assert cm.config.cache.memory_size_mb == 1500
    
    def test_is_feature_enabled(self, temp_config_dir):
        """Test feature flag checking"""
        cm = ConfigManager(config_dir=temp_config_dir)
        
        assert cm.is_feature_enabled('colreg_enabled') == True
        assert cm.is_feature_enabled('fault_injection') == False
        assert cm.is_feature_enabled('non_existent') == False
    
    def test_save_config(self, temp_config_dir):
        """Test saving configuration"""
        cm = ConfigManager(config_dir=temp_config_dir)
        
        # Modify config
        cm.set('database.host', 'saved.db')
        
        # Save config
        cm.save_config()
        
        # Check file exists
        env_file = temp_config_dir / f"{cm.environment.value}.json"
        assert env_file.exists()
        
        # Load and verify
        with open(env_file, 'r') as f:
            data = json.load(f)
            assert data['database']['host'] == 'saved.db'
    
    def test_validate_config(self, temp_config_dir):
        """Test configuration validation"""
        cm = ConfigManager(config_dir=temp_config_dir)
        
        # Valid config
        issues = cm.validate_config()
        assert len(issues) == 0
        
        # Invalid config
        cm.config.performance.max_workers = 0
        cm.config.cache.memory_size_mb = -100
        cm.config.safety.min_ukc_m = -1
        
        issues = cm.validate_config()
        assert len(issues) >= 3
        assert any("max_workers" in issue for issue in issues)
        assert any("memory_size_mb" in issue for issue in issues)
        assert any("min_ukc_m" in issue for issue in issues)
    
    def test_get_environment_configs(self, temp_config_dir):
        """Test loading all environment configs"""
        # Create configs for different environments
        for env in ['development', 'staging', 'production']:
            config = {
                'environment': env,
                'database': {'host': f'{env}.db'}
            }
            with open(temp_config_dir / f"{env}.json", 'w') as f:
                json.dump(config, f)
        
        cm = ConfigManager(config_dir=temp_config_dir)
        configs = cm.get_environment_configs()
        
        assert len(configs) >= 3
        assert Environment.DEVELOPMENT in configs
        assert Environment.PRODUCTION in configs
    
    def test_generate_env_template(self, temp_config_dir):
        """Test environment template generation"""
        cm = ConfigManager(config_dir=temp_config_dir)
        
        template = cm.generate_env_template()
        
        assert "ECDIS_ENV=" in template
        assert "ECDIS_DB_HOST=" in template
        assert "ECDIS_FEATURE_COLREG_ENABLED=" in template
    
    def test_merge_configs(self, temp_config_dir):
        """Test configuration merging"""
        cm = ConfigManager(config_dir=temp_config_dir)
        
        base = {
            'database': {'host': 'base', 'port': 5432},
            'cache': {'enabled': True}
        }
        
        override = {
            'database': {'host': 'override'},
            'cache': {'memory_size_mb': 1000},
            'new_key': 'new_value'
        }
        
        result = cm._merge_configs(base, override)
        
        assert result['database']['host'] == 'override'
        assert result['database']['port'] == 5432  # Preserved
        assert result['cache']['enabled'] == True  # Preserved
        assert result['cache']['memory_size_mb'] == 1000  # Added
        assert result['new_key'] == 'new_value'  # Added