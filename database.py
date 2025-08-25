"""
Database integration system for the translation bot.
Handles user data, translation history, and analytics.
"""

import asyncio
import logging
from datetime import datetime, timedelta
from typing import Optional, List, Dict, Any
from sqlalchemy import create_engine, Column, Integer, String, DateTime, Text, Boolean, Float, JSON
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from sqlalchemy.sql import func
import json

logger = logging.getLogger(__name__)

Base = declarative_base()

class User(Base):
    """User model for storing user information"""
    __tablename__ = 'users'
    
    id = Column(Integer, primary_key=True, index=True)
    telegram_id = Column(Integer, unique=True, index=True, nullable=False)
    username = Column(String(255), nullable=True)
    first_name = Column(String(255), nullable=True)
    last_name = Column(String(255), nullable=True)
    language_code = Column(String(10), default='en')
    is_premium = Column(Boolean, default=False)
    daily_limit = Column(Integer, default=50)
    concurrent_limit = Column(Integer, default=3)
    created_at = Column(DateTime, default=datetime.utcnow)
    last_active = Column(DateTime, default=datetime.utcnow)
    total_requests = Column(Integer, default=0)
    successful_requests = Column(Integer, default=0)
    failed_requests = Column(Integer, default=0)
    is_active = Column(Boolean, default=True)
    preferences = Column(JSON, default=dict)

class TranslationRequest(Base):
    """Translation request model for tracking all translations"""
    __tablename__ = 'translation_requests'
    
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, index=True, nullable=False)
    request_id = Column(String(255), unique=True, index=True, nullable=False)
    file_name = Column(String(500), nullable=True)
    file_size = Column(Integer, nullable=True)
    file_type = Column(String(50), nullable=True)
    source_language = Column(String(10), default='auto')
    target_language = Column(String(10), default='ar')
    text_type = Column(String(50), default='general')
    status = Column(String(50), default='pending')  # pending, processing, completed, failed
    api_service = Column(String(50), nullable=True)
    processing_time = Column(Float, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    started_at = Column(DateTime, nullable=True)
    completed_at = Column(DateTime, nullable=True)
    error_message = Column(Text, nullable=True)
    metadata = Column(JSON, default=dict)

class DailyUsage(Base):
    """Daily usage tracking for users"""
    __tablename__ = 'daily_usage'
    
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, index=True, nullable=False)
    date = Column(DateTime, index=True, nullable=False)
    requests_count = Column(Integer, default=0)
    successful_count = Column(Integer, default=0)
    failed_count = Column(Integer, default=0)
    total_file_size = Column(Integer, default=0)
    avg_processing_time = Column(Float, default=0.0)

class SystemStats(Base):
    """System-wide statistics"""
    __tablename__ = 'system_stats'
    
    id = Column(Integer, primary_key=True, index=True)
    date = Column(DateTime, index=True, nullable=False)
    total_users = Column(Integer, default=0)
    active_users = Column(Integer, default=0)
    total_requests = Column(Integer, default=0)
    successful_requests = Column(Integer, default=0)
    failed_requests = Column(Integer, default=0)
    avg_processing_time = Column(Float, default=0.0)
    api_usage = Column(JSON, default=dict)  # Usage stats per API service
    created_at = Column(DateTime, default=datetime.utcnow)

class DatabaseManager:
    """Database manager for handling all database operations"""
    
    def __init__(self, database_url: Optional[str] = None):
        self.database_url = database_url
        self.engine = None
        self.async_session: Optional[async_sessionmaker] = None
        self.is_initialized = False
        
        if database_url:
            self._setup_database()
    
    def _setup_database(self):
        """Setup database connection and session"""
        try:
            # Convert PostgreSQL URL to async if needed
            if self.database_url.startswith('postgresql://'):
                async_url = self.database_url.replace('postgresql://', 'postgresql+asyncpg://', 1)
            else:
                async_url = self.database_url
            
            self.engine = create_async_engine(
                async_url,
                echo=False,
                pool_size=5,
                max_overflow=10,
                pool_timeout=30,
                pool_recycle=3600,
                pool_pre_ping=True
            )
            
            self.async_session = async_sessionmaker(
                self.engine,
                class_=AsyncSession,
                expire_on_commit=False
            )
            
            logger.info("Database connection initialized successfully")
            self.is_initialized = True
            
        except Exception as e:
            logger.error(f"Failed to initialize database: {e}")
            self.is_initialized = False
    
    async def create_tables(self):
        """Create all database tables"""
        if not self.engine:
            logger.warning("Database not initialized, skipping table creation")
            return
        
        try:
            async with self.engine.begin() as conn:
                await conn.run_sync(Base.metadata.create_all)
            logger.info("Database tables created successfully")
        except Exception as e:
            logger.error(f"Failed to create database tables: {e}")
    
    async def get_or_create_user(self, telegram_id: int, username: str = None, 
                                first_name: str = None, last_name: str = None) -> Optional[User]:
        """Get or create a user"""
        if not self.async_session:
            return None
        
        try:
            async with self.async_session() as session:
                # Try to get existing user
                user = await session.get(User, telegram_id)
                
                if user:
                    # Update last active and info if changed
                    user.last_active = datetime.utcnow()
                    if username and user.username != username:
                        user.username = username
                    if first_name and user.first_name != first_name:
                        user.first_name = first_name
                    if last_name and user.last_name != last_name:
                        user.last_name = last_name
                else:
                    # Create new user
                    user = User(
                        telegram_id=telegram_id,
                        username=username,
                        first_name=first_name,
                        last_name=last_name
                    )
                    session.add(user)
                
                await session.commit()
                await session.refresh(user)
                return user
                
        except Exception as e:
            logger.error(f"Failed to get/create user {telegram_id}: {e}")
            return None
    
    async def create_translation_request(self, user_id: int, request_id: str, 
                                       file_name: str = None, file_size: int = None,
                                       file_type: str = None, **kwargs) -> Optional[TranslationRequest]:
        """Create a new translation request"""
        if not self.async_session:
            return None
        
        try:
            async with self.async_session() as session:
                request = TranslationRequest(
                    user_id=user_id,
                    request_id=request_id,
                    file_name=file_name,
                    file_size=file_size,
                    file_type=file_type,
                    **kwargs
                )
                session.add(request)
                await session.commit()
                await session.refresh(request)
                return request
                
        except Exception as e:
            logger.error(f"Failed to create translation request: {e}")
            return None
    
    async def update_translation_request(self, request_id: str, **updates) -> bool:
        """Update a translation request"""
        if not self.async_session:
            return False
        
        try:
            async with self.async_session() as session:
                request = await session.get(TranslationRequest, {'request_id': request_id})
                if request:
                    for key, value in updates.items():
                        setattr(request, key, value)
                    await session.commit()
                    return True
                return False
                
        except Exception as e:
            logger.error(f"Failed to update translation request {request_id}: {e}")
            return False
    
    async def get_user_daily_usage(self, user_id: int, date: datetime = None) -> Optional[DailyUsage]:
        """Get user's daily usage for a specific date"""
        if not self.async_session:
            return None
        
        if date is None:
            date = datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)
        
        try:
            async with self.async_session() as session:
                usage = await session.get(DailyUsage, {'user_id': user_id, 'date': date})
                return usage
                
        except Exception as e:
            logger.error(f"Failed to get daily usage for user {user_id}: {e}")
            return None
    
    async def update_user_daily_usage(self, user_id: int, increment_requests: int = 1,
                                    increment_successful: int = 0, increment_failed: int = 0,
                                    file_size: int = 0, processing_time: float = 0.0) -> bool:
        """Update user's daily usage statistics"""
        if not self.async_session:
            return False
        
        today = datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)
        
        try:
            async with self.async_session() as session:
                usage = await session.get(DailyUsage, {'user_id': user_id, 'date': today})
                
                if not usage:
                    usage = DailyUsage(user_id=user_id, date=today)
                    session.add(usage)
                
                usage.requests_count += increment_requests
                usage.successful_count += increment_successful
                usage.failed_count += increment_failed
                usage.total_file_size += file_size
                
                # Update average processing time
                if processing_time > 0:
                    total_successful = usage.successful_count
                    if total_successful > 0:
                        current_total_time = usage.avg_processing_time * (total_successful - increment_successful)
                        new_total_time = current_total_time + processing_time
                        usage.avg_processing_time = new_total_time / total_successful
                
                await session.commit()
                return True
                
        except Exception as e:
            logger.error(f"Failed to update daily usage for user {user_id}: {e}")
            return False
    
    async def get_user_stats(self, user_id: int) -> Dict[str, Any]:
        """Get comprehensive user statistics"""
        if not self.async_session:
            return {}
        
        try:
            async with self.async_session() as session:
                user = await session.get(User, user_id)
                if not user:
                    return {}
                
                today = datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)
                daily_usage = await session.get(DailyUsage, {'user_id': user_id, 'date': today})
                
                stats = {
                    'user_id': user.telegram_id,
                    'username': user.username,
                    'join_date': user.created_at.strftime('%Y-%m-%d'),
                    'is_premium': user.is_premium,
                    'total_requests': user.total_requests,
                    'successful_requests': user.successful_requests,
                    'failed_requests': user.failed_requests,
                    'success_rate': (user.successful_requests / max(user.total_requests, 1)) * 100,
                    'daily_requests': daily_usage.requests_count if daily_usage else 0,
                    'daily_limit': user.daily_limit,
                    'remaining_today': user.daily_limit - (daily_usage.requests_count if daily_usage else 0)
                }
                
                return stats
                
        except Exception as e:
            logger.error(f"Failed to get user stats for {user_id}: {e}")
            return {}
    
    async def update_system_stats(self, api_usage: Dict[str, int] = None) -> bool:
        """Update daily system statistics"""
        if not self.async_session:
            return False
        
        today = datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)
        
        try:
            async with self.async_session() as session:
                # Get today's stats or create new
                stats = await session.get(SystemStats, {'date': today})
                if not stats:
                    stats = SystemStats(date=today)
                    session.add(stats)
                
                # Count active users today
                daily_users = await session.execute(
                    "SELECT COUNT(DISTINCT user_id) FROM daily_usage WHERE date = :date",
                    {'date': today}
                )
                stats.active_users = daily_users.scalar() or 0
                
                # Count total users
                total_users = await session.execute("SELECT COUNT(*) FROM users WHERE is_active = true")
                stats.total_users = total_users.scalar() or 0
                
                # Update API usage if provided
                if api_usage:
                    current_api_usage = stats.api_usage or {}
                    for api, count in api_usage.items():
                        current_api_usage[api] = current_api_usage.get(api, 0) + count
                    stats.api_usage = current_api_usage
                
                await session.commit()
                return True
                
        except Exception as e:
            logger.error(f"Failed to update system stats: {e}")
            return False
    
    async def cleanup_old_data(self, days_to_keep: int = 30) -> bool:
        """Clean up old data to manage database size"""
        if not self.async_session:
            return False
        
        cutoff_date = datetime.utcnow() - timedelta(days=days_to_keep)
        
        try:
            async with self.async_session() as session:
                # Delete old translation requests
                await session.execute(
                    "DELETE FROM translation_requests WHERE created_at < :cutoff_date",
                    {'cutoff_date': cutoff_date}
                )
                
                # Delete old daily usage records
                await session.execute(
                    "DELETE FROM daily_usage WHERE date < :cutoff_date",
                    {'cutoff_date': cutoff_date}
                )
                
                # Delete old system stats
                await session.execute(
                    "DELETE FROM system_stats WHERE date < :cutoff_date",
                    {'cutoff_date': cutoff_date}
                )
                
                await session.commit()
                logger.info(f"Cleaned up data older than {days_to_keep} days")
                return True
                
        except Exception as e:
            logger.error(f"Failed to cleanup old data: {e}")
            return False
    
    async def health_check(self) -> bool:
        """Check database connection health"""
        if not self.engine:
            return False
        
        try:
            async with self.engine.begin() as conn:
                await conn.execute("SELECT 1")
            return True
        except Exception as e:
            logger.error(f"Database health check failed: {e}")
            return False
    
    async def close(self):
        """Close database connections"""
        if self.engine:
            await self.engine.dispose()
            logger.info("Database connections closed")

# Global database manager instance
db_manager: Optional[DatabaseManager] = None

def get_database_manager() -> Optional[DatabaseManager]:
    """Get global database manager instance"""
    return db_manager

def initialize_database(database_url: Optional[str] = None) -> DatabaseManager:
    """Initialize global database manager"""
    global db_manager
    db_manager = DatabaseManager(database_url)
    return db_manager