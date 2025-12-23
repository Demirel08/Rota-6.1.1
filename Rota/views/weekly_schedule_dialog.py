"""
EFES ROTA X - Haftalık Üretim Programı
Hem Günlük Liste hem de Makine Bazlı Ağaç Görünümü içerir.
"""

import sys
from datetime import datetime, timedelta

try:
    from utils.timezone_helper import now_turkey, get_current_date_turkey
except ImportError:
    from datetime import datetime as _dt
    now_turkey = lambda: _dt.now()
    get_current_date_turkey = lambda: _dt.now().date()

from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, 
    QPushButton, QTabWidget, QWidget, QFileDialog, 
    QMessageBox, QFrame, QTableWidget, QTableWidgetItem, 
    QHeaderView, QAbstractItemView, QTreeWidget, QTreeWidgetItem
)
from PySide6.QtCore import Qt
from PySide6.QtGui import QColor, QFont, QIcon

try:
    from ui.theme import Theme
    from core.smart_planner import planner
    from core.pdf_engine import PDFEngine
    from core.db_manager import db
except ImportError:
    pass

# --- RENKLER ---
class Colors:
    BG = "#FFFFFF"
    HEADER_BG = "#F8F9FA"
    BORDER = "#E0E0E0"
    TEXT_PRIMARY = "#2D3748"
    TEXT_SECONDARY = "#718096"
    ACCENT = "#3182CE"
    SUCCESS = "#48BB78"
    WARNING = "#ED8936"

class WeeklyScheduleDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Haftalık Üretim Planı")
        self.resize(1100, 750)
        self.setStyleSheet(f"""
            QDialog {{ background-color: {Colors.BG}; }}
            QLabel {{ color: {Colors.TEXT_PRIMARY}; }}
            QTableWidget {{ 
                border: 1px solid {Colors.BORDER}; 
                gridline-color: {Colors.BORDER};
                background-color: white;
            }}
            QHeaderView::section {{
                background-color: {Colors.HEADER_BG};
                padding: 8px;
                border: none;
                font-weight: bold;
                color: {Colors.TEXT_SECONDARY};
            }}
            QTabWidget::pane {{ border: 1px solid {Colors.BORDER}; }}
            QTabBar::tab {{
                background: {Colors.HEADER_BG};
                padding: 10px 20px;
                border-top-left-radius: 4px;
                border-top-right-radius: 4px;
            }}
            QTabBar::tab:selected {{
                background: {Colors.ACCENT};
                color: white;
            }}
        """)
        
        # Veriyi Çek
        try:
            self.schedule_data = planner.get_weekly_plan()
        except:
            self.schedule_data = {}

        self.init_ui()
        self.load_data()

    def init_ui(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(15)
        layout.setContentsMargins(20, 20, 20, 20)

        # 1. Başlık Alanı
        header_layout = QHBoxLayout()
        title = QLabel("📅 Haftalık Üretim Programı")
        title.setFont(QFont("Segoe UI", 16, QFont.Bold))
        title.setStyleSheet(f"color: {Colors.ACCENT};")
        
        btn_refresh = QPushButton("Yenile")
        btn_refresh.setFixedWidth(100)
        btn_refresh.clicked.connect(self.refresh_data)
        
        header_layout.addWidget(title)
        header_layout.addStretch()
        header_layout.addWidget(btn_refresh)
        layout.addLayout(header_layout)

        # 2. SEKMELER (TABS) - İşte burası yeni kısım
        self.tabs = QTabWidget()
        layout.addWidget(self.tabs)

        # --- TAB 1: GÜNLÜK AKIŞ (Eski Liste) ---
        self.tab_daily = QWidget()
        daily_layout = QVBoxLayout(self.tab_daily)
        
        self.table_daily = QTableWidget()
        self.table_daily.setColumnCount(5)
        self.table_daily.setHorizontalHeaderLabels(["Tarih", "Sipariş No", "Müşteri", "Ürün", "M²"])
        self.table_daily.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.table_daily.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.table_daily.setAlternatingRowColors(True)
        
        daily_layout.addWidget(self.table_daily)
        self.tabs.addTab(self.tab_daily, "📆 Günlük Akış")

        # --- TAB 2: MAKİNE BAZLI (Yeni İstediğin) ---
        self.tab_machine = QWidget()
        machine_layout = QVBoxLayout(self.tab_machine)
        
        self.tree_machine = QTreeWidget()
        self.tree_machine.setColumnCount(4)
        self.tree_machine.setHeaderLabels(["Makine / Sipariş", "Tarih", "Müşteri", "M²"])
        self.tree_machine.setColumnWidth(0, 350) # İlk sütun geniş olsun
        self.tree_machine.setColumnWidth(1, 120)
        self.tree_machine.setAlternatingRowColors(True)
        
        machine_layout.addWidget(self.tree_machine)
        self.tabs.addTab(self.tab_machine, "🏭 Makine Doluluğu")

        # 3. Alt Butonlar
        btn_layout = QHBoxLayout()
        btn_pdf = QPushButton("📄 PDF Olarak Kaydet")
        btn_pdf.setFixedWidth(180)
        btn_pdf.setStyleSheet(f"background-color: {Colors.ACCENT}; color: white; padding: 8px; border-radius: 4px;")
        btn_pdf.clicked.connect(self.export_to_pdf)
        
        btn_close = QPushButton("Kapat")
        btn_close.setFixedWidth(100)
        btn_close.clicked.connect(self.accept)
        
        btn_layout.addStretch()
        btn_layout.addWidget(btn_pdf)
        btn_layout.addWidget(btn_close)
        layout.addLayout(btn_layout)

    def load_data(self):
        """Her iki görünümü de doldur"""
        self._load_daily_table()
        self._load_machine_tree()

    def _load_daily_table(self):
        """Tabloyu doldur"""
        self.table_daily.setRowCount(0)
        if not self.schedule_data: return

        sorted_dates = sorted(self.schedule_data.keys())
        row_count = 0
        
        for date_str in sorted_dates:
            jobs = self.schedule_data[date_str]
            if not jobs: continue
            
            for job in jobs:
                self.table_daily.insertRow(row_count)
                
                # Tarih
                item_date = QTableWidgetItem(date_str)
                item_date.setTextAlignment(Qt.AlignCenter)
                self.table_daily.setItem(row_count, 0, item_date)
                
                # Kod
                item_code = QTableWidgetItem(job.get('code', '-'))
                item_code.setTextAlignment(Qt.AlignCenter)
                self.table_daily.setItem(row_count, 1, item_code)
                
                # Müşteri
                item_cust = QTableWidgetItem(job.get('customer', '-'))
                self.table_daily.setItem(row_count, 2, item_cust)
                
                # Ürün
                item_prod = QTableWidgetItem(job.get('product', '-'))
                self.table_daily.setItem(row_count, 3, item_prod)
                
                # M2
                m2 = job.get('m2', 0)
                item_m2 = QTableWidgetItem(f"{m2:.1f}")
                item_m2.setTextAlignment(Qt.AlignCenter)
                self.table_daily.setItem(row_count, 4, item_m2)
                
                row_count += 1

    def _load_machine_tree(self):
        """Ağaç görünümünü (Makine - Siparişler) doldur"""
        self.tree_machine.clear()
        if not self.schedule_data: return

        # 1. Veriyi makinaya göre grupla
        machine_groups = {}
        
        for date_str, jobs in self.schedule_data.items():
            for job in jobs:
                route_str = job.get('route', '')
                if not route_str: continue # Rotasız işleri atla veya 'Diğer' yap
                
                stations = [s.strip() for s in route_str.split(',')]
                for station in stations:
                    if not station: continue
                    if station not in machine_groups: machine_groups[station] = []
                    
                    machine_groups[station].append({
                        "date": date_str,
                        "code": job.get('code', '-'),
                        "customer": job.get('customer', '-'),
                        "m2": job.get('m2', 0)
                    })

        # 2. Ağaca ekle
        for station_name in sorted(machine_groups.keys()):
            # Ana Dal: Makine
            total_m2 = sum(x['m2'] for x in machine_groups[station_name])
            item_count = len(machine_groups[station_name])
            
            parent = QTreeWidgetItem(self.tree_machine)
            parent.setText(0, f"{station_name} ({item_count} İş)")
            parent.setText(3, f"Top: {total_m2:.1f}")
            parent.setFont(0, QFont("Segoe UI", 10, QFont.Bold))
            parent.setBackground(0, QColor(Colors.HEADER_BG))
            parent.setExpanded(True) # Açık gelsin

            # Alt Dallar: Siparişler (Tarihe göre sıralı)
            jobs_sorted = sorted(machine_groups[station_name], key=lambda x: x['date'])
            for job in jobs_sorted:
                child = QTreeWidgetItem(parent)
                child.setText(0, job['code'])
                child.setText(1, job['date'])
                child.setText(2, job['customer'])
                child.setText(3, f"{job['m2']:.1f}")

    def refresh_data(self):
        try:
            self.schedule_data = planner.get_weekly_plan()
            self.load_data()
            QMessageBox.information(self, "Bilgi", "Veriler güncellendi.")
        except Exception as e:
            QMessageBox.warning(self, "Hata", f"Yenileme hatası: {str(e)}")

    def export_to_pdf(self):
        """PDF Çıktısı - Aktif sekmeye göre"""
        default_name = f"Uretim_Plani_{now_turkey().strftime('%Y%m%d')}.pdf"
        filename, _ = QFileDialog.getSaveFileName(self, "Listeyi Kaydet", default_name, "PDF Files (*.pdf)")
        if not filename: return

        engine = PDFEngine(filename)

        # Hangi sekme aktif?
        current_tab_index = self.tabs.currentIndex()

        if current_tab_index == 0:
            # Günlük Akış sekmesi - Tarih bazlı PDF
            success, msg = engine.generate_weekly_schedule_pdf(self.schedule_data)
        else:
            # Makine Doluluğu sekmesi - Makine bazlı PDF
            success, msg = engine.generate_machine_schedule_pdf(self.schedule_data)

        if success:
            QMessageBox.information(self, "Başarılı", f"PDF kaydedildi:\n{filename}")
        else:
            QMessageBox.critical(self, "Hata", f"PDF oluşturulamadı:\n{msg}")