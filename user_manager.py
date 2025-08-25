
import json
import os
from datetime import datetime, timedelta
from typing import Dict, List, Optional
import logging
from dataclasses import dataclass, asdict
from collections import defaultdict

logger = logging.getLogger(__name__)

@dataclass
class User:
    user_id: int
    username: str
    join_date: datetime
    level: str = "عادي"  # عادي، مميز، مدير
    daily_requests: int = 0
    total_files: int = 0
    completed_files: int = 0
    failed_files: int = 0
    total_processing_time: float = 0.0
    last_activity: Optional[datetime] = None
    rating: Optional[float] = None
    rating_count: int = 0
    preferences: Dict = None
    
    def __post_init__(self):
        if self.preferences is None:
            self.preferences = {
                'language': 'ar',
                'notifications': True,
                'auto_download': True
            }

class UserManager:
    def __init__(self):
        self.users: Dict[int, User] = {}
        self.admins = set()
        self.daily_stats = defaultdict(lambda: defaultdict(int))
        self.load_users()
        self.load_admins()
        
    def load_users(self):
        """تحميل بيانات المستخدمين من الملف"""
        try:
            if os.path.exists('users_data.json'):
                with open('users_data.json', 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    for user_data in data:
                        user = User(**user_data)
                        # تحويل التواريخ من نص إلى datetime
                        if isinstance(user.join_date, str):
                            user.join_date = datetime.fromisoformat(user.join_date)
                        if user.last_activity and isinstance(user.last_activity, str):
                            user.last_activity = datetime.fromisoformat(user.last_activity)
                        self.users[user.user_id] = user
                logger.info(f"تم تحميل {len(self.users)} مستخدم")
        except Exception as e:
            logger.error(f"خطأ في تحميل بيانات المستخدمين: {e}")
            
    def save_users(self):
        """حفظ بيانات المستخدمين في الملف"""
        try:
            users_data = []
            for user in self.users.values():
                user_dict = asdict(user)
                # تحويل التواريخ إلى نص
                if isinstance(user_dict['join_date'], datetime):
                    user_dict['join_date'] = user_dict['join_date'].isoformat()
                if user_dict['last_activity'] and isinstance(user_dict['last_activity'], datetime):
                    user_dict['last_activity'] = user_dict['last_activity'].isoformat()
                users_data.append(user_dict)
                
            with open('users_data.json', 'w', encoding='utf-8') as f:
                json.dump(users_data, f, ensure_ascii=False, indent=2)
        except Exception as e:
            logger.error(f"خطأ في حفظ بيانات المستخدمين: {e}")
            
    def load_admins(self):
        """تحميل قائمة المشرفين"""
        admin_ids = os.getenv("ADMIN_IDS", "").split(",")
        for admin_id in admin_ids:
            if admin_id.strip().isdigit():
                self.admins.add(int(admin_id.strip()))
        logger.info(f"تم تحميل {len(self.admins)} مشرف")
        
    def register_user(self, user_id: int, username: str) -> User:
        """تسجيل مستخدم جديد"""
        if user_id not in self.users:
            user = User(
                user_id=user_id,
                username=username,
                join_date=datetime.now(),
                last_activity=datetime.now()
            )
            self.users[user_id] = user
            self.save_users()
            logger.info(f"تم تسجيل مستخدم جديد: {username} ({user_id})")
        else:
            # تحديث النشاط
            self.users[user_id].last_activity = datetime.now()
            if self.users[user_id].username != username:
                self.users[user_id].username = username
                
        return self.users[user_id]
        
    def get_user(self, user_id: int) -> Optional[User]:
        """الحصول على بيانات المستخدم"""
        return self.users.get(user_id)
        
    def can_process_file(self, user_id: int) -> bool:
        """فحص إمكانية معالجة ملف للمستخدم"""
        user = self.get_user(user_id)
        if not user:
            return False
            
        # فحص الحد اليومي
        daily_limit = 50 if user.level == "عادي" else 100
        if user.daily_requests >= daily_limit:
            return False
            
        return True
        
    def update_user_stats(self, user_id: int, action: str, **kwargs):
        """تحديث إحصائيات المستخدم"""
        user = self.get_user(user_id)
        if not user:
            return
            
        user.last_activity = datetime.now()
        
        if action == "request":
            user.daily_requests += 1
            user.total_files += 1
            
        elif action == "completed":
            user.completed_files += 1
            processing_time = kwargs.get('processing_time', 0)
            user.total_processing_time += processing_time
            
        elif action == "failed":
            user.failed_files += 1
            
        elif action == "rating":
            rating = kwargs.get('rating', 0)
            if user.rating is None:
                user.rating = rating
                user.rating_count = 1
            else:
                # حساب المتوسط الجديد
                total_rating = user.rating * user.rating_count + rating
                user.rating_count += 1
                user.rating = total_rating / user.rating_count
                
        self.save_users()
        
    def get_user_stats(self, user_id: int) -> Dict:
        """الحصول على إحصائيات المستخدم"""
        user = self.get_user(user_id)
        if not user:
            return {}
            
        success_rate = 0
        if user.total_files > 0:
            success_rate = (user.completed_files / user.total_files) * 100
            
        avg_processing_time = 0
        if user.completed_files > 0:
            avg_processing_time = user.total_processing_time / user.completed_files
            
        return {
            'join_date': user.join_date.strftime('%Y-%m-%d'),
            'level': user.level,
            'daily_requests': user.daily_requests,
            'total_files': user.total_files,
            'completed_today': self._get_completed_today(user_id),
            'processing': self._get_processing_count(user_id),
            'success_rate': f"{success_rate:.1f}",
            'avg_processing_time': f"{avg_processing_time:.1f}s",
            'rating': user.rating or "لم يتم التقييم"
        }
        
    def get_detailed_stats(self, user_id: int) -> Dict:
        """إحصائيات تفصيلية للمستخدم"""
        user = self.get_user(user_id)
        if not user:
            return {}
            
        basic_stats = self.get_user_stats(user_id)
        
        # إحصائيات إضافية
        total_time_formatted = self._format_duration(user.total_processing_time)
        avg_time_formatted = f"{user.total_processing_time / max(user.completed_files, 1):.1f}s"
        
        return {
            **basic_stats,
            'total_time': total_time_formatted,
            'avg_processing_time': avg_time_formatted,
            'rating_count': user.rating_count,
            'last_activity': user.last_activity.strftime('%Y-%m-%d %H:%M') if user.last_activity else 'غير محدد'
        }
        
    def is_admin(self, user_id: int) -> bool:
        """فحص إذا كان المستخدم مشرف"""
        return user_id in self.admins
        
    def promote_user(self, user_id: int, level: str = "مميز"):
        """ترقية مستخدم"""
        user = self.get_user(user_id)
        if user:
            user.level = level
            self.save_users()
            logger.info(f"تم ترقية المستخدم {user_id} إلى {level}")
            
    def reset_daily_stats(self):
        """إعادة تعيين الإحصائيات اليومية"""
        for user in self.users.values():
            user.daily_requests = 0
        self.save_users()
        logger.info("تم إعادة تعيين الإحصائيات اليومية لجميع المستخدمين")
        
    def get_top_users(self, limit: int = 10) -> List[Dict]:
        """الحصول على أفضل المستخدمين"""
        sorted_users = sorted(
            self.users.values(),
            key=lambda u: u.completed_files,
            reverse=True
        )
        
        return [
            {
                'user_id': user.user_id,
                'username': user.username,
                'completed_files': user.completed_files,
                'success_rate': (user.completed_files / max(user.total_files, 1)) * 100
            }
            for user in sorted_users[:limit]
        ]
        
    def get_system_stats(self) -> Dict:
        """إحصائيات النظام العامة"""
        total_users = len(self.users)
        active_today = len([
            user for user in self.users.values()
            if user.last_activity and user.last_activity.date() == datetime.now().date()
        ])
        
        total_requests = sum(user.total_files for user in self.users.values())
        total_completed = sum(user.completed_files for user in self.users.values())
        
        return {
            'total_users': total_users,
            'active_today': active_today,
            'total_requests': total_requests,
            'total_completed': total_completed,
            'success_rate': (total_completed / max(total_requests, 1)) * 100,
            'premium_users': len([u for u in self.users.values() if u.level == "مميز"])
        }
        
    def _get_completed_today(self, user_id: int) -> int:
        """عدد الملفات المكتملة اليوم (يحتاج ربط مع نظام الطابور)"""
        # هذا سيتم تنفيذه عند ربط الأنظمة
        return 0
        
    def _get_processing_count(self, user_id: int) -> int:
        """عدد الملفات قيد المعالجة (يحتاج ربط مع نظام الطابور)"""
        # هذا سيتم تنفيذه عند ربط الأنظمة
        return 0
        
    def _format_duration(self, seconds: float) -> str:
        """تنسيق المدة الزمنية"""
        if seconds < 60:
            return f"{seconds:.1f}s"
        elif seconds < 3600:
            minutes = seconds / 60
            return f"{minutes:.1f}m"
        else:
            hours = seconds / 3600
            return f"{hours:.1f}h"
            
    def export_users_data(self) -> Dict:
        """تصدير بيانات المستخدمين للنسخ الاحتياطي"""
        return {
            'users': [asdict(user) for user in self.users.values()],
            'admins': list(self.admins),
            'export_date': datetime.now().isoformat()
        }
        
    def import_users_data(self, data: Dict):
        """استيراد بيانات المستخدمين من النسخ الاحتياطي"""
        try:
            for user_data in data.get('users', []):
                user = User(**user_data)
                self.users[user.user_id] = user
                
            self.admins = set(data.get('admins', []))
            self.save_users()
            logger.info(f"تم استيراد {len(data.get('users', []))} مستخدم")
        except Exception as e:
            logger.error(f"خطأ في استيراد بيانات المستخدمين: {e}")
