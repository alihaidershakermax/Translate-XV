
import os
import asyncio
import logging
from datetime import datetime
from typing import Dict, List, Optional, Any
from telegram import Bot
from telegram.constants import ParseMode

logger = logging.getLogger(__name__)

class NotificationSystem:
    def __init__(self):
        self.bot_token = os.getenv("BOT_TOKEN")
        self.bot = Bot(token=self.bot_token) if self.bot_token else None
        
        # قنوات الإشعارات
        self.log_channel = os.getenv("LOG_CHANNEL_ID")
        self.announcement_channel = os.getenv("ANNOUNCEMENT_CHANNEL_ID")
        self.admin_channel = os.getenv("ADMIN_CHANNEL_ID")
        
        # إعدادات الإشعارات
        self.notification_settings = {
            'user_notifications': True,
            'admin_notifications': True,
            'system_logs': True,
            'error_alerts': True
        }
        
    async def notify_user(self, user_id: int, message: str, parse_mode: str = ParseMode.MARKDOWN):
        """إرسال إشعار للمستخدم"""
        try:
            if self.bot:
                await self.bot.send_message(
                    chat_id=user_id,
                    text=message,
                    parse_mode=parse_mode
                )
                logger.debug(f"تم إرسال إشعار للمستخدم {user_id}")
        except Exception as e:
            logger.error(f"خطأ في إرسال إشعار للمستخدم {user_id}: {e}")
            
    async def send_file(self, user_id: int, file, caption: str = ""):
        """إرسال ملف للمستخدم"""
        try:
            if self.bot:
                await self.bot.send_document(
                    chat_id=user_id,
                    document=file,
                    caption=caption,
                    parse_mode=ParseMode.MARKDOWN
                )
                logger.debug(f"تم إرسال ملف للمستخدم {user_id}")
        except Exception as e:
            logger.error(f"خطأ في إرسال ملف للمستخدم {user_id}: {e}")
            
    async def log_system_event(self, event_type: str, message: str, data: Dict = None):
        """تسجيل حدث في قناة السجلات"""
        if not self.log_channel or not self.notification_settings['system_logs']:
            return
            
        timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        
        log_message = f"""
🔧 **[{event_type.upper()}]** - {message}
⏰ الوقت: `{timestamp}`
"""
        
        if data:
            log_message += f"📊 البيانات: `{data}`\n"
            
        try:
            if self.bot:
                await self.bot.send_message(
                    chat_id=self.log_channel,
                    text=log_message,
                    parse_mode=ParseMode.MARKDOWN
                )
        except Exception as e:
            logger.error(f"خطأ في إرسال سجل النظام: {e}")
            
    async def send_error_alert(self, error_type: str, error_message: str, user_id: int = None):
        """إرسال تنبيه خطأ للمشرفين"""
        if not self.admin_channel or not self.notification_settings['error_alerts']:
            return
            
        timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        
        alert_message = f"""
🚨 **[خطأ في النظام]** - {error_type}
⏰ الوقت: `{timestamp}`
📝 الرسالة: `{error_message}`
"""
        
        if user_id:
            alert_message += f"👤 المستخدم: `{user_id}`\n"
            
        alert_message += "\n⚠️ يرجى مراجعة النظام فوراً"
        
        try:
            if self.bot:
                await self.bot.send_message(
                    chat_id=self.admin_channel,
                    text=alert_message,
                    parse_mode=ParseMode.MARKDOWN
                )
        except Exception as e:
            logger.error(f"خطأ في إرسال تنبيه الخطأ: {e}")
            
    async def broadcast_announcement(self, message: str, user_ids: List[int] = None):
        """بث إعلان للمستخدمين"""
        if not self.announcement_channel:
            return
            
        # إرسال للقناة العامة
        try:
            if self.bot:
                await self.bot.send_message(
                    chat_id=self.announcement_channel,
                    text=f"📢 **إعلان عام**\n\n{message}",
                    parse_mode=ParseMode.MARKDOWN
                )
        except Exception as e:
            logger.error(f"خطأ في بث الإعلان: {e}")
            
        # إرسال لمستخدمين محددين
        if user_ids:
            for user_id in user_ids:
                try:
                    await asyncio.sleep(0.1)  # تجنب rate limiting
                    await self.notify_user(user_id, f"📢 **إعلان**\n\n{message}")
                except Exception as e:
                    logger.error(f"خطأ في إرسال إعلان للمستخدم {user_id}: {e}")
                    
    async def send_daily_report(self, stats: Dict):
        """إرسال التقرير اليومي"""
        if not self.admin_channel:
            return
            
        date = datetime.now().strftime('%Y-%m-%d')
        
        report = f"""
📊 **التقرير اليومي - {date}**

👥 **المستخدمين:**
• النشطين اليوم: {stats.get('active_users', 0)}
• الجدد: {stats.get('new_users', 0)}
• الإجمالي: {stats.get('total_users', 0)}

📄 **الملفات:**
• تم معالجتها: {stats.get('processed_files', 0)}
• نجحت: {stats.get('successful_files', 0)}
• فشلت: {stats.get('failed_files', 0)}
• معدل النجاح: {stats.get('success_rate', 0):.1f}%

⚡ **الأداء:**
• متوسط وقت المعالجة: {stats.get('avg_processing_time', 0):.1f}s
• الطلبات المكتملة: {stats.get('completed_requests', 0)}
• حجم الطابور: {stats.get('queue_size', 0)}

🔧 **النظام:**
• حالة APIs: {stats.get('api_status', 'غير محدد')}
• استخدام الخادم: {stats.get('server_usage', 'غير محدد')}
• الذاكرة: {stats.get('memory_usage', 'غير محدد')}

✅ النظام يعمل بشكل طبيعي
        """
        
        try:
            if self.bot:
                await self.bot.send_message(
                    chat_id=self.admin_channel,
                    text=report,
                    parse_mode=ParseMode.MARKDOWN
                )
        except Exception as e:
            logger.error(f"خطأ في إرسال التقرير اليومي: {e}")
            
    async def notify_queue_status(self, user_id: int, position: int, estimated_time: str):
        """إشعار حالة الطابور للمستخدم"""
        message = f"""
📍 **حالة طلبك في الطابور**

🎯 موقعك: **{position}**
⏰ الوقت المتوقع: **{estimated_time}**

🔄 سيتم إشعارك عند بدء المعالجة
        """
        
        await self.notify_user(user_id, message)
        
    async def notify_processing_start(self, user_id: int, file_name: str):
        """إشعار بدء معالجة الملف"""
        message = f"""
🚀 **بدأت معالجة ملفك**

📄 الملف: `{file_name}`
⏳ المعالجة جارية...

🔔 سيتم إرسال النتيجة قريباً
        """
        
        await self.notify_user(user_id, message)
        
    async def notify_completion(self, user_id: int, file_name: str, success: bool, error_msg: str = None):
        """إشعار اكتمال المعالجة"""
        if success:
            message = f"""
✅ **تم الانتهاء من الترجمة بنجاح!**

📄 الملف: `{file_name}`
🎉 تم إرسال الملف المترجم

⭐ لا تنس تقييم الخدمة
            """
        else:
            message = f"""
❌ **فشل في معالجة الملف**

📄 الملف: `{file_name}`
🔧 السبب: {error_msg or 'خطأ غير محدد'}

💡 جرب مرة أخرى أو اتصل بالدعم
            """
            
        await self.notify_user(user_id, message)
        
    async def send_maintenance_notice(self, message: str, duration: str = None):
        """إرسال إشعار صيانة"""
        maintenance_msg = f"""
🔧 **إشعار صيانة النظام**

📝 {message}
"""
        
        if duration:
            maintenance_msg += f"⏰ المدة المتوقعة: {duration}\n"
            
        maintenance_msg += "\n🙏 نعتذر عن أي إزعاج"
        
        # إرسال للقناة العامة
        if self.announcement_channel:
            try:
                if self.bot:
                    await self.bot.send_message(
                        chat_id=self.announcement_channel,
                        text=maintenance_msg,
                        parse_mode=ParseMode.MARKDOWN
                    )
            except Exception as e:
                logger.error(f"خطأ في إرسال إشعار الصيانة: {e}")
                
    async def notify_api_rotation(self, old_service: str, new_service: str, reason: str):
        """إشعار تبديل مزود API"""
        message = f"""
🔄 **تم تبديل مزود API**

📊 من: {old_service}
🎯 إلى: {new_service}
💡 السبب: {reason}

⚡ الخدمة تعمل بشكل طبيعي
        """
        
        await self.log_system_event("API_ROTATION", message)
        
    def configure_notifications(self, settings: Dict):
        """تكوين إعدادات الإشعارات"""
        self.notification_settings.update(settings)
        logger.info(f"تم تحديث إعدادات الإشعارات: {settings}")
        
    async def test_channels(self) -> Dict[str, bool]:
        """اختبار قنوات الإشعارات"""
        results = {}
        
        channels = {
            'log_channel': self.log_channel,
            'announcement_channel': self.announcement_channel,
            'admin_channel': self.admin_channel
        }
        
        for channel_name, channel_id in channels.items():
            if channel_id and self.bot:
                try:
                    await self.bot.send_message(
                        chat_id=channel_id,
                        text="🧪 اختبار القناة - تعمل بشكل صحيح",
                        parse_mode=ParseMode.MARKDOWN
                    )
                    results[channel_name] = True
                except Exception as e:
                    logger.error(f"فشل اختبار {channel_name}: {e}")
                    results[channel_name] = False
            else:
                results[channel_name] = False
                
        return results
