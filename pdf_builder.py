
from reportlab.pdfgen import canvas
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.lib.pagesizes import A4
from bidi.algorithm import get_display
import arabic_reshaper
import os

def create_translated_pdf(text, output_path):
    # محاولة تسجيل خط عربي من النظام
    try:
        # خطوط عربية شائعة في Linux/Unix
        font_paths = [
            '/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf',
            '/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf',
            '/System/Library/Fonts/Arial.ttf',  # macOS
            'C:/Windows/Fonts/arial.ttf'  # Windows
        ]
        
        font_registered = False
        for font_path in font_paths:
            if os.path.exists(font_path):
                pdfmetrics.registerFont(TTFont('Arabic', font_path))
                font_registered = True
                break
        
        if not font_registered:
            # استخدام الخط الافتراضي إذا لم نجد خط مناسب
            raise Exception("No Arabic font found")
            
    except:
        # في حالة عدم وجود خط مناسب، استخدم الخط الافتراضي
        font_name = "Helvetica"
    else:
        font_name = "Arabic"

    # إنشاء ملف PDF
    c = canvas.Canvas(output_path, pagesize=A4)
    c.setFont(font_name, 14)

    # تقسيم النص إلى أسطر
    lines = text.split('\n')
    y_position = 800  # نقطة البداية من الأعلى

    for line in lines:
        if line.strip():
            try:
                # إعادة تشكيل النص العربي وتطبيق الاتجاه الصحيح
                reshaped_text = arabic_reshaper.reshape(line.strip())
                bidi_text = get_display(reshaped_text)
                
                # كتابة النص من اليمين إلى اليسار
                c.drawRightString(550, y_position, bidi_text)
            except:
                # في حالة فشل التشكيل، اكتب النص كما هو
                c.drawString(50, y_position, line.strip())
            
        y_position -= 20  # المسافة بين الأسطر
        
        # إذا وصلنا لنهاية الصفحة، ابدأ صفحة جديدة
        if y_position < 50:
            c.showPage()
            c.setFont(font_name, 14)
            y_position = 800

    c.save()
