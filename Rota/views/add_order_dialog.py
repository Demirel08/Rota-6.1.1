"""
EFES ROTA X - Yeni Siparis Ekleme Dialogu
Excel temali, kompakt tasarim
Tahmini teslimat suresi hesaplama (istasyon kapasitelerine gore)
"""

from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel,
    QLineEdit, QPushButton, QComboBox, QDateEdit,
    QFrame, QMessageBox, QSpinBox, QDoubleSpinBox,
    QGridLayout, QSizePolicy, QCheckBox, QScrollArea,
    QWidget, QGroupBox, QTextEdit, QProgressDialog
)
from PySide6.QtCore import Qt, QDate, QThread, Signal
from PySide6.QtGui import QFont, QCursor
from datetime import datetime, timedelta

try:
    from core.db_manager import db
    from core.smart_planner import planner
    from core.factory_config import factory_config
except ImportError:
    db = None
    planner = None
    factory_config = None


# =============================================================================
# TEMA
# =============================================================================
class Colors:
    BG = "#FFFFFF"
    HEADER_BG = "#F3F3F3"
    BORDER = "#D4D4D4"
    GRID = "#E0E0E0"
    TEXT = "#1A1A1A"
    TEXT_SECONDARY = "#666666"
    TEXT_MUTED = "#999999"
    ACCENT = "#217346"
    
    CRITICAL = "#C00000"
    WARNING = "#C65911"
    SUCCESS = "#107C41"
    INFO = "#0066CC"


# =============================================================================
# FABRIKA KAPASITELERI
# =============================================================================
class FactoryCapacity:
    """Istasyon kapasiteleri ve hesaplamalar - Veritabanindan ceker"""
    
    # Varsayilan kapasiteler (DB'de yoksa kullanilir)
    DEFAULT_CAPACITIES = {
        "INTERMAC": 800, "LIVA KESIM": 800, "LAMINE KESIM": 600,
        "CNC RODAJ": 100, "DOUBLEDGER": 400, "ZIMPARA": 300,
        "TESIR A1": 400, "TESIR B1": 400, "TESIR B1-1": 400, "TESIR B1-2": 400,
        "DELIK": 200, "OYGU": 200,
        "TEMPER A1": 550, "TEMPER B1": 750, "TEMPER BOMBE": 300,
        "LAMINE A1": 250, "ISICAM B1": 500,
        "KUMLAMA": 300, "SEVKIYAT": 5000
    }
    
    _cached_capacities = None
    _cached_station_order = None
    
    @classmethod
    def get_capacities(cls):
        """Veritabanindan kapasiteleri cek, cache'le"""
        if cls._cached_capacities is not None:
            return cls._cached_capacities
        
        if db:
            try:
                cls._cached_capacities = db.get_all_capacities()
                if cls._cached_capacities:
                    return cls._cached_capacities
            except:
                pass
        
        cls._cached_capacities = cls.DEFAULT_CAPACITIES.copy()
        return cls._cached_capacities
    
    @classmethod
    def refresh_cache(cls):
        """Cache'i temizle (kapasite degistiginde cagrilmali)"""
        cls._cached_capacities = None
        cls._cached_station_order = None

    @classmethod
    def get_station_order(cls):
        """Factory config'den istasyon sırasını al"""
        if cls._cached_station_order is not None:
            return cls._cached_station_order

        if factory_config:
            try:
                cls._cached_station_order = factory_config.get_station_order()
                return cls._cached_station_order
            except:
                pass

        # Fallback - factory_config yoksa varsayılan
        cls._cached_station_order = [
            "INTERMAC", "LIVA KESIM", "LAMINE KESIM",
            "CNC RODAJ", "DOUBLEDGER", "ZIMPARA",
            "TESIR A1", "TESIR B1", "TESIR B1-1", "TESIR B1-2", "DELIK", "OYGU",
            "TEMPER A1", "TEMPER B1", "TEMPER BOMBE",
            "LAMINE A1", "ISICAM B1", "KUMLAMA",
            "SEVKIYAT"
        ]
        return cls._cached_station_order

    @classmethod
    def get_capacity(cls, station):
        """Tek istasyon kapasitesini getir"""
        caps = cls.get_capacities()
        return caps.get(station, cls.DEFAULT_CAPACITIES.get(station, 500))
    
    @classmethod
    def estimate_days(cls, route_str, total_m2):
        """Rota ve m2'ye gore tahmini gun hesapla"""
        if not route_str or total_m2 <= 0:
            return 1
        
        stations = [s.strip() for s in route_str.split(',') if s.strip()]
        total_days = 0
        
        for station in stations:
            cap = cls.get_capacity(station)
            if cap > 0:
                # Her istasyon icin: islem suresi + kuyruk tahmini
                process_days = total_m2 / cap
                queue_days = cls._get_queue_days(station)
                total_days += process_days + queue_days
        
        return max(1, int(total_days) + 1)  # Minimum 1 gun, yuvarla
    
    @classmethod
    def _get_queue_days(cls, station):
        """Istasyon kuyruk suresi tahmini"""
        if not db:
            return 0.5  # Varsayilan yarim gun
        
        try:
            # Bekleyen is miktarini kontrol et
            with db.get_connection() as conn:
                result = conn.execute("""
                    SELECT SUM(declared_total_m2) as total_m2
                    FROM orders
                    WHERE status IN ('Beklemede', 'Uretimde')
                    AND route LIKE ?
                """, (f"%{station}%",)).fetchone()
                
                pending_m2 = result['total_m2'] or 0
                cap = cls.get_capacity(station)
                
                if cap > 0:
                    return min(pending_m2 / cap, 5)  # Max 5 gun kuyruk
                return 0.5
        except:
            return 0.5
    
    @classmethod
    def fix_route_order(cls, route_str):
        """Rotayi fabrika sirasina gore duzelt"""
        if not route_str:
            return ""

        stations = [s.strip() for s in route_str.split(',') if s.strip()]
        station_order = cls.get_station_order()

        def get_order(station):
            try:
                return station_order.index(station)
            except ValueError:
                return 999

        sorted_stations = sorted(stations, key=get_order)
        return ",".join(sorted_stations)


# =============================================================================
# ASYNC WORKER THREAD
# =============================================================================
class OrderSaveWorker(QThread):
    """Siparis kaydetme islemi icin arka plan thread'i"""
    finished = Signal(bool, str)  # (success, message)

    def __init__(self, order_data):
        super().__init__()
        self.order_data = order_data

    def run(self):
        """Arka planda siparis kaydet"""
        try:
            if db and db.add_new_order(self.order_data):
                self.finished.emit(True, f"Siparis '{self.order_data['code']}' basariyla kaydedildi.")
            else:
                self.finished.emit(False, "Siparis kaydedilemedi!")
        except Exception as e:
            self.finished.emit(False, f"Kayit hatasi: {str(e)}")


# =============================================================================
# SCROLL ENGELLEYICI SPINBOX
# =============================================================================
class QuietSpinBox(QSpinBox):
    def wheelEvent(self, event):
        event.ignore()

class QuietDoubleSpinBox(QDoubleSpinBox):
    def wheelEvent(self, event):
        event.ignore()


# =============================================================================
# ANA DIALOG
# =============================================================================
class AddOrderDialog(QDialog):
    """Yeni Siparis Ekleme Dialogu"""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Yeni Siparis")
        self.setMinimumSize(700, 650)
        self.resize(750, 700)
        self.setup_ui()

    def _load_glass_types(self):
        """Veritabanından cam türlerini yükle"""
        if db:
            try:
                glass_types = db.get_all_glass_types(active_only=True)
                for gt in glass_types:
                    self.combo_type.addItem(gt['type_name'])
            except:
                # Fallback: Varsayılan türler
                self.combo_type.addItems([
                    "Renksiz Düzcam", "Füme Cam", "Yeşil Cam"
                ])
        else:
            # Fallback
            self.combo_type.addItems([
                "Renksiz Düzcam", "Füme Cam", "Yeşil Cam"
            ])

    def _load_glass_thicknesses(self):
        """Veritabanından kalınlıkları yükle"""
        if db:
            try:
                thicknesses = db.get_all_glass_thicknesses(active_only=True)
                for t in thicknesses:
                    self.combo_thickness.addItem(str(t['thickness']))
            except:
                # Fallback: Varsayılan kalınlıklar
                self.combo_thickness.addItems(["4", "5", "6", "8", "10"])
        else:
            # Fallback
            self.combo_thickness.addItems(["4", "5", "6", "8", "10"])
    
    def setup_ui(self):
        self.setStyleSheet(f"""
            QDialog {{
                background-color: {Colors.BG};
            }}
            QLabel {{
                color: {Colors.TEXT};
                font-size: 11px;
            }}
            QLineEdit, QComboBox, QSpinBox, QDoubleSpinBox, QDateEdit {{
                background-color: {Colors.BG};
                border: 1px solid {Colors.BORDER};
                border-radius: 3px;
                padding: 6px 8px;
                font-size: 11px;
                min-height: 28px;
            }}
            QLineEdit:focus, QComboBox:focus, QSpinBox:focus, QDoubleSpinBox:focus {{
                border-color: {Colors.ACCENT};
            }}
            QCheckBox {{
                font-size: 11px;
                color: {Colors.TEXT};
                spacing: 6px;
            }}
            QCheckBox::indicator {{
                width: 16px;
                height: 16px;
                border: 1px solid {Colors.BORDER};
                border-radius: 3px;
                background-color: {Colors.BG};
            }}
            QCheckBox::indicator:checked {{
                background-color: {Colors.ACCENT};
                border-color: {Colors.ACCENT};
            }}
            QGroupBox {{
                font-size: 11px;
                font-weight: bold;
                color: {Colors.TEXT};
                border: 1px solid {Colors.BORDER};
                border-radius: 4px;
                margin-top: 12px;
                padding-top: 12px;
            }}
            QGroupBox::title {{
                subcontrol-origin: margin;
                left: 10px;
                padding: 0 5px;
            }}
        """)
        
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        
        # Header
        header = QFrame()
        header.setFixedHeight(40)
        header.setStyleSheet(f"""
            QFrame {{
                background-color: {Colors.HEADER_BG};
                border-bottom: 1px solid {Colors.BORDER};
            }}
        """)
        header_layout = QHBoxLayout(header)
        header_layout.setContentsMargins(16, 0, 16, 0)
        
        title = QLabel("Yeni Siparis Olustur")
        title.setStyleSheet(f"font-size: 13px; font-weight: bold; color: {Colors.TEXT};")
        header_layout.addWidget(title)
        header_layout.addStretch()
        
        layout.addWidget(header)
        
        # Scroll area
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.NoFrame)
        scroll.setStyleSheet(f"background-color: {Colors.BG};")
        
        content = QWidget()
        content_layout = QVBoxLayout(content)
        content_layout.setContentsMargins(20, 20, 20, 20)
        content_layout.setSpacing(16)
        
        # Form grid
        form = QGridLayout()
        form.setHorizontalSpacing(16)
        form.setVerticalSpacing(12)
        
        # Satir 1: Kod ve Musteri
        form.addWidget(QLabel("Siparis Kodu:"), 0, 0)
        form.addWidget(QLabel("Musteri:"), 0, 1)
        
        self.inp_code = QLineEdit()
        self.inp_code.setPlaceholderText("I2025-001")
        form.addWidget(self.inp_code, 1, 0)
        
        self.inp_customer = QLineEdit()
        self.inp_customer.setPlaceholderText("Firma adi")
        form.addWidget(self.inp_customer, 1, 1)

        # Satir 2: Proje Secimi
        form.addWidget(QLabel("Proje:"), 2, 0, 1, 2)

        project_row = QHBoxLayout()
        project_row.setSpacing(8)

        self.combo_project = QComboBox()
        self.combo_project.addItem("-- Projesiz --", None)
        self.load_projects()
        self.combo_project.currentIndexChanged.connect(self.on_project_changed)
        project_row.addWidget(self.combo_project, 3)

        self.btn_new_project = QPushButton("+ Yeni Proje")
        self.btn_new_project.setFixedSize(110, 32)
        self.btn_new_project.setCursor(Qt.PointingHandCursor)
        self.btn_new_project.setStyleSheet(f"""
            QPushButton {{
                background-color: {Colors.INFO};
                border: none;
                border-radius: 4px;
                color: white;
                font-size: 10px;
                font-weight: bold;
            }}
            QPushButton:hover {{
                background-color: #0052A3;
            }}
        """)
        self.btn_new_project.clicked.connect(self.create_quick_project)
        project_row.addWidget(self.btn_new_project)

        form.addLayout(project_row, 3, 0, 1, 2)

        # Satir 3: Cam tipi ve Kalinlik
        form.addWidget(QLabel("Cam Tipi:"), 4, 0)
        form.addWidget(QLabel("Kalinlik:"), 4, 1)

        self.combo_type = QComboBox()
        # DİNAMİK: Veritabanından cam türlerini yükle
        self._load_glass_types()
        form.addWidget(self.combo_type, 5, 0)

        self.combo_thickness = QComboBox()
        # DİNAMİK: Veritabanından kalınlıkları yükle
        self._load_glass_thicknesses()
        self.combo_thickness.setCurrentText("6")
        self.combo_thickness.setStyleSheet(f"""
            QComboBox {{
                background-color: {Colors.BG};
                border: 1px solid {Colors.BORDER};
                border-radius: 3px;
                padding: 6px 8px;
                font-size: 11px;
                min-height: 28px;
            }}
        """)
        form.addWidget(self.combo_thickness, 5, 1)

        # Satir 4: Adet ve m2
        form.addWidget(QLabel("Adet:"), 6, 0)
        form.addWidget(QLabel("Toplam m²:"), 6, 1)

        self.spin_qty = QuietSpinBox()
        self.spin_qty.setRange(1, 100000)
        self.spin_qty.setValue(1)
        form.addWidget(self.spin_qty, 7, 0)

        self.spin_m2 = QuietDoubleSpinBox()
        self.spin_m2.setRange(0.1, 100000)
        self.spin_m2.setValue(1)
        self.spin_m2.setSuffix(" m²")
        self.spin_m2.setStyleSheet(f"""
            QDoubleSpinBox {{
                background-color: {Colors.BG};
                border: 2px solid {Colors.ACCENT};
                font-weight: bold;
            }}
        """)
        form.addWidget(self.spin_m2, 7, 1)

        # Satir 5: Oncelik ve Teslim tarihi
        form.addWidget(QLabel("Oncelik:"), 8, 0)
        form.addWidget(QLabel("Teslim Tarihi:"), 8, 1)

        self.combo_priority = QComboBox()
        self.combo_priority.addItems(["Normal", "Acil", "Cok Acil", "Kritik"])
        form.addWidget(self.combo_priority, 9, 0)

        self.date_picker = QDateEdit()
        self.date_picker.setDate(QDate.currentDate().addDays(7))
        self.date_picker.setCalendarPopup(True)
        self.date_picker.setDisplayFormat("dd.MM.yyyy")
        form.addWidget(self.date_picker, 9, 1)

        content_layout.addLayout(form)

        # Not alani
        notes_label = QLabel("Siparis Notu:")
        notes_label.setStyleSheet(f"color: {Colors.TEXT}; font-size: 11px; font-weight: bold; margin-top: 8px;")
        content_layout.addWidget(notes_label)

        self.txt_notes = QTextEdit()
        self.txt_notes.setPlaceholderText("Bu siparise ait ozel notlar, uyarilar veya hatirlatmalar...")
        self.txt_notes.setMaximumHeight(80)
        self.txt_notes.setStyleSheet(f"""
            QTextEdit {{
                background-color: {Colors.BG};
                border: 1px solid {Colors.BORDER};
                border-radius: 3px;
                padding: 8px;
                font-size: 11px;
                color: {Colors.TEXT};
            }}
            QTextEdit:focus {{
                border-color: {Colors.ACCENT};
            }}
        """)
        content_layout.addWidget(self.txt_notes)
        
        # Rota secimi - Factory config'den dinamik
        route_group = QGroupBox("Uretim Rotasi")
        route_layout = QGridLayout(route_group)
        route_layout.setHorizontalSpacing(8)
        route_layout.setVerticalSpacing(6)

        # İstasyon checkboxlarını dinamik oluştur
        self.station_checkboxes = {}  # {station_name: QCheckBox}
        self._create_station_checkboxes(route_layout)

        content_layout.addWidget(route_group)
        
        # Tahmini teslimat hesaplama
        estimate_frame = QFrame()
        estimate_frame.setStyleSheet(f"""
            QFrame {{
                background-color: {Colors.HEADER_BG};
                border: 1px solid {Colors.BORDER};
                border-radius: 4px;
                padding: 12px;
            }}
        """)
        estimate_layout = QHBoxLayout(estimate_frame)
        estimate_layout.setContentsMargins(12, 8, 12, 8)
        estimate_layout.setSpacing(12)
        
        btn_estimate = QPushButton("Tahmini Teslimat Hesapla")
        btn_estimate.setFixedHeight(32)
        btn_estimate.setCursor(Qt.PointingHandCursor)
        btn_estimate.setStyleSheet(f"""
            QPushButton {{
                background-color: {Colors.INFO};
                border: none;
                border-radius: 4px;
                padding: 0 16px;
                color: white;
                font-size: 11px;
                font-weight: bold;
            }}
            QPushButton:hover {{
                background-color: #0052A3;
            }}
        """)
        btn_estimate.clicked.connect(self.calculate_estimate)
        estimate_layout.addWidget(btn_estimate)
        
        self.lbl_estimate = QLabel("")
        self.lbl_estimate.setStyleSheet(f"font-size: 11px; color: {Colors.TEXT};")
        estimate_layout.addWidget(self.lbl_estimate, 1)
        
        content_layout.addWidget(estimate_frame)
        
        content_layout.addStretch()
        
        scroll.setWidget(content)
        layout.addWidget(scroll, 1)
        
        # Alt butonlar
        footer = QFrame()
        footer.setFixedHeight(60)
        footer.setStyleSheet(f"""
            QFrame {{
                background-color: {Colors.HEADER_BG};
                border-top: 1px solid {Colors.BORDER};
            }}
        """)
        footer_layout = QHBoxLayout(footer)
        footer_layout.setContentsMargins(20, 12, 20, 12)
        footer_layout.setSpacing(12)
        
        btn_cancel = QPushButton("Iptal")
        btn_cancel.setFixedSize(100, 36)
        btn_cancel.setStyleSheet(f"""
            QPushButton {{
                background-color: {Colors.BG};
                border: 1px solid {Colors.BORDER};
                border-radius: 4px;
                color: {Colors.TEXT_SECONDARY};
                font-size: 11px;
            }}
            QPushButton:hover {{
                background-color: {Colors.HEADER_BG};
            }}
        """)
        btn_cancel.clicked.connect(self.reject)
        footer_layout.addWidget(btn_cancel)
        
        footer_layout.addStretch()
        
        btn_save = QPushButton("Siparisi Kaydet")
        btn_save.setFixedHeight(36)
        btn_save.setMinimumWidth(150)
        btn_save.setCursor(Qt.PointingHandCursor)
        btn_save.setStyleSheet(f"""
            QPushButton {{
                background-color: {Colors.ACCENT};
                border: none;
                border-radius: 4px;
                padding: 0 24px;
                color: white;
                font-size: 12px;
                font-weight: bold;
            }}
            QPushButton:hover {{
                background-color: #1D6640;
            }}
        """)
        btn_save.clicked.connect(self.save_order)
        footer_layout.addWidget(btn_save)
        
        layout.addWidget(footer)

    def load_projects(self):
        """Aktif projeleri yukle"""
        if not db:
            return

        try:
            projects = db.get_all_projects()
            # 'Aktif' veya 'Devam Ediyor' statusundaki projeleri al
            active_projects = [p for p in projects if p.get('status') in ['Aktif', 'Devam Ediyor']]

            # Combo'yu temizle ve projesiz seçeneğini ekle
            self.combo_project.clear()
            self.combo_project.addItem("-- Projesiz --", None)

            # Aktif projeleri ekle - proje bilgisini data olarak sakla
            for proj in active_projects:
                display_text = f"{proj['project_name']} - {proj.get('customer_name', 'Müşteri Yok')}"
                self.combo_project.addItem(display_text, proj)  # Tüm proje bilgisini sakla

        except Exception as e:
            print(f"Proje yükleme hatası: {e}")
            import traceback
            traceback.print_exc()

    def on_project_changed(self, index):
        """Proje değiştiğinde sipariş kodunu güncelle"""
        if index <= 0:  # "-- Projesiz --" seçiliyse
            return

        project = self.combo_project.currentData()
        if not project:
            return

        # Proje prefix'i varsa sipariş koduna ekle
        prefix = project.get('order_prefix', '').strip()
        if prefix:
            current_code = self.inp_code.text().strip()

            # Eğer kod boşsa veya sadece varsayılan placeholder ise
            if not current_code or current_code == "I2025-001":
                # Yeni kod oluştur: PREFIX-001
                self.inp_code.setText(f"{prefix}-001")
            else:
                # Mevcut kodu prefix ile başlat
                # Önce başka bir prefix varsa çıkar
                if '-' in current_code:
                    parts = current_code.split('-', 1)
                    number_part = parts[1]
                    self.inp_code.setText(f"{prefix}-{number_part}")
                else:
                    self.inp_code.setText(f"{prefix}-{current_code}")

    def create_quick_project(self):
        """Hizli proje olusturma dialogu"""
        from PySide6.QtWidgets import QDialog, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit, QPushButton, QDateEdit, QMessageBox

        dialog = QDialog(self)
        dialog.setWindowTitle("Yeni Proje Olustur")
        dialog.setMinimumWidth(420)
        dialog.setMinimumHeight(400)
        dialog.setStyleSheet(f"""
            QDialog {{
                background-color: {Colors.BG};
            }}
            QLabel {{
                color: {Colors.TEXT};
                font-size: 11px;
            }}
            QLineEdit, QDateEdit {{
                background-color: {Colors.BG};
                border: 1px solid {Colors.BORDER};
                border-radius: 3px;
                padding: 6px 8px;
                font-size: 11px;
                min-height: 28px;
            }}
        """)

        layout = QVBoxLayout(dialog)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(12)

        # Baslik
        title = QLabel("Hızlı Proje Oluştur")
        title.setStyleSheet(f"font-size: 13px; font-weight: bold; color: {Colors.TEXT};")
        layout.addWidget(title)

        # Proje adi
        layout.addWidget(QLabel("Proje Adı:"))
        inp_project_name = QLineEdit()
        inp_project_name.setPlaceholderText("Örn: Yalıkavak Villa")
        layout.addWidget(inp_project_name)

        # Musteri adi - mevcut musteriyi otomatik doldur
        layout.addWidget(QLabel("Müşteri:"))
        inp_customer_name = QLineEdit()
        inp_customer_name.setText(self.inp_customer.text().strip())
        inp_customer_name.setPlaceholderText("Müşteri adı")
        layout.addWidget(inp_customer_name)

        # Sipariş Ön Eki
        layout.addWidget(QLabel("Sipariş Ön Eki (Opsiyonel):"))
        inp_prefix = QLineEdit()
        inp_prefix.setPlaceholderText("Örn: YLK")
        inp_prefix.setMaxLength(10)
        layout.addWidget(inp_prefix)

        # Teslim tarihi
        layout.addWidget(QLabel("Hedef Teslim Tarihi:"))
        inp_date_picker = QDateEdit()
        inp_date_picker.setDate(QDate.currentDate().addDays(30))
        inp_date_picker.setCalendarPopup(True)
        inp_date_picker.setDisplayFormat("dd.MM.yyyy")
        layout.addWidget(inp_date_picker)

        # Butonlar
        btn_layout = QHBoxLayout()
        btn_layout.setSpacing(10)

        btn_cancel = QPushButton("İptal")
        btn_cancel.setFixedSize(100, 32)
        btn_cancel.setStyleSheet(f"""
            QPushButton {{
                background-color: {Colors.BG};
                border: 1px solid {Colors.BORDER};
                border-radius: 4px;
                color: {Colors.TEXT_SECONDARY};
                font-size: 11px;
            }}
            QPushButton:hover {{
                background-color: {Colors.HEADER_BG};
            }}
        """)
        btn_cancel.clicked.connect(dialog.reject)
        btn_layout.addWidget(btn_cancel)

        btn_layout.addStretch()

        btn_create = QPushButton("Oluştur")
        btn_create.setFixedSize(100, 32)
        btn_create.setStyleSheet(f"""
            QPushButton {{
                background-color: {Colors.ACCENT};
                border: none;
                border-radius: 4px;
                color: white;
                font-size: 11px;
                font-weight: bold;
            }}
            QPushButton:hover {{
                background-color: #1D6640;
            }}
        """)

        def save_project():
            project_name = inp_project_name.text().strip()
            customer_name = inp_customer_name.text().strip()
            prefix = inp_prefix.text().strip().upper()

            if not project_name:
                QMessageBox.warning(dialog, "Eksik Bilgi", "Proje adı zorunludur.")
                return

            if not customer_name:
                QMessageBox.warning(dialog, "Eksik Bilgi", "Müşteri adı zorunludur.")
                return

            if not db:
                QMessageBox.warning(dialog, "Hata", "Veritabanı bağlantısı yok!")
                return

            # Otomatik renk seçimi - mevcut projelere göre
            try:
                existing_projects = db.get_all_projects()
                used_colors = [p.get('color', '') for p in existing_projects if p.get('color')]
            except:
                used_colors = []

            # Renk paleti
            available_colors = [
                "#6B46C1", "#0066CC", "#107C41", "#C65911",
                "#C00000", "#E83E8C", "#17A2B8", "#FFC107",
                "#795548", "#9C27B0", "#FF5722", "#00BCD4"
            ]

            # En az kullanılan rengi seç
            color = available_colors[0]  # Varsayılan
            for c in available_colors:
                if c not in used_colors:
                    color = c
                    break

            try:
                project_data = {
                    'project_name': project_name,
                    'customer_name': customer_name,
                    'delivery_date': inp_date_picker.date().toString("yyyy-MM-dd"),
                    'status': 'Aktif',
                    'priority': 'Normal',
                    'notes': 'Sipariş girişi sırasında oluşturuldu',
                    'color': color,
                    'order_prefix': prefix
                }
                project_id = db.add_project(project_data)
                if project_id:
                    # Proje listesini yenile
                    self.load_projects()
                    # Yeni projeyi sec
                    for i in range(self.combo_project.count()):
                        proj_data = self.combo_project.itemData(i)
                        if proj_data and isinstance(proj_data, dict) and proj_data.get('id') == project_id:
                            self.combo_project.setCurrentIndex(i)
                            break
                    QMessageBox.information(dialog, "Başarılı", f"Proje '{project_name}' oluşturuldu.")
                    dialog.accept()
                else:
                    QMessageBox.critical(dialog, "Hata", "Proje oluşturulamadı!")
            except Exception as e:
                QMessageBox.critical(dialog, "Hata", f"Proje oluşturma hatası:\n{str(e)}")

        btn_create.clicked.connect(save_project)
        btn_layout.addWidget(btn_create)

        layout.addLayout(btn_layout)

        dialog.exec()

    def _create_station_checkboxes(self, layout):
        """Factory config'den istasyonları dinamik oluştur"""
        if not factory_config:
            # Fallback - factory_config yoksa
            return

        # İstasyonları gruplara göre al
        groups = factory_config.get_station_groups()

        col = 0
        for group_name, station_names in groups.items():
            # Sevkiyat hariç
            station_names = [s for s in station_names if s != "SEVKIYAT"]
            if not station_names:
                continue

            # Grup başlığı
            lbl_group = QLabel(group_name.upper())
            lbl_group.setStyleSheet(f"color: {Colors.TEXT_SECONDARY}; font-size: 10px;")
            layout.addWidget(lbl_group, 0, col)

            # Checkboxlar
            row = 1
            for station_name in station_names:
                chk = QCheckBox(station_name)
                layout.addWidget(chk, row, col)
                self.station_checkboxes[station_name] = chk
                row += 1

            col += 1
            # Maksimum kolon sınırı kaldırıldı - tüm istasyonlar gösterilsin

    def get_route_string(self):
        """Secili kutucuklardan rota stringi olustur"""
        stations = []

        # Dinamik checkboxlardan seçilenleri al
        for station_name, checkbox in self.station_checkboxes.items():
            if checkbox.isChecked():
                stations.append(station_name)

        # SEVKIYAT her zaman eklenir
        stations.append("SEVKIYAT")
        return ",".join(stations)
    
    def calculate_estimate(self):
        """
        Tahmini teslimat süresi hesapla.
        DÜZELTME: Artık basit matematik yerine SmartPlanner motorunu kullanır.
        Kalınlık katsayılarını ve mevcut fabrika doluluğunu hesaba katar.
        """
        total_m2 = self.spin_m2.value()
        if total_m2 <= 0:
            self.lbl_estimate.setText("Lütfen m² girin")
            self.lbl_estimate.setStyleSheet(f"color: {Colors.WARNING}; font-size: 11px;")
            return
        
        route_str = self.get_route_string()
        if not route_str or route_str == "SEVKIYAT":
            self.lbl_estimate.setText("Lütfen en az bir istasyon seçin")
            self.lbl_estimate.setStyleSheet(f"color: {Colors.WARNING}; font-size: 11px;")
            return

        # SmartPlanner'a soracağımız geçici sipariş verisi
        temp_order_data = {
            'width': 0, 'height': 0, 'quantity': self.spin_qty.value(),
            'total_m2': total_m2,
            'thickness': int(self.combo_thickness.currentText()), # Kalınlık artık önemli!
            'product': self.combo_type.currentText(),
            'route': route_str,
            'priority': self.combo_priority.currentText(),
            'date': None # Tarihi o verecek
        }

        # Planlayıcı varsa ona sor, yoksa basit hesap yap
        if planner:
            try:
                # result = (delivery_date, finish_day_index, delayed_orders_list)
                est_date, days, delayed = planner.calculate_impact(temp_order_data)

                # Sonuçları kontrol et
                if est_date and days is not None:
                    # Tarih kutusunu güncelle
                    self.date_picker.setDate(est_date)

                    # Bilgi metni
                    station_count = len([s for s in route_str.split(',') if s.strip() != "SEVKIYAT"])
                    info_text = f"Tahmini: {days} gün ({station_count} istasyon)\nTeslim: {est_date.strftime('%d.%m.%Y')}"

                    # Eğer bu sipariş başkalarını geciktiriyorsa uyar
                    if delayed:
                        info_text += f"\n⚠️ Dikkat: Bu sipariş {len(delayed)} diğer işi geciktirebilir."
                        self.lbl_estimate.setStyleSheet(f"color: {Colors.WARNING}; font-size: 11px; font-weight: bold;")
                    else:
                        self.lbl_estimate.setStyleSheet(f"color: {Colors.SUCCESS}; font-size: 11px; font-weight: bold;")

                    self.lbl_estimate.setText(info_text)
                    return
                else:
                    # Geçersiz sonuç, basit hesaba geç
                    print("SmartPlanner geçersiz sonuç döndü, basit hesap kullanılıyor")

            except Exception as e:
                print(f"Akıllı hesaplama hatası: {e}")
                import traceback
                traceback.print_exc()
                # Hata olursa eski yönteme (basit hesap) düş (Fallback)
        
        # --- ESKİ BASİT YÖNTEM (YEDEK) ---
        days = FactoryCapacity.estimate_days(route_str, total_m2)
        priority = self.combo_priority.currentText()
        if priority == "Kritik": days = max(1, days - 2)
        
        estimated_date = QDate.currentDate().addDays(days)
        self.date_picker.setDate(estimated_date)
        self.lbl_estimate.setText(f"Basit Tahmin: {days} gün → {estimated_date.toString('dd.MM.yyyy')}")
    def save_order(self):
        """Siparisi kaydet - ASENKRON"""
        code = self.inp_code.text().strip()
        customer = self.inp_customer.text().strip()

        if not code:
            QMessageBox.warning(self, "Eksik Bilgi", "Siparis kodu zorunludur.")
            return

        if not customer:
            QMessageBox.warning(self, "Eksik Bilgi", "Musteri adi zorunludur.")
            return

        qty = self.spin_qty.value()
        total_m2 = self.spin_m2.value()

        if qty <= 0 or total_m2 <= 0:
            QMessageBox.warning(self, "Hata", "Adet ve m² 0'dan buyuk olmali.")
            return

        # Rota kontrolu
        route_str = self.get_route_string()
        if route_str == "SEVKIYAT":
            QMessageBox.warning(self, "Hata", "Lutfen en az bir istasyon secin.")
            return

        # Rotayi sirala
        route_str = FactoryCapacity.fix_route_order(route_str)

        thickness = int(self.combo_thickness.currentText())
        product = self.combo_type.currentText()
        product_name = f"{thickness}mm {product}"

        # Stok kontrolu - HIZLI (UI'da yapilabilir)
        if db:
            try:
                current_stock = db.get_stock_quantity(product_name)
                if current_stock < total_m2:
                    reply = QMessageBox.question(
                        self, "Stok Uyarisi",
                        f"Depoda yeterli {product_name} yok!\n\n"
                        f"Mevcut: {current_stock:.1f} m²\n"
                        f"Ihtiyac: {total_m2:.1f} m²\n\n"
                        f"Devam edilsin mi?",
                        QMessageBox.Yes | QMessageBox.No
                    )
                    if reply == QMessageBox.No:
                        return
            except:
                pass

        # Proje ID'sini al
        project_data = self.combo_project.currentData()
        project_id = None
        if project_data and isinstance(project_data, dict):
            project_id = project_data.get('id')

        data = {
            "code": code,
            "customer": customer,
            "product": product,
            "thickness": thickness,
            "width": 0,
            "height": 0,
            "quantity": qty,
            "total_m2": total_m2,
            "priority": self.combo_priority.currentText(),
            "date": self.date_picker.date().toString("yyyy-MM-dd"),
            "route": route_str,
            "sale_price": 0,
            "notes": self.txt_notes.toPlainText().strip(),
            "project_id": project_id
        }

        if db:
            # ASENKRON KAYIT - UI DONMAZ
            self._save_order_async(data)
        else:
            QMessageBox.information(self, "Test", f"Siparis kaydedilecek:\n{data}")
            self.accept()

    def _save_order_async(self, data):
        """Siparis kaydetme islemini arka planda yap"""
        # Progress dialog goster
        self.progress = QProgressDialog("Siparis kaydediliyor...", None, 0, 0, self)
        self.progress.setWindowTitle("Lutfen Bekleyin")
        self.progress.setWindowModality(Qt.WindowModal)
        self.progress.setCursor(QCursor(Qt.WaitCursor))
        self.progress.setMinimumDuration(0)
        self.progress.show()

        # Worker thread basla
        self.worker = OrderSaveWorker(data)
        self.worker.finished.connect(self._on_save_finished)
        self.worker.start()

    def _on_save_finished(self, success, message):
        """Kayit tamamlandiginda cagrilir"""
        self.progress.close()

        if success:
            QMessageBox.information(self, "Basarili", message)
            self.accept()
        else:
            QMessageBox.critical(self, "Hata", message)


if __name__ == "__main__":
    from PySide6.QtWidgets import QApplication
    import sys
    
    app = QApplication(sys.argv)
    app.setFont(QFont("Segoe UI", 9))
    
    dialog = AddOrderDialog()
    dialog.show()
    
    sys.exit(app.exec())