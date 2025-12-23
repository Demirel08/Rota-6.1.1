from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
import os

try:
    from utils.timezone_helper import now_turkey
except ImportError:
    from datetime import datetime as _dt
    now_turkey = lambda: _dt.now()

class PDFEngine:
    """
    EFES ROTA - Raporlama Motoru
    (Makine Bazlı Görünüm - Haftalık Plan)
    """

    def __init__(self, filename="Rapor.pdf"):
        self.filename = filename
        self.styles = getSampleStyleSheet()
        self.register_fonts()
        self.create_custom_styles()

    def register_fonts(self):
        """Türkçe karakter destekli Arial fontunu yükle"""
        try:
            # Normal Arial
            font_path = "C:\\Windows\\Fonts\\arial.ttf"
            if os.path.exists(font_path):
                pdfmetrics.registerFont(TTFont('Arial', font_path))
            else:
                pdfmetrics.registerFont(TTFont('Arial', 'Helvetica')) # Fallback

            # Bold Arial (Başlıklar için)
            font_path_bold = "C:\\Windows\\Fonts\\arialbd.ttf"
            if os.path.exists(font_path_bold):
                pdfmetrics.registerFont(TTFont('Arial-Bold', font_path_bold))
            else:
                pdfmetrics.registerFont(TTFont('Arial-Bold', 'Helvetica-Bold')) # Fallback

        except Exception as e:
            print(f"Font yükleme hatası: {e}")

    def create_custom_styles(self):
        """Rapor için özel stiller"""
        self.style_normal = ParagraphStyle(
            'CustomNormal', 
            parent=self.styles['Normal'], 
            fontName='Arial', 
            fontSize=9
        )
        self.style_title = ParagraphStyle(
            'CustomTitle', 
            parent=self.styles['Heading1'], 
            fontName='Arial-Bold', 
            fontSize=16, 
            spaceAfter=20, 
            alignment=1, # Center
            textColor=colors.darkblue
        )
        self.style_machine_header = ParagraphStyle(
            'MachineHeader', 
            parent=self.styles['Heading2'], 
            fontName='Arial-Bold', 
            fontSize=11, 
            spaceBefore=15, 
            spaceAfter=5, 
            textColor=colors.black,
            backColor=colors.lightgrey, # Hafif gri arka plan
            borderPadding=5
        )

    def generate_weekly_schedule_pdf(self, schedule_data):
        """Haftalık planı Makine Bazlı PDF'e çevirir"""
        doc = SimpleDocTemplate(self.filename, pagesize=A4)
        elements = []
        
        # --- BAŞLIK ---
        tarih = now_turkey().strftime('%d.%m.%Y')
        elements.append(Paragraph(f"Haftalık Makine İş Yükü Raporu ({tarih})", self.style_title))
        
        # --- 1. VERİYİ GRUPLA (Makine -> Siparişler) ---
        machine_groups = {}
        
        # Veri yapısı: { "Date": [Jobs] } -> { "Machine": [Jobs with Date] }
        for date_str, jobs in schedule_data.items():
            for job in jobs:
                route = job.get('route', '')
                if not route: continue
                
                stations = [s.strip() for s in route.split(',')]
                for st in stations:
                    if not st: continue
                    if st not in machine_groups: machine_groups[st] = []
                    
                    machine_groups[st].append({
                        'date': date_str,
                        'code': job.get('code', '-'),
                        'customer': job.get('customer', '-'),
                        'm2': job.get('m2', 0)
                    })
        
        if not machine_groups:
            elements.append(Paragraph("Gösterilecek veri bulunamadı.", self.style_normal))
            try:
                doc.build(elements)
                return True, "Boş PDF oluşturuldu"
            except Exception as e: return False, str(e)

        # --- 2. MAKİNE MAKİNE YAZDIR ---
        for station in sorted(machine_groups.keys()):
            jobs = sorted(machine_groups[station], key=lambda x: x['date']) # Tarihe göre sırala
            total_m2 = sum(j['m2'] for j in jobs)
            count = len(jobs)
            
            # A) Makine Başlığı
            header_text = f"{station} &nbsp; (Toplam: {total_m2:.1f} m² &nbsp;-&nbsp; {count} İş)"
            elements.append(Paragraph(header_text, self.style_machine_header))
            
            # B) Tablo Verisi Hazırla
            data = [['Tarih', 'Sipariş No', 'Müşteri', 'M²']] # Header
            
            for job in jobs:
                # Müşteri ismi çok uzunsa kısalt (PDF taşmasın)
                cust = job['customer']
                if len(cust) > 30: cust = cust[:28] + "..."
                
                data.append([
                    job['date'],
                    job['code'],
                    cust,
                    f"{job['m2']:.1f}"
                ])
            
            # C) Tablo Stili
            # Sütun Genişlikleri: Tarih(70), Kod(90), Müşteri(260), M2(50) -> Toplam ~470
            t = Table(data, colWidths=[70, 90, 260, 50])
            
            t.setStyle(TableStyle([
                ('BACKGROUND', (0, 0), (-1, 0), colors.whitesmoke), # Header rengi
                ('TEXTCOLOR', (0, 0), (-1, 0), colors.black),
                ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
                ('ALIGN', (3, 0), (3, -1), 'RIGHT'), # M2 sağa yaslı
                ('FONTNAME', (0, 0), (-1, -1), 'Arial'),
                ('FONTNAME', (0, 0), (-1, 0), 'Arial-Bold'), # Header bold
                ('FONTSIZE', (0, 0), (-1, -1), 9),
                ('GRID', (0, 0), (-1, -1), 0.5, colors.grey), # Çizgiler
                ('BOTTOMPADDING', (0, 0), (-1, -1), 4),
                ('TOPPADDING', (0, 0), (-1, -1), 4),
            ]))
            
            elements.append(t)
            elements.append(Spacer(1, 15)) # Tablolar arası boşluk

        # --- 3. KAYDET ---
        try:
            doc.build(elements)
            return True, "PDF başarıyla oluşturuldu"
        except Exception as e:
            return False, f"PDF Hatası: {str(e)}"