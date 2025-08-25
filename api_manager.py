
import os
import time
import random
from typing import Dict, List, Optional
import logging
from dataclasses import dataclass
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)

@dataclass
class APIKey:
    key: str
    service: str
    usage_count: int = 0
    daily_limit: int = 1000
    last_used: Optional[datetime] = None
    is_active: bool = True
    error_count: int = 0

class APIManager:
    def __init__(self):
        self.keys = {
            'groq': [],     # Primary AI service
            'gemini': [],   # Fallback services
            'openai': [],
            'azure': []
        }
        self.load_keys()
        self.usage_stats = {}
        self.failed_keys = set()
        self.daily_usage = {}
        
    def load_keys(self):
        """تحميل المفاتيح من متغيرات البيئة"""
        # مفاتيح Groq (الخدمة الأساسية)
        groq_keys = os.getenv("GROQ_KEYS", "").split(",")
        for key in groq_keys:
            if key.strip():
                self.keys['groq'].append(APIKey(
                    key=key.strip(),
                    service='groq',
                    daily_limit=2000  # Groq has higher limits
                ))
        
        # مفاتيح Gemini (احتياطية)
        gemini_keys = os.getenv("GEMINI_KEYS", "").split(",")
        for key in gemini_keys:
            if key.strip():
                self.keys['gemini'].append(APIKey(
                    key=key.strip(),
                    service='gemini',
                    daily_limit=1000
                ))
        
        # مفاتيح OpenAI
        openai_keys = os.getenv("OPENAI_KEYS", "").split(",")
        for key in openai_keys:
            if key.strip():
                self.keys['openai'].append(APIKey(
                    key=key.strip(),
                    service='openai',
                    daily_limit=500
                ))
                
        # مفاتيح Azure (اختيارية - غير مثبتة حالياً)
        azure_keys = os.getenv("AZURE_KEYS", "").split(",")
        for key in azure_keys:
            if key.strip():
                self.keys['azure'].append(APIKey(
                    key=key.strip(),
                    service='azure',
                    daily_limit=2000
                ))
                
        logger.info(f"تم تحميل {sum(len(keys) for keys in self.keys.values())} مفتاح API")

    def get_available_key(self, service: str) -> Optional[APIKey]:
        """الحصول على مفتاح متاح للخدمة المطلوبة"""
        available_keys = [
            key for key in self.keys.get(service, [])
            if key.is_active and key.usage_count < key.daily_limit
            and key.key not in self.failed_keys
        ]
        
        if not available_keys:
            logger.warning(f"لا توجد مفاتيح متاحة للخدمة: {service}")
            return None
            
        # اختيار مفتاح عشوائي من المتاحة
        return random.choice(available_keys)

    def use_key(self, api_key: APIKey, success: bool = True):
        """تسجيل استخدام مفتاح"""
        api_key.usage_count += 1
        api_key.last_used = datetime.now()
        
        if not success:
            api_key.error_count += 1
            if api_key.error_count >= 5:  # تعطيل المفتاح بعد 5 أخطاء
                api_key.is_active = False
                logger.warning(f"تم تعطيل المفتاح {api_key.key[:10]}... بسبب كثرة الأخطاء")

    def rotate_service(self, current_service: str) -> str:
        """تبديل الخدمة عند عدم توفر مفاتيح"""
        # Always try Groq first (primary service)
        if current_service != 'groq' and self.get_available_key('groq'):
            logger.info(f"تم التبديل إلى Groq (الخدمة الأساسية)")
            return 'groq'
        
        # Fallback services priority
        services = ['gemini', 'openai', 'azure']
        try:
            current_index = services.index(current_service) if current_service in services else -1
            next_service = services[(current_index + 1) % len(services)]
            
            if self.get_available_key(next_service):
                logger.info(f"تم التبديل من {current_service} إلى {next_service}")
                return next_service
        except ValueError:
            pass
            
        return current_service

    def reset_daily_limits(self):
        """إعادة تعيين الحدود اليومية"""
        for service_keys in self.keys.values():
            for key in service_keys:
                key.usage_count = 0
                key.error_count = 0
                key.is_active = True
        
        self.failed_keys.clear()
        logger.info("تم إعادة تعيين جميع الحدود اليومية")

    def get_usage_report(self) -> Dict:
        """تقرير استخدام المفاتيح"""
        report = {}
        
        for service, keys in self.keys.items():
            service_stats = {
                'total_keys': len(keys),
                'active_keys': len([k for k in keys if k.is_active]),
                'total_usage': sum(k.usage_count for k in keys),
                'average_usage': sum(k.usage_count for k in keys) / max(len(keys), 1)
            }
            report[service] = service_stats
            
        return report

    def get_status_summary(self) -> str:
        """ملخص حالة النظام"""
        total_keys = sum(len(keys) for keys in self.keys.values())
        active_keys = sum(
            len([k for k in keys if k.is_active]) 
            for keys in self.keys.values()
        )
        
        if active_keys == 0:
            return "❌ غير متاح"
        elif active_keys < total_keys * 0.5:
            return "⚠️ محدود"
        else:
            return "✅ متاح"

    def health_check(self) -> bool:
        """فحص صحة النظام"""
        for service in self.keys:
            if self.get_available_key(service):
                return True
        return False
