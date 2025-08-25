
import os
import asyncio
import logging
from datetime import datetime, timedelta
from collections import defaultdict, deque
import json
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes, CallbackQueryHandler
from telegram.constants import ParseMode
import pdfplumber
from translator import AdvancedTranslator
from pdf_builder import create_translated_pdf
from api_manager import APIManager
from queue_system import QueueSystem
from user_manager import UserManager
from notification_system import NotificationSystem

# إعداد التسجيل
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

class AdvancedTranslationBot:
    def __init__(self):
        self.token = os.getenv("BOT_TOKEN")
        self.api_manager = APIManager()
        self.queue_system = QueueSystem()
        self.user_manager = UserManager()
        self.notification_system = NotificationSystem()
        self.translator = AdvancedTranslator(self.api_manager)
        
        # إحصائيات النظام
        self.system_stats = {
            'total_requests': 0,
            'successful_translations': 0,
            'failed_requests': 0,
            'active_users': set(),
            'daily_stats': defaultdict(int)
        }
        
    async def start(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        user_id = update.effective_user.id
        username = update.effective_user.username or "مستخدم"
        
        # تسجيل المستخدم الجديد
        self.user_manager.register_user(user_id, username)
        self.system_stats['active_users'].add(user_id)
        
        welcome_text = f"""
🤖 **مرحباً بك في نظام الترجمة المتقدم** 

👋 أهلاً {username}!

✨ **الميزات المتاحة:**
📄 ترجمة ملفات PDF, DOCX, PPTX
🖼️ ترجمة النصوص في الصور
📊 معالجة الجداول والرسوم البيانية
🔄 نظام طابور ذكي
⚡ ترجمة سريعة ودقيقة

🎯 **كيفية الاستخدام:**
1. أرسل أي ملف PDF أو صورة
2. اختر اللغة المطلوبة
3. انتظر المعالجة في الطابور
4. احصل على الترجمة المنسقة

📋 استخدم /help للمساعدة الكاملة
📊 استخدم /status لمعرفة حالة طلباتك
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

    async def help_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        help_text = """
📖 **دليل الاستخدام الكامل**

🎯 **الأوامر المتاحة:**
• `/start` - بدء استخدام البوت
• `/status` - حالة طلباتك الحالية
• `/profile` - ملفك الشخصي
• `/stats` - إحصائيات الاستخدام
• `/feedback` - تقييم الخدمة

📄 **أنواع الملفات المدعومة:**
• PDF - ملفات المستندات
• DOCX - مستندات Word
• PPTX - عروض PowerPoint  
• JPG/PNG - الصور والمسح الضوئي

🌐 **اللغات المدعومة:**
• العربية ↔ الإنجليزية
• الفرنسية ↔ العربية
• الألمانية ↔ العربية
• وأكثر من 50 لغة أخرى

⚡ **مميزات متقدمة:**
• OCR للنصوص في الصور
• الحفاظ على التنسيق الأصلي
• ترجمة الجداول والرسوم
• نظام طابور ذكي
• ترجمة فقرة بفقرة

📊 **حدود الاستخدام:**
• المستخدم العادي: 20 ملف/يوم
• المستخدم المميز: 100 ملف/يوم
• حجم الملف الأقصى: 20 ميجابايت

🔧 للمساعدة التقنية: @support_channel
        """
        await update.message.reply_text(help_text, parse_mode=ParseMode.MARKDOWN)

    async def status_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        user_id = update.effective_user.id
        user_stats = self.user_manager.get_user_stats(user_id)
        queue_position = self.queue_system.get_user_queue_position(user_id)
        
        status_text = f"""
📊 **حالة حسابك**

👤 **معلومات المستخدم:**
🆔 المعرف: `{user_id}`
📅 تاريخ التسجيل: {user_stats.get('join_date', 'غير محدد')}
⭐ المستوى: {user_stats.get('level', 'عادي')}

📈 **إحصائيات اليوم:**
📥 الطلبات: {user_stats.get('daily_requests', 0)}/50
✅ مكتملة: {user_stats.get('completed_today', 0)}
⏳ قيد المعالجة: {user_stats.get('processing', 0)}

🎯 **حالة الطابور:**
📍 موقعك في الطابور: {queue_position if queue_position else 'لا توجد طلبات'}
⏰ الوقت المتوقع: {self.queue_system.estimate_wait_time(user_id)}

📊 **إحصائيات إجمالية:**
📄 إجمالي الملفات: {user_stats.get('total_files', 0)}
⭐ تقييم الخدمة: {user_stats.get('rating', 'لم يتم التقييم')}
        """
        
        keyboard = [
            [InlineKeyboardButton("🔄 تحديث", callback_data="refresh_status")],
            [InlineKeyboardButton("📋 تاريخ الطلبات", callback_data="request_history")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await update.message.reply_text(
            status_text, 
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=reply_markup
        )

    async def handle_file(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        user_id = update.effective_user.id
        
        # فحص حدود المستخدم
        if not self.user_manager.can_process_file(user_id):
            await update.message.reply_text(
                "⚠️ لقد تجاوزت حدودك اليومية للملفات.\n"
                "🔄 جرب مرة أخرى غداً أو ترقى لحساب مميز."
            )
            return

        file = await update.message.document.get_file()
        file_name = update.message.document.file_name
        file_size = update.message.document.file_size
        
        # فحص حجم الملف
        if file_size > 20 * 1024 * 1024:  # 20MB
            await update.message.reply_text(
                "❌ حجم الملف كبير جداً.\n"
                "📏 الحد الأقصى: 20 ميجابايت"
            )
            return

        # إضافة للطابور
        task_id = self.queue_system.add_task({
            'user_id': user_id,
            'file': file,
            'file_name': file_name,
            'file_size': file_size,
            'timestamp': datetime.now()
        })

        position = self.queue_system.get_queue_position(task_id)
        wait_time = self.queue_system.estimate_wait_time_for_task(task_id)

        keyboard = [
            [InlineKeyboardButton("🔍 تتبع الطلب", callback_data=f"track_{task_id}")],
            [InlineKeyboardButton("❌ إلغاء", callback_data=f"cancel_{task_id}")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)

        await update.message.reply_text(
            f"📥 **تم استلام ملفك!**\n\n"
            f"📄 الملف: `{file_name}`\n"
            f"📊 الحجم: {file_size / 1024:.1f} KB\n"
            f"📍 موقعك في الطابور: {position}\n"
            f"⏰ الوقت المتوقع: {wait_time}\n\n"
            f"🔄 سيتم إشعارك عند اكتمال المعالجة",
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=reply_markup
        )

        # بدء معالجة الطابور
        await self.process_queue()

    async def process_queue(self):
        """معالجة الطابور"""
        while self.queue_system.has_pending_tasks():
            task = self.queue_system.get_next_task()
            if task:
                await self.process_file_task(task)

    async def process_file_task(self, task):
        """معالجة مهمة ملف واحد"""
        try:
            user_id = task['user_id']
            file = task['file']
            file_name = task['file_name']
            
            # إشعار بدء المعالجة
            await self.notification_system.notify_user(
                user_id, 
                f"🔄 بدأت معالجة ملف: {file_name}"
            )

            # تحميل الملف
            file_path = f"temp_{user_id}_{file_name}"
            await file.download_to_drive(file_path)

            # استخراج النص
            await self.notification_system.notify_user(
                user_id, 
                "📖 جاري استخراج النصوص..."
            )

            text = await self.extract_text_from_file(file_path)
            
            if not text.strip():
                await self.notification_system.notify_user(
                    user_id, 
                    "❌ لم يتم العثور على نص قابل للترجمة في الملف"
                )
                return

            # الترجمة
            await self.notification_system.notify_user(
                user_id, 
                "🌐 جاري الترجمة..."
            )

            translated_text = await self.translator.translate_advanced(text, user_id)

            # إنشاء الملف المترجم
            await self.notification_system.notify_user(
                user_id, 
                "📄 جاري إنشاء الملف المترجم..."
            )

            output_path = f"translated_{user_id}_{file_name}"
            await self.create_translated_file(translated_text, output_path, file_name)

            # إرسال النتيجة
            with open(output_path, "rb") as output_file:
                await self.notification_system.send_file(
                    user_id, 
                    output_file, 
                    f"✅ تمت الترجمة بنجاح!\n📄 الملف: {file_name}"
                )

            # تحديث الإحصائيات
            self.user_manager.update_user_stats(user_id, 'completed')
            self.system_stats['successful_translations'] += 1

            # تنظيف الملفات المؤقتة
            os.remove(file_path)
            os.remove(output_path)

        except Exception as e:
            logger.error(f"Error processing file for user {user_id}: {e}")
            await self.notification_system.notify_user(
                user_id, 
                f"❌ حدث خطأ أثناء معالجة الملف: {str(e)}"
            )
            self.system_stats['failed_requests'] += 1

    async def extract_text_from_file(self, file_path):
        """استخراج النص من الملفات المختلفة"""
        file_extension = file_path.lower().split('.')[-1]
        
        if file_extension == 'pdf':
            text = ""
            with pdfplumber.open(file_path) as pdf:
                for page in pdf.pages:
                    page_text = page.extract_text()
                    if page_text:
                        text += page_text + "\n"
            return text
        
        # يمكن إضافة دعم لصيغ أخرى هنا
        return ""

    async def create_translated_file(self, translated_text, output_path, original_name):
        """إنشاء الملف المترجم"""
        file_extension = original_name.lower().split('.')[-1]
        
        if file_extension == 'pdf':
            create_translated_pdf(translated_text, output_path)
        
        # يمكن إضافة دعم لصيغ أخرى هنا

    async def handle_callback(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """معالج الأزرار التفاعلية"""
        query = update.callback_query
        await query.answer()
        
        if query.data == "my_stats":
            await self.show_user_stats(query)
        elif query.data == "help":
            await self.show_help(query)
        elif query.data.startswith("track_"):
            task_id = query.data.split("_")[1]
            await self.track_task(query, task_id)

    async def show_user_stats(self, query):
        """عرض إحصائيات المستخدم"""
        user_id = query.from_user.id
        stats = self.user_manager.get_detailed_stats(user_id)
        
        stats_text = f"""
📊 **إحصائياتك التفصيلية**

📈 **الاستخدام:**
• الملفات اليوم: {stats['daily_files']}/50
• إجمالي الملفات: {stats['total_files']}
• معدل النجاح: {stats['success_rate']}%

⏰ **الوقت:**
• متوسط وقت المعالجة: {stats['avg_processing_time']}
• إجمالي الوقت المستخدم: {stats['total_time']}

🎯 **التقييم:**
• تقييمك للخدمة: {stats['rating']}/5
• عدد التقييمات: {stats['rating_count']}
        """
        
        await query.edit_message_text(
            stats_text, 
            parse_mode=ParseMode.MARKDOWN
        )

    # أوامر الإدارة (للمشرفين فقط)
    async def admin_stats(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """إحصائيات النظام للمشرفين"""
        user_id = update.effective_user.id
        if not self.user_manager.is_admin(user_id):
            await update.message.reply_text("❌ ليس لديك صلاحية للوصول لهذا الأمر")
            return

        stats = {
            'total_users': len(self.user_manager.users),
            'active_users_today': len(self.system_stats['active_users']),
            'total_requests': self.system_stats['total_requests'],
            'successful_translations': self.system_stats['successful_translations'],
            'queue_size': self.queue_system.get_queue_size(),
            'api_status': self.api_manager.get_status_summary()
        }

        stats_text = f"""
🔧 **إحصائيات النظام**

👥 **المستخدمين:**
• إجمالي المستخدمين: {stats['total_users']}
• النشطين اليوم: {stats['active_users_today']}

📊 **الطلبات:**
• إجمالي الطلبات: {stats['total_requests']}
• الناجحة: {stats['successful_translations']}
• معدل النجاح: {(stats['successful_translations']/max(stats['total_requests'],1)*100):.1f}%

🎯 **النظام:**
• حجم الطابور: {stats['queue_size']}
• حالة API: {stats['api_status']}
        """

        await update.message.reply_text(stats_text, parse_mode=ParseMode.MARKDOWN)

def main():
    bot = AdvancedTranslationBot()
    application = Application.builder().token(bot.token).build()
    
    # إضافة المعالجات
    application.add_handler(CommandHandler("start", bot.start))
    application.add_handler(CommandHandler("help", bot.help_command))
    application.add_handler(CommandHandler("status", bot.status_command))
    application.add_handler(CommandHandler("admin_stats", bot.admin_stats))
    application.add_handler(MessageHandler(filters.Document, bot.handle_file))
    application.add_handler(CallbackQueryHandler(bot.handle_callback))
    
    logger.info("🚀 بدء تشغيل البوت المتقدم...")
    application.run_polling()

if __name__ == "__main__":
    main()
