
import os
import asyncio
import logging
from typing import Dict, List, Optional, Any
from groq import Groq
import google.generativeai as genai
from openai import AsyncOpenAI
import time
import re

logger = logging.getLogger(__name__)

class AdvancedTranslator:
    def __init__(self, api_manager):
        self.api_manager = api_manager
        self.setup_clients()
        
        # إعدادات الترجمة المتقدمة
        self.translation_settings = {
            'chunk_size': 1000,  # حجم القطعة النصية
            'context_overlap': 100,  # تداخل السياق
            'max_retries': 3,
            'timeout': 30
        }
        
        # قوالب الترجمة المتخصصة
        self.translation_prompts = {
            'technical': """
أنت مترجم متخصص في النصوص التقنية والعلمية.
مهمتك ترجمة النص التالي من الإنجليزية إلى العربية مع مراعاة:
1. الحفاظ على المصطلحات التقنية الدقيقة
2. ترجمة المعادلات والرموز بعناية
3. الحفاظ على هيكل الجمل العلمية
4. توحيد المصطلحات عبر النص

النص المراد ترجمته:
{text}

قدم الترجمة العربية الدقيقة فقط:
            """,
            
            'academic': """
أنت مترجم أكاديمي متخصص في النصوص العلمية والبحثية.
ترجم النص التالي مع مراعاة:
1. الأسلوب الأكاديمي الرصين
2. دقة المراجع والاقتباسات
3. المصطلحات البحثية المتخصصة
4. الحفاظ على المعنى العلمي الدقيق

النص:
{text}

الترجمة العربية:
            """,
            
            'general': """
ترجم النص التالي من الإنجليزية إلى العربية بطريقة طبيعية ومفهومة.
احرص على:
1. الوضوح والفهم
2. الأسلوب الطبيعي
3. الحفاظ على المعنى الأصلي
4. استخدام تعبيرات عربية مناسبة

النص:
{text}

الترجمة:
            """
        }
        
    def setup_clients(self):
        """إعداد عملاء الترجمة المختلفين - Groq كخدمة أساسية"""
        # إعداد Groq (الخدمة الأساسية)
        groq_key = self.api_manager.get_available_key('groq')
        if groq_key:
            self.groq_client = Groq(api_key=groq_key.key)
            logger.info("✅ Groq client initialized (Primary AI service)")
        else:
            self.groq_client = None
            logger.warning("⚠️ Groq API not available - primary service missing")
            
        # إعداد Gemini (خدمة احتياطية)
        gemini_key = self.api_manager.get_available_key('gemini')
        if gemini_key:
            genai.configure(api_key=gemini_key.key)
            self.gemini_model = genai.GenerativeModel('gemini-pro')
            logger.info("✅ Gemini client initialized (Fallback service)")
        else:
            self.gemini_model = None
            logger.info("ℹ️ Gemini API not configured (optional fallback)")
            
        # إعداد OpenAI (خدمة احتياطية)
        openai_key = self.api_manager.get_available_key('openai')
        if openai_key:
            self.openai_client = AsyncOpenAI(api_key=openai_key.key)
            logger.info("✅ OpenAI client initialized (Fallback service)")
        else:
            self.openai_client = None
            logger.info("ℹ️ OpenAI API not configured (optional fallback)")
            
    async def translate_advanced(self, text: str, user_id: int, 
                                target_lang: str = "ar", 
                                text_type: str = "general") -> str:
        """الترجمة المتقدمة مع معالجة ذكية"""
        
        # تحليل نوع النص تلقائياً
        detected_type = self.detect_text_type(text)
        if detected_type:
            text_type = detected_type
            
        # تقسيم النص إلى قطع مناسبة
        chunks = self.split_text_intelligently(text)
        
        translated_chunks = []
        
        for i, chunk in enumerate(chunks):
            logger.info(f"ترجمة القطعة {i+1}/{len(chunks)} للمستخدم {user_id}")
            
            # ترجمة كل قطعة مع الحفاظ على السياق
            context = self.get_context(chunks, i)
            translated_chunk = await self.translate_chunk(
                chunk, target_lang, text_type, context
            )
            
            if translated_chunk:
                translated_chunks.append(translated_chunk)
            else:
                logger.error(f"فشل في ترجمة القطعة {i+1}")
                translated_chunks.append(f"[خطأ في ترجمة هذا الجزء: {chunk[:100]}...]")
                
        # دمج القطع المترجمة
        final_translation = self.merge_translated_chunks(translated_chunks)
        
        # مراجعة وتحسين الترجمة
        final_translation = await self.review_translation(final_translation, text_type)
        
        return final_translation
        
    def detect_text_type(self, text: str) -> Optional[str]:
        """كشف نوع النص تلقائياً"""
        
        # مؤشرات النصوص التقنية
        technical_indicators = [
            r'\b(algorithm|function|variable|equation|formula)\b',
            r'\b(API|HTTP|JSON|XML|SQL)\b',
            r'\b(server|database|network|protocol)\b',
            r'[=+\-*/]|\b\d+\.\d+\b',  # معادلات ورقام
            r'\b(Fig\.|Table|Figure)\s+\d+',  # مراجع الأشكال
        ]
        
        # مؤشرات النصوص الأكاديمية
        academic_indicators = [
            r'\b(research|study|analysis|methodology)\b',
            r'\b(hypothesis|conclusion|abstract|bibliography)\b',
            r'\b(et al\.|ibid\.|op\. cit\.)\b',
            r'\[\d+\]|\(\d{4}\)',  # مراجع
            r'\b(p\.|pp\.|vol\.|no\.)\s*\d+',  # صفحات ومجلدات
        ]
        
        text_lower = text.lower()
        
        technical_score = sum(1 for pattern in technical_indicators 
                            if re.search(pattern, text_lower))
        academic_score = sum(1 for pattern in academic_indicators 
                           if re.search(pattern, text_lower))
                           
        if technical_score > academic_score and technical_score > 2:
            return 'technical'
        elif academic_score > 2:
            return 'academic'
        else:
            return 'general'
            
    def split_text_intelligently(self, text: str) -> List[str]:
        """تقسيم النص بذكاء مع الحفاظ على السياق"""
        chunks = []
        current_chunk = ""
        
        # تقسيم حسب الفقرات أولاً
        paragraphs = text.split('\n\n')
        
        for paragraph in paragraphs:
            # إذا كانت الفقرة طويلة، قسمها حسب الجمل
            if len(paragraph) > self.translation_settings['chunk_size']:
                sentences = re.split(r'[.!?]+', paragraph)
                
                for sentence in sentences:
                    sentence = sentence.strip()
                    if not sentence:
                        continue
                        
                    # إذا كانت الجملة طويلة جداً، قسمها بحذر
                    if len(sentence) > self.translation_settings['chunk_size']:
                        sub_chunks = self.split_long_sentence(sentence)
                        for sub_chunk in sub_chunks:
                            if len(current_chunk + sub_chunk) > self.translation_settings['chunk_size']:
                                if current_chunk:
                                    chunks.append(current_chunk.strip())
                                current_chunk = sub_chunk
                            else:
                                current_chunk += sub_chunk + " "
                    else:
                        if len(current_chunk + sentence) > self.translation_settings['chunk_size']:
                            if current_chunk:
                                chunks.append(current_chunk.strip())
                            current_chunk = sentence + ". "
                        else:
                            current_chunk += sentence + ". "
            else:
                if len(current_chunk + paragraph) > self.translation_settings['chunk_size']:
                    if current_chunk:
                        chunks.append(current_chunk.strip())
                    current_chunk = paragraph + "\n\n"
                else:
                    current_chunk += paragraph + "\n\n"
                    
        if current_chunk.strip():
            chunks.append(current_chunk.strip())
            
        return chunks
        
    def split_long_sentence(self, sentence: str) -> List[str]:
        """تقسيم الجملة الطويلة بحذر"""
        # تقسيم حسب الفواصل أولاً
        parts = re.split(r'[,;:]', sentence)
        
        chunks = []
        current = ""
        
        for part in parts:
            part = part.strip()
            if len(current + part) > self.translation_settings['chunk_size'] // 2:
                if current:
                    chunks.append(current.strip())
                current = part
            else:
                current += part + ", "
                
        if current.strip():
            chunks.append(current.strip())
            
        return chunks
        
    def get_context(self, chunks: List[str], current_index: int) -> str:
        """الحصول على السياق للقطعة الحالية"""
        context = ""
        
        # إضافة سياق من القطعة السابقة
        if current_index > 0:
            prev_chunk = chunks[current_index - 1]
            context += prev_chunk[-self.translation_settings['context_overlap']:] + "\n\n"
            
        return context
        
    async def translate_chunk(self, chunk: str, target_lang: str, 
                            text_type: str, context: str = "") -> Optional[str]:
        """ترجمة قطعة نص واحدة"""
        
        # اختيار القالب المناسب
        prompt_template = self.translation_prompts.get(text_type, 
                                                     self.translation_prompts['general'])
        
        # إضافة السياق إذا كان متوفراً
        full_text = context + chunk if context else chunk
        prompt = prompt_template.format(text=full_text)
        
        # محاولة الترجمة مع خدمات مختلفة
        for attempt in range(self.translation_settings['max_retries']):
            try:
                # جرب Gemini أولاً
                if self.gemini_model:
                    return await self.translate_with_gemini(prompt)
                    
                # ثم OpenAI
                elif self.openai_client:
                    return await self.translate_with_openai(prompt)
                    
                # ثم Groq
                elif self.groq_client:
                    return await self.translate_with_groq(prompt)
                    
            except Exception as e:
                logger.warning(f"محاولة {attempt + 1} فشلت: {e}")
                if attempt < self.translation_settings['max_retries'] - 1:
                    await asyncio.sleep(2 ** attempt)  # انتظار متزايد
                    
        return None
        
    async def translate_with_gemini(self, prompt: str) -> str:
        """الترجمة باستخدام Gemini"""
        try:
            response = await asyncio.wait_for(
                asyncio.to_thread(self.gemini_model.generate_content, prompt),
                timeout=self.translation_settings['timeout']
            )
            return response.text.strip()
        except Exception as e:
            logger.error(f"خطأ في Gemini: {e}")
            raise
            
    async def translate_with_openai(self, prompt: str) -> str:
        """الترجمة باستخدام OpenAI"""
        try:
            response = await self.openai_client.chat.completions.create(
                model="gpt-3.5-turbo",
                messages=[{"role": "user", "content": prompt}],
                max_tokens=2000,
                temperature=0.1
            )
            return response.choices[0].message.content.strip()
        except Exception as e:
            logger.error(f"خطأ في OpenAI: {e}")
            raise
            
    async def translate_with_groq(self, prompt: str) -> str:
        """الترجمة باستخدام Groq"""
        try:
            response = await asyncio.wait_for(
                asyncio.to_thread(
                    self.groq_client.chat.completions.create,
                    model="llama3-8b-8192",
                    messages=[{"role": "user", "content": prompt}],
                    max_tokens=2000,
                    temperature=0.1
                ),
                timeout=self.translation_settings['timeout']
            )
            return response.choices[0].message.content.strip()
        except Exception as e:
            logger.error(f"خطأ في Groq: {e}")
            raise
            
    def merge_translated_chunks(self, chunks: List[str]) -> str:
        """دمج القطع المترجمة بذكاء"""
        if not chunks:
            return ""
            
        merged = chunks[0]
        
        for i in range(1, len(chunks)):
            # إزالة التداخل المحتمل
            current_chunk = chunks[i]
            
            # البحث عن تداخل في نهاية النص السابق وبداية الحالي
            overlap = self.find_overlap(merged, current_chunk)
            
            if overlap:
                # إزالة التداخل من القطعة الحالية
                current_chunk = current_chunk[len(overlap):].strip()
                
            # إضافة فاصل مناسب
            if not merged.endswith(('\n', '.', '!', '?')):
                merged += " "
                
            merged += current_chunk
            
        return merged.strip()
        
    def find_overlap(self, text1: str, text2: str) -> str:
        """البحث عن التداخل بين نصين"""
        max_overlap = min(len(text1), len(text2), self.translation_settings['context_overlap'])
        
        for i in range(max_overlap, 0, -1):
            if text1[-i:] == text2[:i]:
                return text2[:i]
                
        return ""
        
    async def review_translation(self, translation: str, text_type: str) -> str:
        """مراجعة وتحسين الترجمة"""
        
        # قواعد تحسين أساسية
        translation = self.apply_basic_improvements(translation)
        
        # مراجعة متقدمة للنصوص التقنية
        if text_type == 'technical':
            translation = self.improve_technical_translation(translation)
        elif text_type == 'academic':
            translation = self.improve_academic_translation(translation)
            
        return translation
        
    def apply_basic_improvements(self, text: str) -> str:
        """تطبيق تحسينات أساسية على الترجمة"""
        
        # تصحيح المسافات
        text = re.sub(r'\s+', ' ', text)
        text = re.sub(r'\s*([.!?,:;])', r'\1', text)
        text = re.sub(r'([.!?])\s*', r'\1 ', text)
        
        # تصحيح علامات الترقيم العربية
        text = text.replace('،', '، ')
        text = text.replace('؛', '؛ ')
        text = text.replace(':', ': ')
        
        # إزالة المسافات الزائدة
        text = re.sub(r'\s+', ' ', text)
        text = text.strip()
        
        return text
        
    def improve_technical_translation(self, text: str) -> str:
        """تحسين الترجمة التقنية"""
        
        # قاموس المصطلحات التقنية الشائعة
        tech_terms = {
            'algorithm': 'خوارزمية',
            'database': 'قاعدة بيانات',
            'server': 'خادم',
            'client': 'عميل',
            'network': 'شبكة',
            'protocol': 'بروتوكول',
            'interface': 'واجهة',
            'framework': 'إطار عمل'
        }
        
        # تطبيق توحيد المصطلحات
        for en_term, ar_term in tech_terms.items():
            # البحث عن الترجمات المختلفة وتوحيدها
            pattern = r'\b' + re.escape(ar_term) + r'\b'
            if re.search(pattern, text):
                # توحيد المصطلح في كامل النص
                text = re.sub(pattern, ar_term, text, flags=re.IGNORECASE)
                
        return text
        
    def improve_academic_translation(self, text: str) -> str:
        """تحسين الترجمة الأكاديمية"""
        
        # قاموس المصطلحات الأكاديمية
        academic_terms = {
            'research': 'بحث',
            'study': 'دراسة',
            'analysis': 'تحليل',
            'methodology': 'منهجية',
            'hypothesis': 'فرضية',
            'conclusion': 'خلاصة',
            'abstract': 'ملخص',
            'bibliography': 'قائمة مراجع'
        }
        
        # تطبيق توحيد المصطلحات الأكاديمية
        for en_term, ar_term in academic_terms.items():
            pattern = r'\b' + re.escape(ar_term) + r'\b'
            if re.search(pattern, text):
                text = re.sub(pattern, ar_term, text, flags=re.IGNORECASE)
                
        return text
        
    def translate_text(self, text: str, target_lang: str = "ar") -> str:
        """ترجمة بسيطة للتوافق مع النظام القديم"""
        # هذه دالة للتوافق مع النظام القديم
        try:
            if self.groq_client:
                completion = self.groq_client.chat.completions.create(
                    model="llama3-8b-8192",
                    messages=[
                        {"role": "system", "content": f"ترجم النص التالي إلى {target_lang} بشكل احترافي."},
                        {"role": "user", "content": text}
                    ],
                    temperature=0.1,
                    max_tokens=4096,
                    stream=False
                )
                return completion.choices[0].message.content
        except Exception as e:
            logger.error(f"خطأ في الترجمة البسيطة: {e}")
            
        return "خطأ في الترجمة"

# للتوافق مع النظام القديم
class GroqTranslator:
    def __init__(self):
        api_key = os.getenv("GROQ_API_KEY")
        if not api_key:
            raise ValueError("⚠️ لا يوجد مفتاح Groq API في المتغيرات البيئية")
        self.client = Groq(api_key=api_key)

    def translate_text(self, text, target_lang="ar"):
        completion = self.client.chat.completions.create(
            model="llama3-8b-8192",
            messages=[
                {"role": "system", "content": f"ترجم النص التالي إلى {target_lang} بشكل احترافي."},
                {"role": "user", "content": text}
            ],
            temperature=1,
            max_tokens=4096,
            stream=False
        )
        return completion.choices[0].message.content
