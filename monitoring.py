"""
Comprehensive logging and monitoring system for the translation bot.
Includes structured logging, metrics collection, and health monitoring.
"""

import asyncio
import logging
import logging.handlers
import time
import json
import os
from datetime import datetime, timedelta
from typing import Dict, Any, Optional, List
from dataclasses import dataclass, asdict
from collections import defaultdict, deque
import structlog
from prometheus_client import Counter, Histogram, Gauge, generate_latest, CONTENT_TYPE_LATEST
import aiohttp

# Configure structured logging
structlog.configure(
    processors=[
        structlog.stdlib.filter_by_level,
        structlog.stdlib.add_logger_name,
        structlog.stdlib.add_log_level,
        structlog.stdlib.PositionalArgumentsFormatter(),
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.StackInfoRenderer(),
        structlog.processors.format_exc_info,
        structlog.processors.UnicodeDecoder(),
        structlog.processors.JSONRenderer()
    ],
    context_class=dict,
    logger_factory=structlog.stdlib.LoggerFactory(),
    wrapper_class=structlog.stdlib.BoundLogger,
    cache_logger_on_first_use=True,
)

@dataclass
class LogEvent:
    """Structured log event"""
    timestamp: str
    level: str
    message: str
    user_id: Optional[int] = None
    request_id: Optional[str] = None
    duration: Optional[float] = None
    error: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = None

@dataclass
class MetricSnapshot:
    """System metrics snapshot"""
    timestamp: str
    requests_total: int
    requests_successful: int
    requests_failed: int
    active_users: int
    queue_size: int
    avg_response_time: float
    cache_hit_rate: float
    api_usage: Dict[str, int]
    memory_usage: float
    uptime: float

class LogManager:
    """Advanced logging manager with structured logging"""
    
    def __init__(self, log_level: str = "INFO", log_file: str = "bot.log"):
        self.log_level = getattr(logging, log_level.upper())
        self.log_file = log_file
        self.setup_logging()
        
        # Structured logger
        self.logger = structlog.get_logger("translation_bot")
        
        # Log storage for monitoring
        self.recent_logs = deque(maxlen=1000)
        self.error_logs = deque(maxlen=100)
    
    def setup_logging(self):
        """Setup comprehensive logging configuration"""
        
        # Create logs directory
        os.makedirs("logs", exist_ok=True)
        
        # Root logger configuration
        root_logger = logging.getLogger()
        root_logger.setLevel(self.log_level)
        
        # Clear existing handlers
        for handler in root_logger.handlers[:]:
            root_logger.removeHandler(handler)
        
        # Console handler with colored output
        console_handler = logging.StreamHandler()
        console_handler.setLevel(self.log_level)
        console_formatter = logging.Formatter(
            '%(asctime)s - %(name)s - %(levelname)s - %(message)s',
            datefmt='%Y-%m-%d %H:%M:%S'
        )
        console_handler.setFormatter(console_formatter)
        root_logger.addHandler(console_handler)
        
        # File handler with rotation
        file_handler = logging.handlers.RotatingFileHandler(
            f"logs/{self.log_file}",
            maxBytes=50*1024*1024,  # 50MB
            backupCount=5,
            encoding='utf-8'
        )
        file_handler.setLevel(self.log_level)
        file_formatter = logging.Formatter(
            '%(asctime)s - %(name)s - %(levelname)s - %(pathname)s:%(lineno)d - %(message)s'
        )
        file_handler.setFormatter(file_formatter)
        root_logger.addHandler(file_handler)
        
        # Error file handler
        error_handler = logging.handlers.RotatingFileHandler(
            "logs/errors.log",
            maxBytes=20*1024*1024,  # 20MB
            backupCount=3,
            encoding='utf-8'
        )
        error_handler.setLevel(logging.ERROR)
        error_handler.setFormatter(file_formatter)
        root_logger.addHandler(error_handler)
        
        # JSON handler for structured logs
        json_handler = logging.handlers.RotatingFileHandler(
            "logs/structured.log",
            maxBytes=100*1024*1024,  # 100MB
            backupCount=10,
            encoding='utf-8'
        )
        json_handler.setLevel(logging.INFO)
        json_formatter = logging.Formatter('%(message)s')
        json_handler.setFormatter(json_formatter)
        
        # Add custom filter for structured logs
        class StructuredLogFilter(logging.Filter):
            def filter(self, record):
                return hasattr(record, 'structured') and record.structured
        
        json_handler.addFilter(StructuredLogFilter())
        root_logger.addHandler(json_handler)
    
    def log_event(self, level: str, message: str, **kwargs):
        """Log a structured event"""
        event = LogEvent(
            timestamp=datetime.utcnow().isoformat(),
            level=level.upper(),
            message=message,
            **kwargs
        )
        
        # Store in recent logs
        self.recent_logs.append(event)
        
        # Store errors separately
        if level.upper() in ['ERROR', 'CRITICAL']:
            self.error_logs.append(event)
        
        # Log with structured logger
        log_data = asdict(event)
        log_data = {k: v for k, v in log_data.items() if v is not None}
        
        getattr(self.logger, level.lower())(**log_data)
    
    def get_recent_logs(self, limit: int = 50) -> List[LogEvent]:
        """Get recent log events"""
        return list(self.recent_logs)[-limit:]
    
    def get_error_logs(self, limit: int = 20) -> List[LogEvent]:
        """Get recent error logs"""
        return list(self.error_logs)[-limit:]

class MetricsCollector:
    """Prometheus metrics collector"""
    
    def __init__(self):
        # Request metrics
        self.requests_total = Counter(
            'translation_requests_total',
            'Total translation requests',
            ['status', 'user_type']
        )
        
        self.request_duration = Histogram(
            'translation_request_duration_seconds',
            'Request processing duration',
            ['operation']
        )
        
        # User metrics
        self.active_users = Gauge(
            'translation_active_users',
            'Number of active users'
        )
        
        self.user_requests = Counter(
            'translation_user_requests_total',
            'Total requests per user',
            ['user_id']
        )
        
        # System metrics
        self.queue_size = Gauge(
            'translation_queue_size',
            'Current queue size'
        )
        
        self.api_calls = Counter(
            'translation_api_calls_total',
            'API calls by service',
            ['service', 'status']
        )
        
        self.cache_operations = Counter(
            'translation_cache_operations_total',
            'Cache operations',
            ['operation', 'result']
        )
        
        # Error metrics
        self.errors_total = Counter(
            'translation_errors_total',
            'Total errors',
            ['error_type']
        )
        
        # Performance metrics
        self.memory_usage = Gauge(
            'translation_memory_usage_bytes',
            'Memory usage in bytes'
        )
        
        self.uptime = Gauge(
            'translation_uptime_seconds',
            'Bot uptime in seconds'
        )
    
    def record_request(self, status: str, user_type: str = "regular", duration: float = 0):
        """Record a translation request"""
        self.requests_total.labels(status=status, user_type=user_type).inc()
        if duration > 0:
            self.request_duration.labels(operation="translation").observe(duration)
    
    def record_api_call(self, service: str, status: str):
        """Record an API call"""
        self.api_calls.labels(service=service, status=status).inc()
    
    def record_cache_operation(self, operation: str, result: str):
        """Record a cache operation"""
        self.cache_operations.labels(operation=operation, result=result).inc()
    
    def record_error(self, error_type: str):
        """Record an error"""
        self.errors_total.labels(error_type=error_type).inc()
    
    def update_system_metrics(self, queue_size: int, active_users: int, memory_mb: float, uptime: float):
        """Update system metrics"""
        self.queue_size.set(queue_size)
        self.active_users.set(active_users)
        self.memory_usage.set(memory_mb * 1024 * 1024)  # Convert to bytes
        self.uptime.set(uptime)
    
    def get_metrics(self) -> str:
        """Get Prometheus formatted metrics"""
        return generate_latest()

class HealthMonitor:
    """System health monitoring"""
    
    def __init__(self, check_interval: int = 60):
        self.check_interval = check_interval
        self.health_status = {
            'status': 'unknown',
            'last_check': None,
            'components': {},
            'uptime': 0,
            'start_time': time.time()
        }
        
        self.alert_thresholds = {
            'error_rate': 5.0,  # 5% error rate
            'response_time': 30.0,  # 30 seconds average
            'queue_size': 100,  # 100 pending tasks
            'memory_usage': 80.0,  # 80% memory usage
            'disk_usage': 90.0   # 90% disk usage
        }
        
        self.alerts = deque(maxlen=50)
    
    async def check_component_health(self, name: str, check_func) -> Dict[str, Any]:
        """Check health of a specific component"""
        start_time = time.time()
        try:
            result = await check_func() if asyncio.iscoroutinefunction(check_func) else check_func()
            duration = time.time() - start_time
            
            return {
                'status': 'healthy' if result else 'unhealthy',
                'response_time': duration,
                'last_check': datetime.utcnow().isoformat(),
                'details': result if isinstance(result, dict) else {}
            }
        except Exception as e:
            duration = time.time() - start_time
            return {
                'status': 'error',
                'response_time': duration,
                'last_check': datetime.utcnow().isoformat(),
                'error': str(e)
            }
    
    async def full_health_check(self, components: Dict[str, Any]) -> Dict[str, Any]:
        """Perform full system health check"""
        start_time = time.time()
        
        # Check all components
        component_results = {}
        for name, check_func in components.items():
            component_results[name] = await self.check_component_health(name, check_func)
        
        # Calculate overall status
        all_healthy = all(
            comp['status'] == 'healthy' 
            for comp in component_results.values()
        )
        
        has_errors = any(
            comp['status'] == 'error' 
            for comp in component_results.values()
        )
        
        if has_errors:
            overall_status = 'error'
        elif all_healthy:
            overall_status = 'healthy'
        else:
            overall_status = 'degraded'
        
        # Update health status
        self.health_status.update({
            'status': overall_status,
            'last_check': datetime.utcnow().isoformat(),
            'components': component_results,
            'uptime': time.time() - self.health_status['start_time'],
            'check_duration': time.time() - start_time
        })
        
        return self.health_status
    
    def check_alerts(self, metrics: Dict[str, float]):
        """Check for alert conditions"""
        current_time = datetime.utcnow()
        
        for metric, threshold in self.alert_thresholds.items():
            if metric in metrics:
                value = metrics[metric]
                
                # Check if threshold is exceeded
                if (metric in ['error_rate', 'response_time', 'queue_size', 'memory_usage', 'disk_usage'] 
                    and value > threshold):
                    
                    alert = {
                        'timestamp': current_time.isoformat(),
                        'metric': metric,
                        'value': value,
                        'threshold': threshold,
                        'severity': 'high' if value > threshold * 1.5 else 'medium',
                        'message': f"{metric} ({value}) exceeded threshold ({threshold})"
                    }
                    
                    self.alerts.append(alert)
    
    def get_alerts(self, severity: str = None, limit: int = 10) -> List[Dict[str, Any]]:
        """Get recent alerts"""
        alerts = list(self.alerts)
        
        if severity:
            alerts = [a for a in alerts if a.get('severity') == severity]
        
        return alerts[-limit:]

class MonitoringSystem:
    """Integrated monitoring system"""
    
    def __init__(self, log_level: str = "INFO"):
        self.log_manager = LogManager(log_level)
        self.metrics = MetricsCollector()
        self.health_monitor = HealthMonitor()
        
        # Monitoring state
        self.start_time = time.time()
        self.request_times = deque(maxlen=1000)  # Track response times
        self.error_counts = defaultdict(int)
        
        # Background monitoring task
        self.monitoring_task: Optional[asyncio.Task] = None
    
    async def start_monitoring(self, health_checks: Dict[str, Any]):
        """Start background monitoring"""
        self.health_checks = health_checks
        self.monitoring_task = asyncio.create_task(self._monitoring_loop())
        self.log_manager.log_event("info", "Monitoring system started")
    
    async def stop_monitoring(self):
        """Stop background monitoring"""
        if self.monitoring_task:
            self.monitoring_task.cancel()
            try:
                await self.monitoring_task
            except asyncio.CancelledError:
                pass
        self.log_manager.log_event("info", "Monitoring system stopped")
    
    async def _monitoring_loop(self):
        """Background monitoring loop"""
        while True:
            try:
                # Perform health check
                await self.health_monitor.full_health_check(self.health_checks)
                
                # Calculate metrics
                current_metrics = self._calculate_current_metrics()
                
                # Check for alerts
                self.health_monitor.check_alerts(current_metrics)
                
                # Update Prometheus metrics
                self._update_prometheus_metrics(current_metrics)
                
                # Log system status
                self.log_manager.log_event(
                    "info", 
                    "System health check completed",
                    metadata=current_metrics
                )
                
                await asyncio.sleep(60)  # Check every minute
                
            except asyncio.CancelledError:
                break
            except Exception as e:
                self.log_manager.log_event(
                    "error", 
                    "Monitoring loop error",
                    error=str(e)
                )
                await asyncio.sleep(30)  # Wait before retrying
    
    def _calculate_current_metrics(self) -> Dict[str, float]:
        """Calculate current system metrics"""
        now = time.time()
        uptime = now - self.start_time
        
        # Calculate average response time
        if self.request_times:
            avg_response_time = sum(self.request_times) / len(self.request_times)
        else:
            avg_response_time = 0
        
        # Calculate error rate
        total_errors = sum(self.error_counts.values())
        total_requests = len(self.request_times) + total_errors
        error_rate = (total_errors / max(total_requests, 1)) * 100
        
        return {
            'uptime': uptime,
            'avg_response_time': avg_response_time,
            'error_rate': error_rate,
            'total_requests': total_requests,
            'total_errors': total_errors
        }
    
    def _update_prometheus_metrics(self, current_metrics: Dict[str, float]):
        """Update Prometheus metrics with current values"""
        self.metrics.uptime.set(current_metrics['uptime'])
        
        # Update other metrics as needed
        # This would be expanded based on available system metrics
    
    def record_request(self, duration: float, status: str = "success", user_type: str = "regular"):
        """Record a request for monitoring"""
        self.request_times.append(duration)
        self.metrics.record_request(status, user_type, duration)
        
        self.log_manager.log_event(
            "info",
            "Request processed",
            duration=duration,
            metadata={'status': status, 'user_type': user_type}
        )
    
    def record_error(self, error_type: str, error_message: str, **kwargs):
        """Record an error for monitoring"""
        self.error_counts[error_type] += 1
        self.metrics.record_error(error_type)
        
        self.log_manager.log_event(
            "error",
            error_message,
            error=error_type,
            **kwargs
        )
    
    def get_system_status(self) -> Dict[str, Any]:
        """Get comprehensive system status"""
        return {
            'health': self.health_monitor.health_status,
            'metrics': self._calculate_current_metrics(),
            'alerts': self.health_monitor.get_alerts(limit=5),
            'recent_logs': [asdict(log) for log in self.log_manager.get_recent_logs(10)],
            'error_logs': [asdict(log) for log in self.log_manager.get_error_logs(5)]
        }
    
    def get_prometheus_metrics(self) -> str:
        """Get Prometheus formatted metrics"""
        return self.metrics.get_metrics()

# Global monitoring instance
monitoring_system: Optional[MonitoringSystem] = None

def get_monitoring_system() -> Optional[MonitoringSystem]:
    """Get global monitoring system instance"""
    return monitoring_system

def initialize_monitoring(log_level: str = "INFO") -> MonitoringSystem:
    """Initialize global monitoring system"""
    global monitoring_system
    monitoring_system = MonitoringSystem(log_level)
    return monitoring_system