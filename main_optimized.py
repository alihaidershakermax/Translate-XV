"""
Optimized Translation Bot with Advanced Performance Features
- Async processing with connection pooling
- Advanced caching and database integration
- Enhanced error handling and monitoring
- Production-ready configuration
"""

import os
import asyncio
import logging
import signal
import aiohttp
from datetime import datetime, timedelta
from typing import Optional, Dict, Any, List
from concurrent.futures import ThreadPoolExecutor
import time

# Telegram imports
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, Bot
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes, CallbackQueryHandler
from telegram.constants import ParseMode
from telegram.error import TelegramError, RetryAfter, TimedOut

# Local imports
from config import get_settings, validate_environment
from cache_system import AdvancedCacheSystem, CacheKey
from database import initialize_database, get_database_manager
from translator import AdvancedTranslator
from pdf_builder import create_translated_pdf
from api_manager import APIManager
from queue_system import QueueSystem
from user_manager import UserManager
from notification_system import NotificationSystem

# Configure logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO,
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler('bot.log', encoding='utf-8')
    ]
)
logger = logging.getLogger(__name__)

class OptimizedTranslationBot:
    """Production-optimized translation bot with advanced features"""
    
    def __init__(self):
        # Load configuration
        self.settings = get_settings()
        
        # Initialize core components
        self.api_manager = APIManager()
        self.cache_system = AdvancedCacheSystem(
            redis_url=self.settings.redis_url,
            default_ttl=self.settings.cache_ttl_seconds
        )
        
        # Initialize database
        self.db_manager = initialize_database(self.settings.database_url)
        
        # Initialize business logic components
        self.queue_system = QueueSystem()
        self.user_manager = UserManager()
        self.notification_system = NotificationSystem()
        self.translator = AdvancedTranslator(self.api_manager)
        self.translator.cache_system = self.cache_system  # Add caching to translator
        
        # Application instance
        self.application: Optional[Application] = None
        
        # Performance monitoring
        self.start_time = time.time()
        self.request_count = 0
        self.error_count = 0
        
        # Connection pool for HTTP requests
        self.session: Optional[aiohttp.ClientSession] = None
        
        # Thread pool for CPU-intensive tasks
        self.thread_pool = ThreadPoolExecutor(max_workers=self.settings.max_workers)
        
        # Background tasks
        self.background_tasks: List[asyncio.Task] = []
        
        # Graceful shutdown flag
        self.shutdown_requested = False
    
    async def initialize(self):
        """Initialize all async components"""
        logger.info("Initializing optimized translation bot...")
        
        # Validate environment
        if not validate_environment():
            raise RuntimeError("Environment validation failed")
        
        # Create HTTP session with connection pooling
        connector = aiohttp.TCPConnector(
            limit=100,  # Total connection pool size
            limit_per_host=20,  # Per-host connection limit
            ttl_dns_cache=300,  # DNS cache TTL
            use_dns_cache=True,
            keepalive_timeout=30,
            enable_cleanup_closed=True
        )
        
        timeout = aiohttp.ClientTimeout(total=30, connect=10)
        self.session = aiohttp.ClientSession(
            connector=connector,
            timeout=timeout,
            headers={'User-Agent': 'TranslationBot/1.0'}
        )
        
        # Initialize database tables
        if self.db_manager.is_initialized:
            await self.db_manager.create_tables()
        
        # Setup Telegram application
        await self._setup_telegram_application()
        
        # Start background tasks
        await self._start_background_tasks()
        
        logger.info("Bot initialization completed successfully")
    
    async def _setup_telegram_application(self):
        """Setup Telegram application with optimizations"""
        # Create application with connection pooling
        builder = Application.builder()
        builder.token(self.settings.bot_token)
        builder.concurrent_updates(True)  # Enable concurrent update processing
        builder.pool_timeout(30)
        builder.read_timeout(30)
        builder.write_timeout(30)
        builder.connect_timeout(10)
        
        self.application = builder.build()
        
        # Add handlers
        self.application.add_handler(CommandHandler("start", self.start_command))
        self.application.add_handler(CommandHandler("help", self.help_command))
        self.application.add_handler(CommandHandler("status", self.status_command))
        self.application.add_handler(CommandHandler("stats", self.stats_command))
        self.application.add_handler(CallbackQueryHandler(self.button_callback))
        self.application.add_handler(MessageHandler(filters.Document.ALL, self.handle_document))
        self.application.add_handler(MessageHandler(filters.PHOTO, self.handle_photo))
        self.application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, self.handle_text))
        
        # Add error handler
        self.application.add_error_handler(self.error_handler)
    
    async def _start_background_tasks(self):
        """Start background maintenance tasks"""
        # Queue processor
        self.background_tasks.append(
            asyncio.create_task(self._queue_processor())
        )
        
        # Statistics updater
        self.background_tasks.append(
            asyncio.create_task(self._stats_updater())
        )
        
        # Cache cleanup
        self.background_tasks.append(
            asyncio.create_task(self._cache_cleanup())
        )
        
        # Database cleanup
        if self.db_manager.is_initialized:
            self.background_tasks.append(
                asyncio.create_task(self._database_cleanup())
            )
        
        logger.info(f"Started {len(self.background_tasks)} background tasks")
    
    async def start_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Enhanced start command with database integration"""
        user = update.effective_user
        
        # Register/update user in database
        if self.db_manager.is_initialized:
            await self.db_manager.get_or_create_user(
                telegram_id=user.id,
                username=user.username,
                first_name=user.first_name,
                last_name=user.last_name
            )
        
        # Get user stats from cache or database
        cache_key = CacheKey.user_quota_key(user.id)
        user_stats = await self.cache_system.get(cache_key)
        
        if not user_stats and self.db_manager.is_initialized:
            user_stats = await self.db_manager.get_user_stats(user.id)
            if user_stats:
                await self.cache_system.set(cache_key, user_stats, ttl=300)
        
        welcome_text = f"""
🤖 **مرحباً بك في نظام الترجمة المتقدم المُحسَّن** 

👋 أهلاً {user.first_name or user.username}!

✨ **الميزات الجديدة:**
⚡ معالجة فائقة السرعة مع التخزين المؤقت
🔄 نظام طابور ذكي محسّن
📊 قاعدة بيانات متقدمة للإحصائيات
🛡️ أمان وموثوقية عالية
🌐 دعم أكثر من 50 لغة

📋 **كيفية الاستخدام:**
1. أرسل أي ملف PDF أو صورة
2. اختر اللغة المطلوبة
3. احصل على ترجمة فورية عالية الجودة

📊 **حالتك الحالية:**
📥 الطلبات اليوم: {user_stats.get('daily_requests', 0) if user_stats else 0}/{self.settings.daily_limit_per_user}
✅ معدل النجاح: {user_stats.get('success_rate', 0):.1f}% {' ' if user_stats else ''}

استخدم /help للمساعدة الكاملة
        """
        
        keyboard = [
            [InlineKeyboardButton("📊 إحصائياتي", callback_data="my_stats")],
            [InlineKeyboardButton("❓ المساعدة", callback_data="help"),
             InlineKeyboardButton("⚙️ الإعدادات", callback_data="settings")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await update.message.reply_text(
            welcome_text, 
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=reply_markup
        )
    
    async def handle_document(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Optimized document handling with async processing"""
        user_id = update.effective_user.id
        self.request_count += 1
        
        try:
            # Check user limits with caching
            if not await self._check_user_limits(user_id):
                await update.message.reply_text(
                    "⚠️ لقد تجاوزت حدودك اليومية للملفات.\n"
                    "🔄 جرب مرة أخرى غداً أو ترقى لحساب مميز."
                )
                return
            
            document = update.message.document
            
            # Validate file
            if document.file_size > self.settings.max_file_size_mb * 1024 * 1024:
                await update.message.reply_text(
                    f"❌ حجم الملف كبير جداً.\n"
                    f"📏 الحد الأقصى: {self.settings.max_file_size_mb} ميجابايت"
                )
                return
            
            # Check file hash for duplicates
            file_bytes = await document.get_file().download_as_bytearray()
            file_hash = CacheKey.get_file_hash(bytes(file_bytes))
            
            # Check if file was already processed
            cache_key = CacheKey.file_processing_key(file_hash)
            cached_result = await self.cache_system.get(cache_key)
            
            if cached_result:
                logger.info(f"Serving cached result for file hash: {file_hash[:12]}...")
                await self._send_cached_result(update, cached_result)
                return
            
            # Add to queue for processing
            task_data = {
                'user_id': user_id,
                'file_bytes': file_bytes,
                'file_name': document.file_name,
                'file_size': document.file_size,
                'file_hash': file_hash,
                'message_id': update.message.message_id,
                'chat_id': update.effective_chat.id,
                'timestamp': datetime.now()
            }
            
            task_id = self.queue_system.add_task(task_data)
            
            # Send confirmation with tracking
            position = self.queue_system.get_queue_position(task_id)
            wait_time = self.queue_system.estimate_wait_time_for_task(task_id)
            
            keyboard = [
                [InlineKeyboardButton("🔍 تتبع الطلب", callback_data=f"track_{task_id}")],
                [InlineKeyboardButton("❌ إلغاء", callback_data=f"cancel_{task_id}")]
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)
            
            await update.message.reply_text(
                f"📥 **تم استلام ملفك!**\n\n"
                f"📄 الملف: `{document.file_name}`\n"
                f"📊 الحجم: {document.file_size / 1024:.1f} KB\n"
                f"📍 موقعك في الطابور: {position}\n"
                f"⏰ الوقت المتوقع: {wait_time}\n\n"
                f"🔄 سيتم إشعارك عند اكتمال المعالجة",
                parse_mode=ParseMode.MARKDOWN,
                reply_markup=reply_markup
            )
            
            # Update user usage
            await self._update_user_usage(user_id, document.file_size)
            
        except Exception as e:
            logger.error(f"Error handling document from user {user_id}: {e}")
            self.error_count += 1
            await update.message.reply_text(
                "❌ حدث خطأ أثناء معالجة الملف. يرجى المحاولة مرة أخرى."
            )
    
    async def _check_user_limits(self, user_id: int) -> bool:
        """Check user limits with caching"""
        cache_key = CacheKey.user_quota_key(user_id)
        usage_data = await self.cache_system.get(cache_key)
        
        if usage_data is None:
            # Get from database if available
            if self.db_manager.is_initialized:
                usage = await self.db_manager.get_user_daily_usage(user_id)
                usage_data = {
                    'requests_count': usage.requests_count if usage else 0,
                    'date': datetime.now().strftime('%Y-%m-%d')
                }
            else:
                usage_data = {'requests_count': 0, 'date': datetime.now().strftime('%Y-%m-%d')}
            
            await self.cache_system.set(cache_key, usage_data, ttl=3600)
        
        # Check if date changed
        current_date = datetime.now().strftime('%Y-%m-%d')
        if usage_data.get('date') != current_date:
            usage_data = {'requests_count': 0, 'date': current_date}
            await self.cache_system.set(cache_key, usage_data, ttl=3600)
        
        return usage_data['requests_count'] < self.settings.daily_limit_per_user
    
    async def _update_user_usage(self, user_id: int, file_size: int):
        """Update user usage statistics"""
        cache_key = CacheKey.user_quota_key(user_id)
        
        # Update cache
        await self.cache_system.increment(cache_key + ":requests", 1, ttl=86400)
        
        # Update database
        if self.db_manager.is_initialized:
            await self.db_manager.update_user_daily_usage(
                user_id=user_id,
                increment_requests=1,
                file_size=file_size
            )
    
    async def _queue_processor(self):
        """Background queue processor"""
        logger.info("Queue processor started")
        
        while not self.shutdown_requested:
            try:
                # Process up to max_concurrent_translations tasks
                active_tasks = []
                
                for _ in range(self.settings.max_concurrent_translations):
                    task = self.queue_system.get_next_task()
                    if task:
                        active_tasks.append(
                            asyncio.create_task(self._process_translation_task(task))
                        )
                
                if active_tasks:
                    await asyncio.gather(*active_tasks, return_exceptions=True)
                else:
                    await asyncio.sleep(5)  # Wait 5 seconds if no tasks
                    
            except Exception as e:
                logger.error(f"Error in queue processor: {e}")
                await asyncio.sleep(10)
    
    async def _process_translation_task(self, task):
        """Process a single translation task"""
        task_id = task.id
        user_id = task.user_id
        
        try:
            logger.info(f"Processing task {task_id} for user {user_id}")
            start_time = time.time()
            
            # Extract text from file
            extracted_text = await self._extract_text_async(task.file_bytes, task.file_name)
            
            if not extracted_text.strip():
                await self._notify_user_error(user_id, "لم يتم العثور على نص قابل للترجمة")
                self.queue_system.complete_task(task_id, success=False)
                return
            
            # Translate text with caching
            translated_text = await self.translator.translate_advanced(
                extracted_text, user_id, target_lang="ar"
            )
            
            # Create output file
            output_data = await self._create_output_file_async(
                translated_text, task.file_name
            )
            
            # Cache the result
            cache_key = CacheKey.file_processing_key(task.file_hash)
            cache_data = {
                'translated_text': translated_text,
                'output_data': output_data,
                'original_name': task.file_name,
                'processed_at': datetime.now().isoformat()
            }
            await self.cache_system.set(cache_key, cache_data, ttl=7200)  # 2 hours
            
            # Send result to user
            await self._send_translation_result(user_id, output_data, task.file_name)
            
            # Update statistics
            processing_time = time.time() - start_time
            await self._update_success_stats(user_id, processing_time)
            
            self.queue_system.complete_task(task_id, success=True)
            logger.info(f"Task {task_id} completed in {processing_time:.2f} seconds")
            
        except Exception as e:
            logger.error(f"Error processing task {task_id}: {e}")
            await self._notify_user_error(user_id, f"حدث خطأ أثناء المعالجة: {str(e)}")
            self.queue_system.complete_task(task_id, success=False)
            self.error_count += 1
    
    async def _extract_text_async(self, file_bytes: bytes, file_name: str) -> str:
        """Extract text from file asynchronously"""
        # Run CPU-intensive text extraction in thread pool
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(
            self.thread_pool, 
            self._extract_text_sync, 
            file_bytes, 
            file_name
        )
    
    def _extract_text_sync(self, file_bytes: bytes, file_name: str) -> str:
        """Synchronous text extraction (runs in thread pool)"""
        # Import here to avoid blocking the main thread
        import pdfplumber
        from PIL import Image
        import pytesseract
        import io
        
        file_ext = file_name.lower().split('.')[-1]
        
        try:
            if file_ext == 'pdf':
                with io.BytesIO(file_bytes) as pdf_file:
                    with pdfplumber.open(pdf_file) as pdf:
                        text = ""
                        for page in pdf.pages:
                            page_text = page.extract_text()
                            if page_text:
                                text += page_text + "\n"
                return text
            
            elif file_ext in ['jpg', 'jpeg', 'png', 'bmp', 'tiff']:
                with io.BytesIO(file_bytes) as img_file:
                    image = Image.open(img_file)
                    text = pytesseract.image_to_string(image, lang='ara+eng')
                return text
            
            else:
                return "نوع الملف غير مدعوم"
                
        except Exception as e:
            logger.error(f"Text extraction error: {e}")
            return ""
    
    async def error_handler(self, update: object, context: ContextTypes.DEFAULT_TYPE):
        """Enhanced error handler with logging"""
        self.error_count += 1
        
        if isinstance(context.error, RetryAfter):
            logger.warning(f"Rate limited. Retry after {context.error.retry_after} seconds")
            await asyncio.sleep(context.error.retry_after)
        elif isinstance(context.error, TimedOut):
            logger.warning("Request timed out")
        else:
            logger.error(f"Update {update} caused error {context.error}")
    
    async def run(self):
        """Run the bot with webhook or polling"""
        await self.initialize()
        
        try:
            if self.settings.webhook_url and self.settings.environment.value == "production":
                # Use webhook in production
                await self.application.run_webhook(
                    listen="0.0.0.0",
                    port=int(os.getenv("PORT", 8080)),
                    webhook_url=self.settings.webhook_url,
                    secret_token=self.settings.webhook_secret
                )
            else:
                # Use polling in development
                await self.application.run_polling(drop_pending_updates=True)
                
        except Exception as e:
            logger.error(f"Bot run error: {e}")
            raise
    
    async def shutdown(self):
        """Graceful shutdown"""
        logger.info("Initiating graceful shutdown...")
        self.shutdown_requested = True
        
        # Cancel background tasks
        for task in self.background_tasks:
            task.cancel()
        
        if self.background_tasks:
            await asyncio.gather(*self.background_tasks, return_exceptions=True)
        
        # Close connections
        if self.session:
            await self.session.close()
        
        if self.db_manager:
            await self.db_manager.close()
        
        # Shutdown thread pool
        self.thread_pool.shutdown(wait=True)
        
        logger.info("Shutdown completed")

async def main():
    """Main entry point with signal handling"""
    bot = OptimizedTranslationBot()
    
    # Setup signal handlers for graceful shutdown
    def signal_handler(signum, frame):
        logger.info(f"Received signal {signum}")
        asyncio.create_task(bot.shutdown())
    
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)
    
    try:
        await bot.run()
    except KeyboardInterrupt:
        logger.info("Received keyboard interrupt")
    finally:
        await bot.shutdown()

if __name__ == "__main__":
    asyncio.run(main())