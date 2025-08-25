"""
Configuration management system for the translation bot.
Handles environment variables, validation, and settings.
"""

import os
import logging
from typing import List, Optional, Dict, Any
from pydantic import BaseSettings, Field, validator
from enum import Enum

logger = logging.getLogger(__name__)

class Environment(str, Enum):
    DEVELOPMENT = "development"
    STAGING = "staging"
    PRODUCTION = "production"

class LogLevel(str, Enum):
    DEBUG = "DEBUG"
    INFO = "INFO"
    WARNING = "WARNING"
    ERROR = "ERROR"
    CRITICAL = "CRITICAL"

class Settings(BaseSettings):
    """Application settings with validation"""
    
    # Environment
    environment: Environment = Field(default=Environment.DEVELOPMENT)
    debug: bool = Field(default=False)
    log_level: LogLevel = Field(default=LogLevel.INFO)
    
    # Bot Configuration
    bot_token: str = Field(..., description="Telegram Bot Token")
    webhook_url: Optional[str] = Field(default=None, description="Webhook URL for production")
    webhook_secret: Optional[str] = Field(default=None, description="Webhook secret token")
    max_workers: int = Field(default=4, ge=1, le=10)
    
    # API Keys (comma-separated for multiple keys)
    groq_keys: str = Field(..., description="Groq API keys (comma-separated) - Primary AI service")
    gemini_keys: str = Field(default="", description="Gemini API keys (comma-separated) - Optional fallback")
    openai_keys: str = Field(default="", description="OpenAI API keys (comma-separated) - Optional fallback")
    azure_keys: str = Field(default="", description="Azure API keys (comma-separated) - Optional fallback")
    
    # Database Configuration
    database_url: Optional[str] = Field(default=None, description="PostgreSQL database URL")
    redis_url: Optional[str] = Field(default=None, description="Redis cache URL")
    
    # Performance Settings
    max_file_size_mb: int = Field(default=20, ge=1, le=100)
    max_concurrent_translations: int = Field(default=10, ge=1, le=50)
    translation_timeout: int = Field(default=300, ge=30, le=600)
    queue_timeout: int = Field(default=1800, ge=300, le=3600)
    
    # Rate Limiting
    daily_limit_per_user: int = Field(default=50, ge=1, le=1000)
    concurrent_limit_per_user: int = Field(default=3, ge=1, le=10)
    
    # Cache Settings
    cache_ttl_seconds: int = Field(default=3600, ge=300, le=86400)
    cache_max_size: int = Field(default=1000, ge=100, le=10000)
    
    # Monitoring
    enable_metrics: bool = Field(default=True)
    metrics_port: int = Field(default=8090, ge=8000, le=9000)
    health_check_interval: int = Field(default=30, ge=10, le=300)
    
    @validator('bot_token')
    def validate_bot_token(cls, v):
        if not v or len(v) < 10:
            raise ValueError('Bot token must be provided and valid')
        return v
    
    @validator('webhook_url')
    def validate_webhook_url(cls, v, values):
        env = values.get('environment')
        if env == Environment.PRODUCTION and not v:
            raise ValueError('Webhook URL is required in production')
        if v and not v.startswith('https://'):
            raise ValueError('Webhook URL must use HTTPS')
        return v
    
    @validator('groq_keys')
    def validate_groq_keys(cls, v):
        if not v or len(v.strip()) == 0:
            raise ValueError('GROQ_KEYS is required as the primary AI translation service')
        return v
    
    @validator('environment')
    def validate_environment_settings(cls, v, values):
        if v == Environment.PRODUCTION:
            # Groq is required, others are optional fallbacks
            if not values.get('groq_keys'):
                raise ValueError('GROQ_KEYS is required in production')
            
            # Warn about optional fallback services
            optional_keys = ['gemini_keys', 'openai_keys', 'azure_keys']
            available_fallbacks = [key for key in optional_keys if values.get(key)]
            if not available_fallbacks:
                logger.warning('No fallback AI services configured - consider adding backup API keys')
        return v
    
    def get_api_keys(self, service: str) -> List[str]:
        """Get API keys for a specific service"""
        key_mapping = {
            'groq': self.groq_keys,     # Primary service
            'gemini': self.gemini_keys, # Fallback services
            'openai': self.openai_keys,
            'azure': self.azure_keys
        }
        
        keys_str = key_mapping.get(service, '')
        if not keys_str:
            return []
            
        return [key.strip() for key in keys_str.split(',') if key.strip()]
    
    def get_database_config(self) -> Optional[Dict[str, Any]]:
        """Get database configuration"""
        if not self.database_url:
            return None
            
        return {
            'url': self.database_url,
            'pool_size': 5,
            'max_overflow': 10,
            'pool_timeout': 30,
            'pool_recycle': 3600
        }
    
    def get_redis_config(self) -> Optional[Dict[str, Any]]:
        """Get Redis configuration"""
        if not self.redis_url:
            return None
            
        return {
            'url': self.redis_url,
            'encoding': 'utf-8',
            'decode_responses': True,
            'max_connections': 20,
            'retry_on_timeout': True
        }
    
    class Config:
        env_file = '.env'
        env_file_encoding = 'utf-8'
        case_sensitive = False
        
        # Environment variable prefixes
        env_prefix = ''
        
        # Field aliases for common environment variable names
        fields = {
            'bot_token': {'env': 'BOT_TOKEN'},
            'webhook_url': {'env': 'WEBHOOK_URL'},
            'webhook_secret': {'env': 'WEBHOOK_SECRET'},
            'groq_keys': {'env': 'GROQ_KEYS'},        # Primary service
            'gemini_keys': {'env': 'GEMINI_KEYS'},    # Optional fallbacks
            'openai_keys': {'env': 'OPENAI_KEYS'},
            'azure_keys': {'env': 'AZURE_KEYS'},
            'database_url': {'env': 'DATABASE_URL'},
            'redis_url': {'env': 'REDIS_URL'},
            'environment': {'env': 'ENVIRONMENT'},
            'log_level': {'env': 'LOG_LEVEL'},
            'max_workers': {'env': 'MAX_WORKERS'}
        }

def load_settings() -> Settings:
    """Load and validate application settings"""
    try:
        settings = Settings()
        logger.info(f"Settings loaded successfully for {settings.environment} environment")
        
        # Log configuration summary (without sensitive data)
        logger.info(f"Configuration summary:")
        logger.info(f"- Environment: {settings.environment}")
        logger.info(f"- Debug mode: {settings.debug}")
        logger.info(f"- Log level: {settings.log_level}")
        logger.info(f"- Max workers: {settings.max_workers}")
        logger.info(f"- Primary AI Service: Groq ({'✓' if settings.groq_keys else '✗'})")
        logger.info(f"- Fallback Services: {len([s for s in ['gemini', 'openai', 'azure'] if settings.get_api_keys(s)])} available")
        logger.info(f"- Database configured: {bool(settings.database_url)}")
        logger.info(f"- Redis configured: {bool(settings.redis_url)}")
        
        return settings
        
    except Exception as e:
        logger.error(f"Failed to load settings: {e}")
        raise

def validate_environment() -> bool:
    """Validate that all required environment variables are set"""
    try:
        settings = load_settings()
        
        # Check critical requirements
        critical_missing = []
        
        if not settings.bot_token:
            critical_missing.append('BOT_TOKEN')
            
        # Check if at least one API service is configured (Groq is primary)
        if not settings.groq_keys:
            critical_missing.append('GROQ_KEYS (primary AI translation service)')
        
        # Optional: Check for fallback services
        fallback_services = ['gemini', 'openai', 'azure']
        available_fallbacks = [service for service in fallback_services if settings.get_api_keys(service)]
        
        if not available_fallbacks:
            logger.warning('No fallback AI services configured - only Groq will be available')
        
        if critical_missing:
            logger.error(f"Critical environment variables missing: {', '.join(critical_missing)}")
            return False
            
        # Warnings for production
        if settings.environment == Environment.PRODUCTION:
            warnings = []
            
            if not settings.database_url:
                warnings.append('DATABASE_URL (using in-memory storage)')
                
            if not settings.redis_url:
                warnings.append('REDIS_URL (caching disabled)')
                
            if not settings.webhook_url:
                warnings.append('WEBHOOK_URL (using polling mode)')
                
            if warnings:
                logger.warning(f"Production warnings: {', '.join(warnings)}")
        
        logger.info("Environment validation completed successfully")
        return True
        
    except Exception as e:
        logger.error(f"Environment validation failed: {e}")
        return False

# Global settings instance
settings: Optional[Settings] = None

def get_settings() -> Settings:
    """Get global settings instance"""
    global settings
    if settings is None:
        settings = load_settings()
    return settings