"""
Configuration Management System
Handles environment-specific configurations
"""

import os
import json
import yaml
from dataclasses import dataclass, field, asdict
from typing import Dict, Any, Optional, List
from pathlib import Path
from enum import Enum
import logging

logger = logging.getLogger(__name__)


class Environment(Enum):
    """Deployment environments"""
    DEVELOPMENT = "development"
    TESTING = "testing"
    STAGING = "staging"
    PRODUCTION = "production"


@dataclass
class DatabaseConfig:
    """Database configuration"""
    host: str = "localhost"
    port: int = 5432
    database: str = "ecdis_planner"
    username: str = "ecdis_user"
    password: str = ""
    pool_size: int = 10
    timeout: int = 30


@dataclass
class CacheConfig:
    """Cache configuration"""
    enabled: bool = True
    type: str = "tiered"  # memory, disk, tiered
    memory_size_mb: float = 500.0
    disk_size_mb: float = 2000.0
    disk_path: str = "/tmp/ecdis_cache"
    ttl_seconds: int = 3600
    compression: bool = True


@dataclass
class PerformanceConfig:
    """Performance tuning configuration"""
    max_workers: int = 4
    batch_size: int = 100
    prefetch_radius: int = 2
    tile_size_deg: float = 1.0
    max_memory_mb: float = 4096.0
    enable_profiling: bool = False


@dataclass
class SafetyConfig:
    """Safety configuration"""
    min_ukc_m: float = 2.0
    safety_margin: float = 0.2
    max_response_time_ms: float = 100.0
    failover_enabled: bool = True
    degraded_mode_threshold: float = 0.7
    emergency_stop_enabled: bool = True


@dataclass
class LoggingConfig:
    """Logging configuration"""
    level: str = "INFO"
    format: str = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    file_enabled: bool = True
    file_path: str = "logs/ecdis_planner.log"
    max_size_mb: int = 100
    backup_count: int = 5
    console_enabled: bool = True


@dataclass
class FeatureFlags:
    """Feature flags for gradual rollout"""
    colreg_enabled: bool = True
    four_d_planner: bool = True
    s104_tides: bool = True
    eta_optimizer: bool = True
    ukc_plugin: bool = True
    safety_shield: bool = True
    sensor_failover: bool = True
    fault_injection: bool = False
    tile_management: bool = True
    cache_strategy: bool = True
    dynamic_loading: bool = True
    prefetch: bool = True


@dataclass
class AppConfig:
    """Complete application configuration"""
    environment: Environment
    database: DatabaseConfig = field(default_factory=DatabaseConfig)
    cache: CacheConfig = field(default_factory=CacheConfig)
    performance: PerformanceConfig = field(default_factory=PerformanceConfig)
    safety: SafetyConfig = field(default_factory=SafetyConfig)
    logging: LoggingConfig = field(default_factory=LoggingConfig)
    feature_flags: FeatureFlags = field(default_factory=FeatureFlags)
    custom: Dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary"""
        data = asdict(self)
        data['environment'] = self.environment.value
        return data
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'AppConfig':
        """Create from dictionary"""
        # Convert environment string to enum
        env = Environment(data.get('environment', 'development'))
        
        # Create nested configs
        config = cls(
            environment=env,
            database=DatabaseConfig(**data.get('database', {})),
            cache=CacheConfig(**data.get('cache', {})),
            performance=PerformanceConfig(**data.get('performance', {})),
            safety=SafetyConfig(**data.get('safety', {})),
            logging=LoggingConfig(**data.get('logging', {})),
            feature_flags=FeatureFlags(**data.get('feature_flags', {})),
            custom=data.get('custom', {})
        )
        
        return config


class ConfigManager:
    """Manages application configuration"""
    
    def __init__(self, 
                 config_dir: Optional[Path] = None,
                 environment: Optional[str] = None):
        """
        Initialize configuration manager.
        
        Args:
            config_dir: Configuration directory
            environment: Environment name
        """
        self.config_dir = config_dir or Path("config")
        self.environment = Environment(environment or os.getenv('ECDIS_ENV', 'development'))
        
        # Configuration files
        self.default_config_file = self.config_dir / "default.json"
        self.env_config_file = self.config_dir / f"{self.environment.value}.json"
        self.secrets_file = self.config_dir / ".secrets.json"
        
        # Load configuration
        self.config = self._load_config()
        
        logger.info(f"Configuration loaded for environment: {self.environment.value}")
    
    def _load_config(self) -> AppConfig:
        """Load configuration from files"""
        # Start with defaults
        config_data = self._get_default_config()
        
        # Load default config file if exists
        if self.default_config_file.exists():
            with open(self.default_config_file, 'r') as f:
                default_data = json.load(f)
                config_data = self._merge_configs(config_data, default_data)
        
        # Load environment-specific config
        if self.env_config_file.exists():
            with open(self.env_config_file, 'r') as f:
                env_data = json.load(f)
                config_data = self._merge_configs(config_data, env_data)
        
        # Load secrets (never commit this file)
        if self.secrets_file.exists():
            with open(self.secrets_file, 'r') as f:
                secrets_data = json.load(f)
                config_data = self._merge_configs(config_data, secrets_data)
        
        # Override with environment variables
        config_data = self._apply_env_overrides(config_data)
        
        # Create config object
        return AppConfig.from_dict(config_data)
    
    def _get_default_config(self) -> Dict[str, Any]:
        """Get default configuration"""
        return {
            'environment': self.environment.value,
            'database': asdict(DatabaseConfig()),
            'cache': asdict(CacheConfig()),
            'performance': asdict(PerformanceConfig()),
            'safety': asdict(SafetyConfig()),
            'logging': asdict(LoggingConfig()),
            'feature_flags': asdict(FeatureFlags())
        }
    
    def _merge_configs(self, base: Dict[str, Any], override: Dict[str, Any]) -> Dict[str, Any]:
        """Merge configuration dictionaries"""
        result = base.copy()
        
        for key, value in override.items():
            if key in result and isinstance(result[key], dict) and isinstance(value, dict):
                # Recursive merge for nested dicts
                result[key] = self._merge_configs(result[key], value)
            else:
                result[key] = value
        
        return result
    
    def _apply_env_overrides(self, config_data: Dict[str, Any]) -> Dict[str, Any]:
        """Apply environment variable overrides"""
        # Database overrides
        if 'ECDIS_DB_HOST' in os.environ:
            config_data['database']['host'] = os.environ['ECDIS_DB_HOST']
        if 'ECDIS_DB_PORT' in os.environ:
            config_data['database']['port'] = int(os.environ['ECDIS_DB_PORT'])
        if 'ECDIS_DB_PASSWORD' in os.environ:
            config_data['database']['password'] = os.environ['ECDIS_DB_PASSWORD']
        
        # Cache overrides
        if 'ECDIS_CACHE_SIZE' in os.environ:
            config_data['cache']['memory_size_mb'] = float(os.environ['ECDIS_CACHE_SIZE'])
        
        # Performance overrides
        if 'ECDIS_MAX_WORKERS' in os.environ:
            config_data['performance']['max_workers'] = int(os.environ['ECDIS_MAX_WORKERS'])
        
        # Feature flag overrides (ECDIS_FEATURE_*)
        for key, value in os.environ.items():
            if key.startswith('ECDIS_FEATURE_'):
                feature_name = key[14:].lower()  # Remove prefix
                if feature_name in config_data['feature_flags']:
                    config_data['feature_flags'][feature_name] = value.lower() == 'true'
        
        return config_data
    
    def save_config(self, filepath: Optional[Path] = None):
        """Save current configuration to file"""
        if filepath is None:
            filepath = self.env_config_file
        
        # Ensure directory exists
        filepath.parent.mkdir(parents=True, exist_ok=True)
        
        # Save as JSON
        with open(filepath, 'w') as f:
            json.dump(self.config.to_dict(), f, indent=2)
        
        logger.info(f"Configuration saved to {filepath}")
    
    def get(self, key: str, default: Any = None) -> Any:
        """Get configuration value by dot-notation key"""
        # Support dot notation (e.g., "database.host")
        keys = key.split('.')
        value = self.config.to_dict()
        
        for k in keys:
            if isinstance(value, dict) and k in value:
                value = value[k]
            else:
                return default
        
        return value
    
    def set(self, key: str, value: Any):
        """Set configuration value by dot-notation key"""
        keys = key.split('.')
        
        # Navigate to parent
        config_dict = self.config.to_dict()
        current = config_dict
        
        for k in keys[:-1]:
            if k not in current:
                current[k] = {}
            current = current[k]
        
        # Set value
        current[keys[-1]] = value
        
        # Recreate config object
        self.config = AppConfig.from_dict(config_dict)
    
    def is_feature_enabled(self, feature: str) -> bool:
        """Check if feature flag is enabled"""
        return getattr(self.config.feature_flags, feature, False)
    
    def get_environment_configs(self) -> Dict[Environment, AppConfig]:
        """Load all environment configurations"""
        configs = {}
        
        for env in Environment:
            env_file = self.config_dir / f"{env.value}.json"
            if env_file.exists():
                with open(env_file, 'r') as f:
                    data = json.load(f)
                    configs[env] = AppConfig.from_dict(data)
        
        return configs
    
    def validate_config(self) -> List[str]:
        """Validate current configuration"""
        issues = []
        
        # Check required fields
        if not self.config.database.host:
            issues.append("Database host is not configured")
        
        # Check value ranges
        if self.config.performance.max_workers < 1:
            issues.append("max_workers must be at least 1")
        
        if self.config.cache.memory_size_mb < 0:
            issues.append("cache memory_size_mb cannot be negative")
        
        if self.config.safety.min_ukc_m < 0:
            issues.append("min_ukc_m cannot be negative")
        
        # Check paths
        cache_path = Path(self.config.cache.disk_path)
        if self.config.cache.type in ['disk', 'tiered'] and not cache_path.parent.exists():
            issues.append(f"Cache directory parent does not exist: {cache_path.parent}")
        
        return issues
    
    def generate_env_template(self) -> str:
        """Generate environment variable template"""
        lines = []
        lines.append("# ECDIS Route Planner Environment Variables\n")
        lines.append("# Copy to .env and fill in values\n\n")
        
        lines.append("# Environment\n")
        lines.append("ECDIS_ENV=development\n\n")
        
        lines.append("# Database\n")
        lines.append("ECDIS_DB_HOST=localhost\n")
        lines.append("ECDIS_DB_PORT=5432\n")
        lines.append("ECDIS_DB_PASSWORD=\n\n")
        
        lines.append("# Cache\n")
        lines.append("ECDIS_CACHE_SIZE=500\n\n")
        
        lines.append("# Performance\n")
        lines.append("ECDIS_MAX_WORKERS=4\n\n")
        
        lines.append("# Feature Flags\n")
        for flag in asdict(FeatureFlags()).keys():
            lines.append(f"ECDIS_FEATURE_{flag.upper()}=true\n")
        
        return "".join(lines)