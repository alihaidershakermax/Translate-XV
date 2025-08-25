#!/usr/bin/env python3
"""
Production startup script for the Advanced Translation Bot.
Integrates all systems and handles graceful startup/shutdown.
"""

import asyncio
import signal
import sys
import os
import logging
import time
from pathlib import Path

# Add the current directory to Python path
sys.path.insert(0, str(Path(__file__).parent))

# Import all our systems
from config import get_settings, validate_environment
from cache_system import AdvancedCacheSystem
from database import initialize_database
from monitoring import initialize_monitoring
from security import initialize_security
from health_server import create_health_server
from main_optimized import OptimizedTranslationBot

logger = logging.getLogger(__name__)

class ProductionBotRunner:
    """Production bot runner with complete system integration"""
    
    def __init__(self):
        self.settings = None
        self.bot = None
        self.health_server = None
        self.cache_system = None
        self.db_manager = None
        self.monitoring_system = None
        self.security_manager = None
        self.shutdown_event = asyncio.Event()
        
    async def initialize_all_systems(self):
        """Initialize all bot systems in the correct order"""
        logger.info("=== Starting Advanced Translation Bot ===")
        start_time = time.time()
        
        try:
            # 1. Load and validate configuration
            logger.info("📋 Loading configuration...")
            self.settings = get_settings()
            
            if not validate_environment():
                raise RuntimeError("Environment validation failed")
            
            logger.info(f"✅ Configuration loaded for {self.settings.environment.value} environment")
            
            # 2. Initialize cache system
            logger.info("💾 Initializing cache system...")
            self.cache_system = AdvancedCacheSystem(
                redis_url=self.settings.redis_url,
                default_ttl=self.settings.cache_ttl_seconds
            )
            
            # Test cache connection
            cache_stats = await self.cache_system.get_stats()
            logger.info(f"✅ Cache system initialized - Redis: {cache_stats['redis_available']}")
            
            # 3. Initialize database
            logger.info("🗄️  Initializing database...")
            self.db_manager = initialize_database(self.settings.database_url)
            
            if self.db_manager.is_initialized:
                await self.db_manager.create_tables()
                db_health = await self.db_manager.health_check()
                logger.info(f"✅ Database initialized - Health: {db_health}")
            else:
                logger.warning("⚠️  Database not configured - using in-memory storage")
            
            # 4. Initialize monitoring system
            logger.info("📊 Initializing monitoring system...")
            self.monitoring_system = initialize_monitoring(self.settings.log_level.value)
            
            # Setup health checks for monitoring
            health_checks = {
                'database': self.db_manager.health_check if self.db_manager.is_initialized else lambda: True,
                'cache': self.cache_system._test_redis_connection,
                'memory': self._check_memory_usage,
                'disk': self._check_disk_usage
            }
            
            await self.monitoring_system.start_monitoring(health_checks)
            logger.info("✅ Monitoring system started")
            
            # 5. Initialize security system
            logger.info("🔒 Initializing security system...")
            self.security_manager = initialize_security(self.cache_system)
            logger.info("✅ Security system initialized")
            
            # 6. Initialize health check server
            logger.info("🏥 Starting health check server...")
            port = int(os.getenv("PORT", self.settings.metrics_port))
            self.health_server = create_health_server(port=port)
            
            # Set component references for health checks
            self.health_server.set_components(
                cache_system=self.cache_system,
                db_manager=self.db_manager,
                monitoring_system=self.monitoring_system
            )
            
            await self.health_server.start()
            logger.info(f"✅ Health check server started on port {port}")
            
            # 7. Initialize the main bot
            logger.info("🤖 Initializing translation bot...")
            self.bot = OptimizedTranslationBot()
            
            # Inject our systems into the bot
            self.bot.cache_system = self.cache_system
            self.bot.db_manager = self.db_manager
            self.bot.monitoring_system = self.monitoring_system
            self.bot.security_manager = self.security_manager
            
            await self.bot.initialize()
            
            # Set bot reference in health server
            self.health_server.set_components(bot_instance=self.bot)
            
            initialization_time = time.time() - start_time
            logger.info(f"✅ Bot initialized successfully in {initialization_time:.2f} seconds")
            
            # Log system summary
            await self._log_system_summary()
            
        except Exception as e:
            logger.error(f"❌ Initialization failed: {e}")
            await self.cleanup()
            raise
    
    async def _log_system_summary(self):
        """Log a summary of all initialized systems"""
        summary = f"""
=== System Initialization Summary ===
🌍 Environment: {self.settings.environment.value}
💾 Cache System: {'Redis + Memory' if self.cache_system.redis_client else 'Memory Only'}
🗄️  Database: {'PostgreSQL' if self.db_manager.is_initialized else 'In-Memory'}
📊 Monitoring: Active with {len(self.monitoring_system.health_checks)} health checks
🔒 Security: Rate limiting + Abuse protection enabled
🏥 Health Server: Running on port {self.health_server.port}
🤖 Bot: Optimized with async processing

📈 Performance Settings:
   - Max Workers: {self.settings.max_workers}
   - Max Concurrent Translations: {self.settings.max_concurrent_translations}
   - Cache TTL: {self.settings.cache_ttl_seconds}s
   - Daily User Limit: {self.settings.daily_limit_per_user}
   - Max File Size: {self.settings.max_file_size_mb}MB

🔧 Features Enabled:
   ✅ Advanced Caching
   ✅ Database Persistence  
   ✅ Real-time Monitoring
   ✅ Security & Rate Limiting
   ✅ Health Checks
   ✅ Graceful Shutdown
   ✅ Connection Pooling
   ✅ Async Processing

=== Bot Ready for Production ===
        """
        logger.info(summary)
        
        # Log to monitoring system
        if self.monitoring_system:
            self.monitoring_system.log_manager.log_event(
                "info",
                "System initialization completed",
                metadata={
                    "environment": self.settings.environment.value,
                    "features": ["caching", "database", "monitoring", "security", "health_checks"],
                    "performance_settings": {
                        "max_workers": self.settings.max_workers,
                        "max_concurrent": self.settings.max_concurrent_translations,
                        "cache_ttl": self.settings.cache_ttl_seconds
                    }
                }
            )
    
    async def run(self):
        """Run the complete bot system"""
        try:
            await self.initialize_all_systems()
            
            # Setup signal handlers for graceful shutdown
            loop = asyncio.get_running_loop()
            for sig in (signal.SIGTERM, signal.SIGINT):
                loop.add_signal_handler(sig, lambda: asyncio.create_task(self.initiate_shutdown()))
            
            logger.info("🚀 Bot is now running...")
            
            # Start the bot (this will run until shutdown)
            await self.bot.run()
            
        except KeyboardInterrupt:
            logger.info("Received keyboard interrupt")
        except Exception as e:
            logger.error(f"Runtime error: {e}")
            raise
        finally:
            await self.cleanup()
    
    async def initiate_shutdown(self):
        """Initiate graceful shutdown"""
        logger.info("🛑 Shutdown signal received, initiating graceful shutdown...")
        self.shutdown_event.set()
        
        if self.bot:
            await self.bot.shutdown()
    
    async def cleanup(self):
        """Cleanup all resources"""
        logger.info("🧹 Cleaning up resources...")
        
        cleanup_tasks = []
        
        # Stop health server
        if self.health_server:
            cleanup_tasks.append(self.health_server.stop())
        
        # Stop monitoring
        if self.monitoring_system:
            cleanup_tasks.append(self.monitoring_system.stop_monitoring())
        
        # Close database connections
        if self.db_manager:
            cleanup_tasks.append(self.db_manager.close())
        
        # Close cache connections
        if self.cache_system and self.cache_system.redis_client:
            cleanup_tasks.append(self.cache_system.redis_client.aclose())
        
        # Execute all cleanup tasks
        if cleanup_tasks:
            await asyncio.gather(*cleanup_tasks, return_exceptions=True)
        
        logger.info("✅ Cleanup completed")
    
    async def _check_memory_usage(self) -> bool:
        """Check system memory usage"""
        try:
            import psutil
            memory = psutil.virtual_memory()
            return memory.percent < 90  # Healthy if under 90%
        except Exception:
            return True  # Assume healthy if can't check
    
    async def _check_disk_usage(self) -> bool:
        """Check disk usage"""
        try:
            import psutil
            disk = psutil.disk_usage('/')
            return (disk.used / disk.total) < 0.9  # Healthy if under 90%
        except Exception:
            return True  # Assume healthy if can't check

async def main():
    """Main entry point"""
    
    # Configure logging for startup
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        handlers=[
            logging.StreamHandler(sys.stdout),
            logging.FileHandler('startup.log', encoding='utf-8')
        ]
    )
    
    logger.info("Starting Advanced Translation Bot...")
    
    runner = ProductionBotRunner()
    
    try:
        await runner.run()
    except Exception as e:
        logger.error(f"Fatal error: {e}")
        sys.exit(1)

if __name__ == "__main__":
    # Ensure we're running Python 3.11+
    if sys.version_info < (3, 11):
        print("❌ Python 3.11 or higher is required")
        sys.exit(1)
    
    # Run the bot
    asyncio.run(main())