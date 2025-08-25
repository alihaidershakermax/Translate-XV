"""
Security and rate limiting system for the translation bot.
Includes user authentication, rate limiting, abuse prevention, and security middleware.
"""

import asyncio
import time
import hashlib
import secrets
import logging
from datetime import datetime, timedelta
from typing import Dict, Any, Optional, List, Set
from dataclasses import dataclass, field
from collections import defaultdict, deque
import ipaddress
import re

from telegram import Update, User
from telegram.ext import ContextTypes

from config import get_settings
from cache_system import AdvancedCacheSystem, CacheKey

logger = logging.getLogger(__name__)

@dataclass
class SecurityEvent:
    """Security event for logging and monitoring"""
    timestamp: str
    event_type: str
    user_id: Optional[int]
    ip_address: Optional[str]
    severity: str  # low, medium, high, critical
    description: str
    metadata: Dict[str, Any] = field(default_factory=dict)

@dataclass
class RateLimitRule:
    """Rate limiting rule configuration"""
    name: str
    requests: int  # Number of requests
    period: int    # Time period in seconds
    burst: int = 0 # Burst allowance
    penalty_duration: int = 300  # Penalty duration in seconds

class RateLimiter:
    """Advanced rate limiter with multiple strategies"""
    
    def __init__(self, cache_system: AdvancedCacheSystem):
        self.cache_system = cache_system
        
        # Rate limiting rules
        self.rules = {
            'user_requests': RateLimitRule(
                name='user_requests',
                requests=50,    # 50 requests
                period=86400,   # per day
                burst=5,        # 5 burst requests
                penalty_duration=3600  # 1 hour penalty
            ),
            'user_files': RateLimitRule(
                name='user_files', 
                requests=20,    # 20 files
                period=86400,   # per day
                burst=2,        # 2 burst files
                penalty_duration=7200  # 2 hour penalty
            ),
            'ip_requests': RateLimitRule(
                name='ip_requests',
                requests=100,   # 100 requests
                period=3600,    # per hour
                burst=10,       # 10 burst requests
                penalty_duration=1800  # 30 min penalty
            ),
            'global_api': RateLimitRule(
                name='global_api',
                requests=1000,  # 1000 requests
                period=3600,    # per hour
                burst=50,       # 50 burst requests
                penalty_duration=600   # 10 min penalty
            )
        }
    
    async def check_rate_limit(self, rule_name: str, identifier: str) -> Dict[str, Any]:
        """Check if request is within rate limit"""
        rule = self.rules.get(rule_name)
        if not rule:
            return {'allowed': True, 'reason': 'no_rule'}
        
        current_time = int(time.time())
        cache_key = f"rate_limit:{rule_name}:{identifier}"
        penalty_key = f"penalty:{rule_name}:{identifier}"
        
        # Check if user is under penalty
        penalty_until = await self.cache_system.get(penalty_key)
        if penalty_until and current_time < int(penalty_until):
            remaining = int(penalty_until) - current_time
            return {
                'allowed': False,
                'reason': 'penalty',
                'remaining_penalty': remaining,
                'rule': rule.name
            }
        
        # Get current request count
        request_data = await self.cache_system.get(cache_key)
        if not request_data:
            request_data = {'count': 0, 'start_time': current_time, 'burst_used': 0}
        
        # Reset counter if period has passed
        if current_time - request_data['start_time'] >= rule.period:
            request_data = {'count': 0, 'start_time': current_time, 'burst_used': 0}
        
        # Check if within limits
        current_count = request_data['count']
        burst_used = request_data.get('burst_used', 0)
        
        # Allow burst requests
        if current_count >= rule.requests:
            if burst_used < rule.burst:
                # Use burst allowance
                request_data['burst_used'] = burst_used + 1
                await self.cache_system.set(cache_key, request_data, ttl=rule.period)
                return {
                    'allowed': True,
                    'reason': 'burst',
                    'remaining': rule.requests + rule.burst - current_count - 1,
                    'rule': rule.name
                }
            else:
                # Rate limit exceeded, apply penalty
                penalty_until = current_time + rule.penalty_duration
                await self.cache_system.set(penalty_key, str(penalty_until), ttl=rule.penalty_duration)
                
                return {
                    'allowed': False,
                    'reason': 'rate_limit_exceeded',
                    'penalty_duration': rule.penalty_duration,
                    'rule': rule.name
                }
        
        # Within normal limits
        request_data['count'] = current_count + 1
        await self.cache_system.set(cache_key, request_data, ttl=rule.period)
        
        return {
            'allowed': True,
            'reason': 'within_limit',
            'remaining': rule.requests - current_count - 1,
            'rule': rule.name
        }
    
    async def get_rate_limit_status(self, rule_name: str, identifier: str) -> Dict[str, Any]:
        """Get current rate limit status without incrementing"""
        rule = self.rules.get(rule_name)
        if not rule:
            return {'exists': False}
        
        current_time = int(time.time())
        cache_key = f"rate_limit:{rule_name}:{identifier}"
        penalty_key = f"penalty:{rule_name}:{identifier}"
        
        # Check penalty status
        penalty_until = await self.cache_system.get(penalty_key)
        penalty_active = penalty_until and current_time < int(penalty_until)
        
        # Get current usage
        request_data = await self.cache_system.get(cache_key)
        if not request_data:
            request_data = {'count': 0, 'start_time': current_time, 'burst_used': 0}
        
        # Calculate remaining quota
        if current_time - request_data['start_time'] >= rule.period:
            remaining = rule.requests
            period_remaining = rule.period
        else:
            remaining = max(0, rule.requests - request_data['count'])
            period_remaining = rule.period - (current_time - request_data['start_time'])
        
        return {
            'exists': True,
            'rule': rule.name,
            'limit': rule.requests,
            'period': rule.period,
            'remaining': remaining,
            'used': request_data['count'],
            'burst_available': rule.burst - request_data.get('burst_used', 0),
            'penalty_active': penalty_active,
            'penalty_remaining': int(penalty_until) - current_time if penalty_active else 0,
            'period_remaining': period_remaining
        }

class SecurityManager:
    """Comprehensive security management system"""
    
    def __init__(self, cache_system: AdvancedCacheSystem):
        self.cache_system = cache_system
        self.rate_limiter = RateLimiter(cache_system)
        
        # Security configuration
        self.settings = get_settings()
        
        # Blocked users and IPs
        self.blocked_users: Set[int] = set()
        self.blocked_ips: Set[str] = set()
        self.suspicious_patterns: List[str] = [
            r'<script',
            r'javascript:',
            r'data:text/html',
            r'eval\(',
            r'document\.cookie',
            r'XSS',
            r'../../../',
            r'\.\./',
            r'file://',
            r'ftp://',
        ]
        
        # Security events storage
        self.security_events = deque(maxlen=1000)
        self.failed_attempts = defaultdict(int)
        
        # Admin users (can be configured via environment)
        admin_user_ids = self.settings.admin_user_ids if hasattr(self.settings, 'admin_user_ids') else ""
        self.admin_users = set(int(uid) for uid in admin_user_ids.split(',') if uid.strip().isdigit())
        
    async def authenticate_user(self, user: User, update: Update = None) -> Dict[str, Any]:
        """Authenticate and authorize user"""
        user_id = user.id
        
        # Check if user is blocked
        if user_id in self.blocked_users:
            await self._log_security_event(
                'blocked_user_attempt',
                user_id=user_id,
                severity='high',
                description=f"Blocked user {user_id} attempted access"
            )
            return {
                'authenticated': False,
                'reason': 'user_blocked',
                'message': 'Your account has been blocked. Contact support.'
            }
        
        # Check IP-based blocking (if available)
        ip_address = self._extract_ip_from_update(update)
        if ip_address and ip_address in self.blocked_ips:
            await self._log_security_event(
                'blocked_ip_attempt',
                user_id=user_id,
                severity='high',
                description=f"Blocked IP {ip_address} attempted access",
                metadata={'ip': ip_address}
            )
            return {
                'authenticated': False,
                'reason': 'ip_blocked',
                'message': 'Access denied from this location.'
            }
        
        # Check rate limits
        rate_check = await self.rate_limiter.check_rate_limit('user_requests', str(user_id))
        if not rate_check['allowed']:
            await self._log_security_event(
                'rate_limit_exceeded',
                user_id=user_id,
                severity='medium',
                description=f"Rate limit exceeded for user {user_id}",
                metadata={'rate_check': rate_check}
            )
            return {
                'authenticated': False,
                'reason': 'rate_limited',
                'message': 'Too many requests. Please try again later.',
                'retry_after': rate_check.get('remaining_penalty', 60)
            }
        
        # IP-based rate limiting
        if ip_address:
            ip_rate_check = await self.rate_limiter.check_rate_limit('ip_requests', ip_address)
            if not ip_rate_check['allowed']:
                await self._log_security_event(
                    'ip_rate_limit_exceeded',
                    user_id=user_id,
                    severity='medium',
                    description=f"IP rate limit exceeded for {ip_address}",
                    metadata={'ip': ip_address, 'rate_check': ip_rate_check}
                )
                return {
                    'authenticated': False,
                    'reason': 'ip_rate_limited',
                    'message': 'Too many requests from this location.'
                }
        
        # User verification checks
        if not self._is_user_verified(user):
            return {
                'authenticated': False,
                'reason': 'user_not_verified',
                'message': 'Please verify your account first.',
                'requires_verification': True
            }
        
        # Success
        await self._log_security_event(
            'user_authenticated',
            user_id=user_id,
            severity='low',
            description=f"User {user_id} authenticated successfully"
        )
        
        return {
            'authenticated': True,
            'user_id': user_id,
            'is_admin': user_id in self.admin_users,
            'rate_limit_status': rate_check
        }
    
    async def validate_file_upload(self, file_data: bytes, file_name: str, user_id: int) -> Dict[str, Any]:
        """Validate file upload for security"""
        
        # File size check
        if len(file_data) > self.settings.max_file_size_mb * 1024 * 1024:
            await self._log_security_event(
                'file_size_exceeded',
                user_id=user_id,
                severity='low',
                description=f"File size exceeded for user {user_id}",
                metadata={'file_name': file_name, 'size': len(file_data)}
            )
            return {
                'valid': False,
                'reason': 'file_too_large',
                'message': f'File too large. Maximum size: {self.settings.max_file_size_mb}MB'
            }
        
        # File type validation
        allowed_extensions = {'.pdf', '.doc', '.docx', '.txt', '.jpg', '.jpeg', '.png', '.bmp', '.tiff'}
        file_ext = file_name.lower().split('.')[-1] if '.' in file_name else ''
        
        if f'.{file_ext}' not in allowed_extensions:
            await self._log_security_event(
                'invalid_file_type',
                user_id=user_id,
                severity='medium',
                description=f"Invalid file type uploaded by user {user_id}",
                metadata={'file_name': file_name, 'extension': file_ext}
            )
            return {
                'valid': False,
                'reason': 'invalid_file_type',
                'message': f'File type not allowed: {file_ext}'
            }
        
        # Malware/content scanning (basic)
        if self._scan_file_content(file_data, file_name):
            await self._log_security_event(
                'malicious_file_detected',
                user_id=user_id,
                severity='critical',
                description=f"Potentially malicious file uploaded by user {user_id}",
                metadata={'file_name': file_name}
            )
            return {
                'valid': False,
                'reason': 'security_threat',
                'message': 'File contains potentially malicious content.'
            }
        
        # File upload rate limiting
        rate_check = await self.rate_limiter.check_rate_limit('user_files', str(user_id))
        if not rate_check['allowed']:
            return {
                'valid': False,
                'reason': 'file_rate_limited',
                'message': 'Too many files uploaded. Please try again later.',
                'retry_after': rate_check.get('remaining_penalty', 3600)
            }
        
        return {
            'valid': True,
            'file_hash': hashlib.sha256(file_data).hexdigest(),
            'rate_limit_status': rate_check
        }
    
    async def validate_text_input(self, text: str, user_id: int) -> Dict[str, Any]:
        """Validate text input for security"""
        
        # Length check
        if len(text) > 100000:  # 100KB text limit
            await self._log_security_event(
                'text_too_long',
                user_id=user_id,
                severity='low',
                description=f"Text input too long from user {user_id}",
                metadata={'length': len(text)}
            )
            return {
                'valid': False,
                'reason': 'text_too_long',
                'message': 'Text input too long. Maximum 100,000 characters.'
            }
        
        # Pattern matching for suspicious content
        for pattern in self.suspicious_patterns:
            if re.search(pattern, text, re.IGNORECASE):
                await self._log_security_event(
                    'suspicious_text_pattern',
                    user_id=user_id,
                    severity='high',
                    description=f"Suspicious text pattern detected from user {user_id}",
                    metadata={'pattern': pattern, 'text_length': len(text)}
                )
                return {
                    'valid': False,
                    'reason': 'suspicious_content',
                    'message': 'Text contains suspicious content.'
                }
        
        return {'valid': True}
    
    async def handle_failed_attempt(self, user_id: int, attempt_type: str, details: Dict[str, Any] = None):
        """Handle failed authentication/authorization attempts"""
        self.failed_attempts[user_id] += 1
        
        await self._log_security_event(
            f'failed_{attempt_type}',
            user_id=user_id,
            severity='medium',
            description=f"Failed {attempt_type} attempt by user {user_id}",
            metadata={'attempt_count': self.failed_attempts[user_id], 'details': details or {}}
        )
        
        # Auto-block after too many failed attempts
        if self.failed_attempts[user_id] >= 10:
            await self.block_user(user_id, f"Too many failed {attempt_type} attempts")
    
    async def block_user(self, user_id: int, reason: str, duration: Optional[int] = None):
        """Block a user temporarily or permanently"""
        self.blocked_users.add(user_id)
        
        # Store in cache for persistence
        block_key = f"blocked_user:{user_id}"
        block_data = {
            'reason': reason,
            'blocked_at': datetime.utcnow().isoformat(),
            'duration': duration
        }
        
        ttl = duration if duration else 86400 * 7  # 7 days default
        await self.cache_system.set(block_key, block_data, ttl=ttl)
        
        await self._log_security_event(
            'user_blocked',
            user_id=user_id,
            severity='high',
            description=f"User {user_id} blocked: {reason}",
            metadata={'duration': duration}
        )
    
    async def unblock_user(self, user_id: int):
        """Unblock a user"""
        self.blocked_users.discard(user_id)
        await self.cache_system.delete(f"blocked_user:{user_id}")
        
        await self._log_security_event(
            'user_unblocked',
            user_id=user_id,
            severity='medium',
            description=f"User {user_id} unblocked"
        )
    
    def _is_user_verified(self, user: User) -> bool:
        """Check if user is verified (basic verification)"""
        # For now, we consider all users verified
        # This can be enhanced with phone verification, etc.
        return True
    
    def _extract_ip_from_update(self, update: Update) -> Optional[str]:
        """Extract IP address from Telegram update (limited info available)"""
        # Telegram doesn't provide user IP addresses directly
        # This is a placeholder for potential webhook IP extraction
        return None
    
    def _scan_file_content(self, file_data: bytes, file_name: str) -> bool:
        """Basic file content scanning for malicious patterns"""
        try:
            # Check for common malicious patterns in binary data
            dangerous_patterns = [
                b'<script',
                b'javascript:',
                b'eval(',
                b'document.cookie',
                b'vbscript:',
                b'onload=',
                b'onerror=',
                b'onclick='
            ]
            
            file_start = file_data[:4096]  # Check first 4KB
            
            for pattern in dangerous_patterns:
                if pattern in file_start:
                    return True
            
            # Check for suspicious file signatures
            if file_name.lower().endswith('.pdf'):
                # Basic PDF validation
                if not file_data.startswith(b'%PDF-'):
                    return True
            
            return False
            
        except Exception as e:
            logger.error(f"Error scanning file content: {e}")
            return True  # Err on the side of caution
    
    async def _log_security_event(self, event_type: str, severity: str, description: str, 
                                 user_id: Optional[int] = None, **kwargs):
        """Log security event"""
        event = SecurityEvent(
            timestamp=datetime.utcnow().isoformat(),
            event_type=event_type,
            user_id=user_id,
            ip_address=kwargs.get('ip_address'),
            severity=severity,
            description=description,
            metadata=kwargs.get('metadata', {})
        )
        
        self.security_events.append(event)
        
        # Log to main logger based on severity
        log_level = {
            'low': logging.INFO,
            'medium': logging.WARNING,
            'high': logging.ERROR,
            'critical': logging.CRITICAL
        }.get(severity, logging.INFO)
        
        logger.log(log_level, f"Security Event: {description}", extra={
            'event_type': event_type,
            'user_id': user_id,
            'severity': severity,
            **kwargs
        })
    
    async def get_security_status(self) -> Dict[str, Any]:
        """Get comprehensive security status"""
        recent_events = list(self.security_events)[-50:]  # Last 50 events
        
        # Count events by type and severity
        event_counts = defaultdict(int)
        severity_counts = defaultdict(int)
        
        for event in recent_events:
            event_counts[event.event_type] += 1
            severity_counts[event.severity] += 1
        
        return {
            'blocked_users_count': len(self.blocked_users),
            'blocked_ips_count': len(self.blocked_ips),
            'recent_events_count': len(recent_events),
            'event_types': dict(event_counts),
            'severity_distribution': dict(severity_counts),
            'failed_attempts': dict(self.failed_attempts),
            'rate_limiter_rules': {name: {
                'requests': rule.requests,
                'period': rule.period,
                'burst': rule.burst
            } for name, rule in self.rate_limiter.rules.items()}
        }
    
    async def get_user_security_info(self, user_id: int) -> Dict[str, Any]:
        """Get security information for a specific user"""
        # Rate limit status
        rate_statuses = {}
        for rule_name in self.rate_limiter.rules:
            rate_statuses[rule_name] = await self.rate_limiter.get_rate_limit_status(rule_name, str(user_id))
        
        # Recent events for this user
        user_events = [event for event in self.security_events if event.user_id == user_id][-10:]
        
        return {
            'user_id': user_id,
            'is_blocked': user_id in self.blocked_users,
            'is_admin': user_id in self.admin_users,
            'failed_attempts': self.failed_attempts.get(user_id, 0),
            'rate_limits': rate_statuses,
            'recent_events': [
                {
                    'timestamp': event.timestamp,
                    'type': event.event_type,
                    'severity': event.severity,
                    'description': event.description
                } for event in user_events
            ]
        }

# Global security manager instance
security_manager: Optional[SecurityManager] = None

def get_security_manager() -> Optional[SecurityManager]:
    """Get global security manager instance"""
    return security_manager

def initialize_security(cache_system: AdvancedCacheSystem) -> SecurityManager:
    """Initialize global security manager"""
    global security_manager
    security_manager = SecurityManager(cache_system)
    return security_manager