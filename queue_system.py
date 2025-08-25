
import uuid
import asyncio
from datetime import datetime, timedelta
from collections import deque, defaultdict
from typing import Dict, List, Optional, Any
import logging

logger = logging.getLogger(__name__)

class QueueTask:
    def __init__(self, task_data: Dict[str, Any]):
        self.id = str(uuid.uuid4())
        self.user_id = task_data['user_id']
        self.file_name = task_data['file_name']
        self.file_size = task_data['file_size']
        self.file = task_data['file_bytes']  # <-- تم التغيير هنا
        self.created_at = datetime.now()
        self.priority = self.calculate_priority(task_data)
        self.estimated_time = self.estimate_processing_time(task_data)
        
    def calculate_priority(self, task_data: Dict) -> int:
        """حساب أولوية المهمة بناءً على عوامل مختلفة"""
        priority = 100  # أولوية أساسية
        
        # أولوية أقل للملفات الكبيرة
        file_size_mb = task_data['file_size'] / (1024 * 1024)
        if file_size_mb > 10:
            priority -= 30
        elif file_size_mb > 5:
            priority -= 15
            
        # أولوية أعلى للمستخدمين المميزين (يمكن إضافة هذا لاحقاً)
        # if user_is_premium:
        #     priority += 50
            
        return priority
        
    def estimate_processing_time(self, task_data: Dict) -> int:
        """تقدير وقت المعالجة بالثواني"""
        base_time = 30  # 30 ثانية أساسية
        file_size_mb = task_data['file_size'] / (1024 * 1024)
        
        # إضافة وقت حسب حجم الملف
        additional_time = file_size_mb * 10  # 10 ثواني لكل ميجابايت
        
        return int(base_time + additional_time)

class QueueSystem:
    def __init__(self):
        self.main_queue = deque()
        self.priority_queue = deque()
        self.processing_tasks = {}
        self.user_limits = defaultdict(lambda: {'daily': 0, 'concurrent': 0})
        self.completed_tasks = deque(maxlen=1000)  # حفظ آخر 1000 مهمة مكتملة
        
        # إعدادات النظام
        self.max_concurrent_per_user = 3
        self.max_daily_per_user = 50
        self.max_concurrent_total = 10
        
    def add_task(self, task_data: Dict[str, Any]) -> str:
        """إضافة مهمة جديدة للطابور"""
        user_id = task_data['user_id']
        
        # فحص الحدود
        if not self._can_add_task(user_id):
            raise Exception("تم تجاوز حدود المستخدم")
            
        task = QueueTask(task_data)
        
        # إضافة للطابور المناسب حسب الأولوية
        if task.priority > 150:
            self.priority_queue.append(task)
        else:
            self.main_queue.append(task)
            
        # تحديث حدود المستخدم
        self.user_limits[user_id]['concurrent'] += 1
        self.user_limits[user_id]['daily'] += 1
        
        logger.info(f"تمت إضافة مهمة {task.id} للمستخدم {user_id}")
        return task.id
        
    def get_next_task(self) -> Optional[QueueTask]:
        """الحصول على المهمة التالية للمعالجة"""
        if len(self.processing_tasks) >= self.max_concurrent_total:
            return None
            
        # الأولوية للطابور ذو الأولوية العالية
        if self.priority_queue:
            task = self.priority_queue.popleft()
        elif self.main_queue:
            task = self.main_queue.popleft()
        else:
            return None
            
        self.processing_tasks[task.id] = task
        return task
        
    def complete_task(self, task_id: str, success: bool = True):
        """إنهاء مهمة"""
        if task_id in self.processing_tasks:
            task = self.processing_tasks.pop(task_id)
            task.completed_at = datetime.now()
            task.success = success
            
            # تحديث حدود المستخدم
            self.user_limits[task.user_id]['concurrent'] -= 1
            
            # إضافة للمهام المكتملة
            self.completed_tasks.append(task)
            
            logger.info(f"تم إنهاء المهمة {task_id} - النجاح: {success}")
            
    def get_queue_position(self, task_id: str) -> Optional[int]:
        """الحصول على موقع المهمة في الطابور"""
        # البحث في طابور الأولوية
        for i, task in enumerate(self.priority_queue):
            if task.id == task_id:
                return i + 1
                
        # البحث في الطابور الرئيسي
        for i, task in enumerate(self.main_queue):
            if task.id == task_id:
                return len(self.priority_queue) + i + 1
                
        # إذا كانت قيد المعالجة
        if task_id in self.processing_tasks:
            return 0  # قيد المعالجة الآن
            
        return None
        
    def get_user_queue_position(self, user_id: int) -> Optional[int]:
        """الحصول على موقع أقرب مهمة للمستخدم في الطابور"""
        positions = []
        
        # البحث في طابور الأولوية
        for i, task in enumerate(self.priority_queue):
            if task.user_id == user_id:
                positions.append(i + 1)
                
        # البحث في الطابور الرئيسي
        for i, task in enumerate(self.main_queue):
            if task.user_id == user_id:
                positions.append(len(self.priority_queue) + i + 1)
                
        return min(positions) if positions else None
        
    def estimate_wait_time(self, user_id: int) -> str:
        """تقدير وقت الانتظار للمستخدم"""
        position = self.get_user_queue_position(user_id)
        if position is None:
            return "لا توجد طلبات في الطابور"
            
        if position == 0:
            return "قيد المعالجة الآن"
            
        # تقدير الوقت بناءً على الموقع والمهام الحالية
        avg_processing_time = 45  # متوسط 45 ثانية لكل مهمة
        estimated_seconds = position * avg_processing_time
        
        if estimated_seconds < 60:
            return f"أقل من دقيقة"
        elif estimated_seconds < 3600:
            minutes = estimated_seconds // 60
            return f"حوالي {minutes} دقيقة"
        else:
            hours = estimated_seconds // 3600
            return f"حوالي {hours} ساعة"
            
    def estimate_wait_time_for_task(self, task_id: str) -> str:
        """تقدير وقت الانتظار لمهمة محددة"""
        position = self.get_queue_position(task_id)
        if position is None:
            return "غير موجود في الطابور"
            
        if position == 0:
            return "قيد المعالجة الآن"
            
        avg_processing_time = 45
        estimated_seconds = position * avg_processing_time
        
        if estimated_seconds < 60:
            return f"أقل من دقيقة"
        elif estimated_seconds < 3600:
            minutes = estimated_seconds // 60
            return f"حوالي {minutes} دقيقة"
        else:
            hours = estimated_seconds // 3600
            return f"حوالي {hours} ساعة"
            
    def get_queue_size(self) -> Dict[str, int]:
        """الحصول على أحجام الطوابير"""
        return {
            'priority': len(self.priority_queue),
            'main': len(self.main_queue),
            'processing': len(self.processing_tasks),
            'total': len(self.priority_queue) + len(self.main_queue) + len(self.processing_tasks)
        }
        
    def has_pending_tasks(self) -> bool:
        """فحص وجود مهام معلقة"""
        return bool(self.priority_queue or self.main_queue)
        
    def get_user_active_tasks(self, user_id: int) -> List[QueueTask]:
        """الحصول على المهام النشطة للمستخدم"""
        tasks = []
        
        # المهام في الطوابير
        for task in list(self.priority_queue) + list(self.main_queue):
            if task.user_id == user_id:
                tasks.append(task)
                
        # المهام قيد المعالجة
        for task in self.processing_tasks.values():
            if task.user_id == user_id:
                tasks.append(task)
                
        return tasks
        
    def _can_add_task(self, user_id: int) -> bool:
        """فحص إمكانية إضافة مهمة للمستخدم"""
        user_stats = self.user_limits[user_id]
        
        # فحص الحد اليومي
        if user_stats['daily'] >= self.max_daily_per_user:
            return False
            
        # فحص الحد المتزامن
        if user_stats['concurrent'] >= self.max_concurrent_per_user:
            return False
            
        return True
        
    def reset_daily_limits(self):
        """إعادة تعيين الحدود اليومية"""
        for user_id in self.user_limits:
            self.user_limits[user_id]['daily'] = 0
            
        logger.info("تم إعادة تعيين الحدود اليومية للطابور")
        
    def get_queue_stats(self) -> Dict:
        """إحصائيات الطابور"""
        completed_today = len([
            task for task in self.completed_tasks
            if task.completed_at and task.completed_at.date() == datetime.now().date()
        ])
        
        successful_today = len([
            task for task in self.completed_tasks
            if (task.completed_at and task.completed_at.date() == datetime.now().date() 
                and getattr(task, 'success', False))
        ])
        
        return {
            'queue_sizes': self.get_queue_size(),
            'completed_today': completed_today,
            'success_rate': (successful_today / max(completed_today, 1)) * 100,
            'active_users': len(self.user_limits),
            'avg_wait_time': self._calculate_avg_wait_time()
        }
        
    def _calculate_avg_wait_time(self) -> float:
        """حساب متوسط وقت الانتظار"""
        if not self.completed_tasks:
            return 0.0
            
        total_wait_time = 0
        count = 0
        
        for task in list(self.completed_tasks)[-100:]:  # آخر 100 مهمة
            if hasattr(task, 'completed_at') and task.completed_at:
                wait_time = (task.completed_at - task.created_at).total_seconds()
                total_wait_time += wait_time
                count += 1
                
        return total_wait_time / max(count, 1)
