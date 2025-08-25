"""
Health check endpoints and web server for monitoring.
Provides REST API for health checks, metrics, and status monitoring.
"""

import asyncio
import json
import os
import time
from datetime import datetime
from typing import Dict, Any, Optional
import logging
import psutil
import aiohttp
from aiohttp import web, ClientSession
from aiohttp.web import Response, Request
import weakref

from config import get_settings
from monitoring import get_monitoring_system
from database import get_database_manager
from cache_system import AdvancedCacheSystem

logger = logging.getLogger(__name__)

class HealthCheckServer:
    """HTTP server for health checks and monitoring endpoints"""
    
    def __init__(self, host: str = "0.0.0.0", port: int = 8080):
        self.host = host
        self.port = port
        self.app = web.Application()
        self.runner: Optional[web.AppRunner] = None
        self.site: Optional[web.TCPSite] = None
        
        # Component references (weak references to avoid circular imports)
        self._bot_instance = None
        self._cache_system = None
        self._db_manager = None
        self._monitoring_system = None
        
        self.start_time = time.time()
        self.setup_routes()
    
    def setup_routes(self):
        """Setup all HTTP routes"""
        # Health check endpoints
        self.app.router.add_get('/health', self.health_check)
        self.app.router.add_get('/health/ready', self.readiness_check)
        self.app.router.add_get('/health/live', self.liveness_check)
        
        # Metrics endpoints
        self.app.router.add_get('/metrics', self.prometheus_metrics)
        self.app.router.add_get('/status', self.system_status)
        self.app.router.add_get('/stats', self.system_stats)
        
        # Component-specific health checks
        self.app.router.add_get('/health/database', self.database_health)
        self.app.router.add_get('/health/cache', self.cache_health)
        self.app.router.add_get('/health/bot', self.bot_health)
        
        # Administrative endpoints
        self.app.router.add_get('/info', self.system_info)
        self.app.router.add_get('/logs', self.recent_logs)
        
        # Webhook endpoint for Telegram
        self.app.router.add_post('/webhook', self.webhook_handler)
        
        # Root endpoint
        self.app.router.add_get('/', self.root_handler)
    
    def set_components(self, bot_instance=None, cache_system=None, db_manager=None, monitoring_system=None):
        """Set component references for health checks"""
        if bot_instance:
            self._bot_instance = weakref.ref(bot_instance)
        if cache_system:
            self._cache_system = weakref.ref(cache_system)
        if db_manager:
            self._db_manager = weakref.ref(db_manager)
        if monitoring_system:
            self._monitoring_system = weakref.ref(monitoring_system)
    
    async def root_handler(self, request: Request) -> Response:
        """Root endpoint with basic info"""
        uptime = time.time() - self.start_time
        return web.json_response({
            "service": "Translation Bot",
            "version": "1.0.0",
            "status": "running",
            "uptime": f"{uptime:.2f} seconds",
            "timestamp": datetime.utcnow().isoformat()
        })
    
    async def health_check(self, request: Request) -> Response:
        """Main health check endpoint"""
        try:
            # Check all components
            health_results = {
                "status": "healthy",
                "timestamp": datetime.utcnow().isoformat(),
                "uptime": time.time() - self.start_time,
                "components": {}
            }
            
            # Check database
            db_health = await self._check_database_health()
            health_results["components"]["database"] = db_health
            
            # Check cache
            cache_health = await self._check_cache_health()
            health_results["components"]["cache"] = cache_health
            
            # Check bot
            bot_health = await self._check_bot_health()
            health_results["components"]["bot"] = bot_health
            
            # Check system resources
            system_health = await self._check_system_health()
            health_results["components"]["system"] = system_health
            
            # Determine overall status
            component_statuses = [comp["status"] for comp in health_results["components"].values()]
            
            if "error" in component_statuses:
                health_results["status"] = "error"
                status_code = 503
            elif "degraded" in component_statuses:
                health_results["status"] = "degraded"
                status_code = 200
            else:
                health_results["status"] = "healthy"
                status_code = 200
            
            return web.json_response(health_results, status=status_code)
            
        except Exception as e:
            logger.error(f"Health check failed: {e}")
            return web.json_response({
                "status": "error",
                "error": str(e),
                "timestamp": datetime.utcnow().isoformat()
            }, status=503)
    
    async def readiness_check(self, request: Request) -> Response:
        """Kubernetes readiness probe"""
        try:
            # Check if service is ready to accept traffic
            ready = True
            checks = {}
            
            # Database connection
            if self._db_manager and self._db_manager():
                db_ready = await self._db_manager().health_check()
                checks["database"] = db_ready
                ready = ready and db_ready
            
            # Cache connection
            if self._cache_system and self._cache_system():
                cache_stats = await self._cache_system()._test_redis_connection()
                checks["cache"] = cache_stats
                ready = ready and cache_stats
            
            # Bot instance
            if self._bot_instance and self._bot_instance():
                bot_ready = self._bot_instance().application is not None
                checks["bot"] = bot_ready
                ready = ready and bot_ready
            
            status_code = 200 if ready else 503
            return web.json_response({
                "ready": ready,
                "checks": checks,
                "timestamp": datetime.utcnow().isoformat()
            }, status=status_code)
            
        except Exception as e:
            return web.json_response({
                "ready": False,
                "error": str(e),
                "timestamp": datetime.utcnow().isoformat()
            }, status=503)
    
    async def liveness_check(self, request: Request) -> Response:
        """Kubernetes liveness probe"""
        try:
            # Simple liveness check - service is running
            uptime = time.time() - self.start_time
            
            # Check if process is responsive
            alive = uptime > 0 and uptime < 86400 * 7  # Not older than 7 days
            
            status_code = 200 if alive else 503
            return web.json_response({
                "alive": alive,
                "uptime": uptime,
                "timestamp": datetime.utcnow().isoformat()
            }, status=status_code)
            
        except Exception as e:
            return web.json_response({
                "alive": False,
                "error": str(e),
                "timestamp": datetime.utcnow().isoformat()
            }, status=503)
    
    async def prometheus_metrics(self, request: Request) -> Response:
        """Prometheus metrics endpoint"""
        try:
            if self._monitoring_system and self._monitoring_system():
                metrics_data = self._monitoring_system().get_prometheus_metrics()
                return Response(text=metrics_data, content_type="text/plain; version=0.0.4; charset=utf-8")
            else:
                return Response(text="# Monitoring system not available\n", content_type="text/plain")
                
        except Exception as e:
            logger.error(f"Failed to get metrics: {e}")
            return Response(text=f"# Error: {e}\n", content_type="text/plain", status=500)
    
    async def system_status(self, request: Request) -> Response:
        """Comprehensive system status"""
        try:
            status = {
                "timestamp": datetime.utcnow().isoformat(),
                "uptime": time.time() - self.start_time,
                "version": "1.0.0",
                "environment": get_settings().environment.value,
                "components": {},
                "metrics": {}
            }
            
            # Get component statuses
            status["components"]["database"] = await self._check_database_health()
            status["components"]["cache"] = await self._check_cache_health()
            status["components"]["bot"] = await self._check_bot_health()
            status["components"]["system"] = await self._check_system_health()
            
            # Get monitoring data if available
            if self._monitoring_system and self._monitoring_system():
                monitoring_data = self._monitoring_system().get_system_status()
                status["metrics"] = monitoring_data.get("metrics", {})
                status["alerts"] = monitoring_data.get("alerts", [])
            
            return web.json_response(status)
            
        except Exception as e:
            logger.error(f"Failed to get system status: {e}")
            return web.json_response({
                "error": str(e),
                "timestamp": datetime.utcnow().isoformat()
            }, status=500)
    
    async def system_stats(self, request: Request) -> Response:
        """Detailed system statistics"""
        try:
            # System resource usage
            cpu_percent = psutil.cpu_percent(interval=1)
            memory = psutil.virtual_memory()
            disk = psutil.disk_usage('/')
            
            stats = {
                "timestamp": datetime.utcnow().isoformat(),
                "uptime": time.time() - self.start_time,
                "system": {
                    "cpu_percent": cpu_percent,
                    "memory": {
                        "total": memory.total,
                        "available": memory.available,
                        "percent": memory.percent,
                        "used": memory.used
                    },
                    "disk": {
                        "total": disk.total,
                        "used": disk.used,
                        "free": disk.free,
                        "percent": (disk.used / disk.total) * 100
                    }
                },
                "process": {
                    "pid": os.getpid(),
                    "memory_info": dict(psutil.Process().memory_info()._asdict()),
                    "cpu_percent": psutil.Process().cpu_percent()
                }
            }
            
            # Add cache stats if available
            if self._cache_system and self._cache_system():
                cache_stats = await self._cache_system().get_stats()
                stats["cache"] = cache_stats
            
            return web.json_response(stats)
            
        except Exception as e:
            logger.error(f"Failed to get system stats: {e}")
            return web.json_response({
                "error": str(e),
                "timestamp": datetime.utcnow().isoformat()
            }, status=500)
    
    async def database_health(self, request: Request) -> Response:
        """Database-specific health check"""
        health = await self._check_database_health()
        status_code = 200 if health["status"] == "healthy" else 503
        return web.json_response(health, status=status_code)
    
    async def cache_health(self, request: Request) -> Response:
        """Cache-specific health check"""
        health = await self._check_cache_health()
        status_code = 200 if health["status"] == "healthy" else 503
        return web.json_response(health, status=status_code)
    
    async def bot_health(self, request: Request) -> Response:
        """Bot-specific health check"""
        health = await self._check_bot_health()
        status_code = 200 if health["status"] == "healthy" else 503
        return web.json_response(health, status=status_code)
    
    async def system_info(self, request: Request) -> Response:
        """System information endpoint"""
        try:
            settings = get_settings()
            info = {
                "service": "Translation Bot",
                "version": "1.0.0",
                "environment": settings.environment.value,
                "python_version": f"{psutil.PYTHON_VERSION}",
                "platform": psutil.PLATFORM,
                "boot_time": psutil.boot_time(),
                "cpu_count": psutil.cpu_count(),
                "memory_total": psutil.virtual_memory().total,
                "disk_total": psutil.disk_usage('/').total,
                "start_time": self.start_time,
                "uptime": time.time() - self.start_time,
                "configuration": {
                    "max_workers": settings.max_workers,
                    "max_file_size_mb": settings.max_file_size_mb,
                    "daily_limit_per_user": settings.daily_limit_per_user,
                    "cache_ttl_seconds": settings.cache_ttl_seconds,
                    "database_configured": bool(settings.database_url),
                    "redis_configured": bool(settings.redis_url),
                    "webhook_configured": bool(settings.webhook_url)
                }
            }
            return web.json_response(info)
            
        except Exception as e:
            return web.json_response({
                "error": str(e),
                "timestamp": datetime.utcnow().isoformat()
            }, status=500)
    
    async def recent_logs(self, request: Request) -> Response:
        """Recent logs endpoint"""
        try:
            limit = int(request.query.get('limit', 50))
            level = request.query.get('level', 'all').upper()
            
            logs = []
            if self._monitoring_system and self._monitoring_system():
                if level == 'ERROR':
                    logs = self._monitoring_system().log_manager.get_error_logs(limit)
                else:
                    logs = self._monitoring_system().log_manager.get_recent_logs(limit)
            
            # Convert to dict for JSON serialization
            logs_data = [log._asdict() if hasattr(log, '_asdict') else log for log in logs]
            
            return web.json_response({
                "logs": logs_data,
                "count": len(logs_data),
                "timestamp": datetime.utcnow().isoformat()
            })
            
        except Exception as e:
            return web.json_response({
                "error": str(e),
                "timestamp": datetime.utcnow().isoformat()
            }, status=500)
    
    async def webhook_handler(self, request: Request) -> Response:
        """Telegram webhook handler"""
        try:
            if not self._bot_instance or not self._bot_instance():
                return web.json_response({"error": "Bot not available"}, status=503)
            
            # Verify webhook secret if configured
            settings = get_settings()
            if settings.webhook_secret:
                secret_header = request.headers.get('X-Telegram-Bot-Api-Secret-Token')
                if secret_header != settings.webhook_secret:
                    return web.json_response({"error": "Invalid secret"}, status=401)
            
            # Process update
            update_data = await request.json()
            bot = self._bot_instance()
            
            if bot and bot.application:
                await bot.application.process_update(update_data)
            
            return web.json_response({"status": "ok"})
            
        except Exception as e:
            logger.error(f"Webhook error: {e}")
            return web.json_response({"error": str(e)}, status=500)
    
    async def _check_database_health(self) -> Dict[str, Any]:
        """Check database health"""
        if not self._db_manager or not self._db_manager():
            return {
                "status": "not_configured",
                "message": "Database not configured"
            }
        
        try:
            db = self._db_manager()
            if not db.is_initialized:
                return {
                    "status": "not_initialized",
                    "message": "Database not initialized"
                }
            
            # Test connection
            start_time = time.time()
            healthy = await db.health_check()
            response_time = time.time() - start_time
            
            return {
                "status": "healthy" if healthy else "unhealthy",
                "response_time": response_time,
                "initialized": db.is_initialized,
                "url_configured": bool(db.database_url)
            }
            
        except Exception as e:
            return {
                "status": "error",
                "error": str(e)
            }
    
    async def _check_cache_health(self) -> Dict[str, Any]:
        """Check cache health"""
        if not self._cache_system or not self._cache_system():
            return {
                "status": "not_configured",
                "message": "Cache system not configured"
            }
        
        try:
            cache = self._cache_system()
            start_time = time.time()
            
            # Test Redis connection
            redis_available = await cache._test_redis_connection()
            response_time = time.time() - start_time
            
            # Get cache stats
            stats = await cache.get_stats()
            
            return {
                "status": "healthy" if redis_available else "degraded",
                "redis_available": redis_available,
                "response_time": response_time,
                "memory_cache_size": stats.get("memory_cache_size", 0),
                "redis_memory_used": stats.get("redis_memory_used", "N/A")
            }
            
        except Exception as e:
            return {
                "status": "error",
                "error": str(e)
            }
    
    async def _check_bot_health(self) -> Dict[str, Any]:
        """Check bot health"""
        if not self._bot_instance or not self._bot_instance():
            return {
                "status": "not_initialized",
                "message": "Bot instance not available"
            }
        
        try:
            bot = self._bot_instance()
            
            return {
                "status": "healthy" if bot.application else "not_started",
                "application_initialized": bool(bot.application),
                "shutdown_requested": getattr(bot, 'shutdown_requested', False),
                "request_count": getattr(bot, 'request_count', 0),
                "error_count": getattr(bot, 'error_count', 0)
            }
            
        except Exception as e:
            return {
                "status": "error",
                "error": str(e)
            }
    
    async def _check_system_health(self) -> Dict[str, Any]:
        """Check system resource health"""
        try:
            # CPU and memory usage
            cpu_percent = psutil.cpu_percent(interval=0.1)
            memory = psutil.virtual_memory()
            disk = psutil.disk_usage('/')
            
            # Determine status based on resource usage
            status = "healthy"
            if cpu_percent > 90 or memory.percent > 90 or (disk.used / disk.total) > 0.95:
                status = "degraded"
            if cpu_percent > 95 or memory.percent > 95 or (disk.used / disk.total) > 0.98:
                status = "critical"
            
            return {
                "status": status,
                "cpu_percent": cpu_percent,
                "memory_percent": memory.percent,
                "disk_percent": (disk.used / disk.total) * 100,
                "load_average": os.getloadavg() if hasattr(os, 'getloadavg') else None
            }
            
        except Exception as e:
            return {
                "status": "error",
                "error": str(e)
            }
    
    async def start(self):
        """Start the HTTP server"""
        try:
            self.runner = web.AppRunner(self.app)
            await self.runner.setup()
            
            self.site = web.TCPSite(self.runner, self.host, self.port)
            await self.site.start()
            
            logger.info(f"Health check server started on {self.host}:{self.port}")
            
        except Exception as e:
            logger.error(f"Failed to start health check server: {e}")
            raise
    
    async def stop(self):
        """Stop the HTTP server"""
        try:
            if self.site:
                await self.site.stop()
            
            if self.runner:
                await self.runner.cleanup()
            
            logger.info("Health check server stopped")
            
        except Exception as e:
            logger.error(f"Error stopping health check server: {e}")

# Global health check server instance
health_server: Optional[HealthCheckServer] = None

def get_health_server() -> Optional[HealthCheckServer]:
    """Get global health check server instance"""
    return health_server

def create_health_server(host: str = "0.0.0.0", port: int = 8080) -> HealthCheckServer:
    """Create global health check server instance"""
    global health_server
    health_server = HealthCheckServer(host, port)
    return health_server