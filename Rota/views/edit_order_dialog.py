"""
EFES ROTA X - Sipariş Güncelleme Dialogu
Mevcut siparişlerde rota ve miktar değişikliği yapılmasını sağlar.
Tahmini teslimat tarihi değişikliği uyarısı verir.
"""

from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel,
    QLineEdit, QPushButton, QComboBox, QDateEdit,
    QFrame, QMessageBox, QSpinBox, QDoubleSpinBox,
    QGridLayout, QCheckBox, QScrollArea,
    QWidget, QGroupBox, QTextEdit
)
from PySide6.QtCore import Qt, QDate
from PySide6.QtGui import QFont
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
    """İstasyon kapasiteleri ve hesaplamalar - factory_config'den dinamik"""

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

        # Fallback
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
        caps = cls.get_capacities()
        return caps.get(station, cls.DEFAULT_CAPACITIES.get(station, 500))

    @classmethod
    def fix_route_order(cls, route_str):
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
# SCROLL ENGELLEYİCİ SPINBOX
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
class EditOrderDialog(QDialog):
    """Sipariş Güncelleme Dialogu"""

    def __init__(self, order_id, parent=None):
        super().__init__(parent)
        self.order_id = order_id
        self.original_order = None
        self.original_delivery_date = None

        self.setWindowTitle("Siparişi Güncelle")
        self.setMinimumSize(700, 650)
        self.resize(750, 700)

        # Sipariş bilgilerini yükle
        self.load_order()

        if not self.original_order:
            QMessageBox.critical(self, "Hata", "Sipariş yüklenemedi!")
            self.reject()
            return

        self.setup_ui()

    def load_order(self):
        """Mevcut sipariş bilgilerini yükle"""
        if not db:
            return

        try:
            with db.get_connection() as conn:
                result = conn.execute("SELECT * FROM orders WHERE id=?", (self.order_id,)).fetchone()
                if result:
                    self.original_order = dict(result)
                    self.original_delivery_date = self.original_order.get('delivery_date', '')
        except Exception as e:
            print(f"Sipariş yükleme hatası: {e}")

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

        title = QLabel(f"Sipariş Güncelle: {self.original_order.get('order_code', '')}")
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

        # Satır 1: Kod (readonly) ve Müşteri
        form.addWidget(QLabel("Sipariş Kodu:"), 0, 0)
        form.addWidget(QLabel("Müşteri:"), 0, 1)

        self.inp_code = QLineEdit()
        self.inp_code.setText(self.original_order.get('order_code', ''))
        self.inp_code.setReadOnly(True)
        self.inp_code.setStyleSheet(f"""
            QLineEdit {{
                background-color: {Colors.HEADER_BG};
                color: {Colors.TEXT_MUTED};
            }}
        """)
        form.addWidget(self.inp_code, 1, 0)

        self.inp_customer = QLineEdit()
        self.inp_customer.setText(self.original_order.get('customer_name', ''))
        self.inp_customer.setPlaceholderText("Firma adı")
        form.addWidget(self.inp_customer, 1, 1)

        # Satır 2: Proje Seçimi
        form.addWidget(QLabel("Proje:"), 2, 0, 1, 2)

        self.combo_project = QComboBox()
        self.combo_project.addItem("-- Projesiz --", None)
        self.load_projects()
        form.addWidget(self.combo_project, 3, 0, 1, 2)

        # Satır 3: Cam tipi ve Kalınlık
        form.addWidget(QLabel("Cam Tipi:"), 4, 0)
        form.addWidget(QLabel("Kalınlık:"), 4, 1)

        self.combo_type = QComboBox()
        self.combo_type.addItems([
            "Renksiz Düzcam", "Füme Cam", "Yeşil Cam", "Mavi Cam", "Bronz Cam",
            "Tentesol Gümüş", "Tentesol Yeşil", "Tentesol Mavi", "Tentesol T.Mavi",
            "Extra Clear", "Ultra Clear", "Low e Cam", "Solar Lowe Cam", "Buzlu Cam",
            "Ayna", "Füme Ayna", "Bronz Ayna", "Mavi Ayna",
            "4.4.1 Lamine", "5.5.1 Lamine", "6.6.1 Lamine",
            "4.4.2 Lamine", "5.5.2 Lamine", "6.6.2 Lamine",
            "Temp. Low-e 71/53", "Temp. Solar Low-e 50/33", "Temp. Solar Low-e 62/44",
            "Temp. Solar Low-e 43/28", "Temp. Solar Low-e 70/37", "Temp. Solar Low-e 51/28",
            "Temp. Solar Low-e 50/27", "Temp. Solar Low-e 50/25"
        ])
        current_type = self.original_order.get('product_type', 'Renksiz Düzcam')
        index = self.combo_type.findText(current_type)
        if index >= 0:
            self.combo_type.setCurrentIndex(index)
        else:
            # Eski tip adlarını yeni adlara çevir (geriye uyumluluk)
            type_mapping = {
                "Düz Cam": "Renksiz Düzcam",
                "Satina": "Buzlu Cam",
                "Temperli": "Renksiz Düzcam",
                "Lamine": "4.4.1 Lamine",
                "Renkli": "Füme Cam"
            }
            mapped_type = type_mapping.get(current_type)
            if mapped_type:
                index = self.combo_type.findText(mapped_type)
                if index >= 0:
                    self.combo_type.setCurrentIndex(index)
        form.addWidget(self.combo_type, 5, 0)

        self.combo_thickness = QComboBox()
        self.combo_thickness.addItems(["4", "5", "6", "8", "10"])
        current_thickness = str(self.original_order.get('thickness', 6))
        index = self.combo_thickness.findText(current_thickness)
        if index >= 0:
            self.combo_thickness.setCurrentIndex(index)
        form.addWidget(self.combo_thickness, 5, 1)

        # Satır 4: Adet ve m2
        form.addWidget(QLabel("Adet:"), 6, 0)
        form.addWidget(QLabel("Toplam m²:"), 6, 1)

        self.spin_qty = QuietSpinBox()
        self.spin_qty.setRange(1, 100000)
        self.spin_qty.setValue(self.original_order.get('quantity', 1))
        form.addWidget(self.spin_qty, 7, 0)

        self.spin_m2 = QuietDoubleSpinBox()
        self.spin_m2.setRange(0.1, 100000)
        self.spin_m2.setValue(self.original_order.get('declared_total_m2', 1))
        self.spin_m2.setSuffix(" m²")
        self.spin_m2.setStyleSheet(f"""
            QDoubleSpinBox {{
                background-color: {Colors.BG};
                border: 2px solid {Colors.ACCENT};
                font-weight: bold;
            }}
        """)
        form.addWidget(self.spin_m2, 7, 1)

        # Satır 5: Öncelik ve Teslim tarihi
        form.addWidget(QLabel("Öncelik:"), 8, 0)
        form.addWidget(QLabel("Teslim Tarihi:"), 8, 1)

        self.combo_priority = QComboBox()
        self.combo_priority.addItems(["Normal", "Acil", "Çok Acil", "Kritik"])
        current_priority = self.original_order.get('priority', 'Normal')
        priority_index = self.combo_priority.findText(current_priority)
        if priority_index >= 0:
            self.combo_priority.setCurrentIndex(priority_index)
        form.addWidget(self.combo_priority, 9, 0)

        self.date_picker = QDateEdit()
        delivery_str = self.original_order.get('delivery_date', '')
        if delivery_str:
            try:
                delivery_date = datetime.strptime(delivery_str, "%Y-%m-%d")
                self.date_picker.setDate(QDate(delivery_date.year, delivery_date.month, delivery_date.day))
            except:
                self.date_picker.setDate(QDate.currentDate())
        else:
            self.date_picker.setDate(QDate.currentDate())
        self.date_picker.setCalendarPopup(True)
        self.date_picker.setDisplayFormat("dd.MM.yyyy")
        form.addWidget(self.date_picker, 9, 1)

        content_layout.addLayout(form)

        # Not alanı
        notes_label = QLabel("Sipariş Notu:")
        notes_label.setStyleSheet(f"color: {Colors.TEXT}; font-size: 11px; font-weight: bold; margin-top: 8px;")
        content_layout.addWidget(notes_label)

        self.txt_notes = QTextEdit()
        self.txt_notes.setPlainText(self.original_order.get('notes', ''))
        self.txt_notes.setPlaceholderText("Bu siparişe ait özel notlar, uyarılar veya hatırlatmalar...")
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

        # Rota seçimi - Factory config'den dinamik
        route_group = QGroupBox("Üretim Rotası")
        route_layout = QGridLayout(route_group)
        route_layout.setHorizontalSpacing(8)
        route_layout.setVerticalSpacing(6)

        # İstasyon checkboxlarını dinamik oluştur
        self.station_checkboxes = {}  # {station_name: QCheckBox}
        self._create_station_checkboxes(route_layout)

        # Mevcut rotayı yükle
        self.load_route()

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

        btn_cancel = QPushButton("İptal")
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

        btn_save = QPushButton("Değişiklikleri Kaydet")
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
        """Aktif projeleri yükle"""
        if not db:
            return

        try:
            projects = db.get_all_projects()
            active_projects = [p for p in projects if p.get('status') in ['Aktif', 'Devam Ediyor']]

            self.combo_project.clear()
            self.combo_project.addItem("-- Projesiz --", None)

            for proj in active_projects:
                display_text = f"{proj['project_name']} - {proj.get('customer_name', 'Müşteri Yok')}"
                self.combo_project.addItem(display_text, proj)

            # Mevcut projeyi seç
            current_project_id = self.original_order.get('project_id')
            if current_project_id:
                for i in range(self.combo_project.count()):
                    proj_data = self.combo_project.itemData(i)
                    if proj_data and isinstance(proj_data, dict) and proj_data.get('id') == current_project_id:
                        self.combo_project.setCurrentIndex(i)
                        break

        except Exception as e:
            print(f"Proje yükleme hatası: {e}")

    def _create_station_checkboxes(self, layout):
        """Factory config'den istasyonları dinamik oluştur"""
        if not factory_config:
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
            if col >= 4:
                break

    def load_route(self):
        """Mevcut rotayı checkbox'lara yükle"""
        route = self.original_order.get('route', '')
        stations = [s.strip() for s in route.split(',') if s.strip()]

        # Dinamik checkboxlardan seçilenleri işaretle
        for station in stations:
            if station in self.station_checkboxes:
                self.station_checkboxes[station].setChecked(True)

    def get_route_string(self):
        """Seçili kutucuklardan rota stringi oluştur"""
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
        Tahmini teslimat süresi hesapla ve eski tarih ile karşılaştır
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
            'thickness': int(self.combo_thickness.currentText()),
            'product': self.combo_type.currentText(),
            'route': route_str,
            'priority': self.combo_priority.currentText(),
            'date': None
        }

        # Eski teslimat tarihi
        old_date_str = self.original_delivery_date
        old_date = None
        if old_date_str:
            try:
                old_date = datetime.strptime(old_date_str, "%Y-%m-%d")
            except:
                pass

        # Planlayıcı varsa ona sor
        if planner:
            try:
                est_date, days, delayed = planner.calculate_impact(temp_order_data)

                # Tarih kutusunu güncelle
                self.date_picker.setDate(est_date)

                # Tarih farkını hesapla
                date_diff_text = ""
                if old_date:
                    date_diff = (est_date - old_date).days
                    if date_diff > 0:
                        date_diff_text = f"\n⚠️ {date_diff} gün gecikme"
                    elif date_diff < 0:
                        date_diff_text = f"\n✓ {abs(date_diff)} gün erken"
                    else:
                        date_diff_text = "\n✓ Aynı tarih"

                # Bilgi metni
                station_count = len([s for s in route_str.split(',') if s.strip() != "SEVKIYAT"])
                info_text = f"Tahmini: {days} gün ({station_count} istasyon)\nTeslim: {est_date.strftime('%d.%m.%Y')}{date_diff_text}"

                # Eğer bu sipariş başkalarını geciktiriyorsa uyar
                if delayed:
                    info_text += f"\n⚠️ Dikkat: Bu değişiklik {len(delayed)} diğer işi geciktirebilir."
                    self.lbl_estimate.setStyleSheet(f"color: {Colors.WARNING}; font-size: 11px; font-weight: bold;")
                else:
                    self.lbl_estimate.setStyleSheet(f"color: {Colors.SUCCESS}; font-size: 11px; font-weight: bold;")

                self.lbl_estimate.setText(info_text)
                return

            except Exception as e:
                print(f"Akıllı hesaplama hatası: {e}")

    def save_order(self):
        """Değişiklikleri kaydet"""
        customer = self.inp_customer.text().strip()

        if not customer:
            QMessageBox.warning(self, "Eksik Bilgi", "Müşteri adı zorunludur.")
            return

        qty = self.spin_qty.value()
        total_m2 = self.spin_m2.value()

        if qty <= 0 or total_m2 <= 0:
            QMessageBox.warning(self, "Hata", "Adet ve m² 0'dan büyük olmalı.")
            return

        # Rota kontrolü
        route_str = self.get_route_string()
        if route_str == "SEVKIYAT":
            QMessageBox.warning(self, "Hata", "Lütfen en az bir istasyon seçin.")
            return

        # Rotayı sırala
        route_str = FactoryCapacity.fix_route_order(route_str)

        # Değişiklik kontrolü
        has_changes = False
        change_summary = []

        # Rota değişikliği
        old_route = self.original_order.get('route', '')
        if old_route != route_str:
            has_changes = True
            change_summary.append("• Rota değiştirildi")

        # Miktar değişikliği
        old_m2 = self.original_order.get('declared_total_m2', 0)
        if abs(old_m2 - total_m2) > 0.01:
            has_changes = True
            diff = total_m2 - old_m2
            if diff > 0:
                change_summary.append(f"• Miktar artırıldı (+{diff:.2f} m²)")
            else:
                change_summary.append(f"• Miktar azaltıldı ({diff:.2f} m²)")

        # Teslimat tarihi değişikliği
        new_date_str = self.date_picker.date().toString("yyyy-MM-dd")
        if self.original_delivery_date != new_date_str:
            has_changes = True
            try:
                old_date = datetime.strptime(self.original_delivery_date, "%Y-%m-%d")
                new_date = datetime.strptime(new_date_str, "%Y-%m-%d")
                diff_days = (new_date - old_date).days
                if diff_days > 0:
                    change_summary.append(f"• Teslimat {diff_days} gün ileri alındı")
                elif diff_days < 0:
                    change_summary.append(f"• Teslimat {abs(diff_days)} gün öne alındı")
            except:
                change_summary.append("• Teslimat tarihi değiştirildi")

        # Eğer değişiklik yoksa uyar
        if not has_changes:
            # Diğer alanlarda değişiklik var mı kontrol et
            if (self.original_order.get('customer_name') == customer and
                self.original_order.get('product_type') == self.combo_type.currentText() and
                self.original_order.get('thickness') == int(self.combo_thickness.currentText()) and
                self.original_order.get('quantity') == qty and
                self.original_order.get('priority') == self.combo_priority.currentText() and
                self.original_order.get('notes', '') == self.txt_notes.toPlainText().strip()):

                QMessageBox.information(self, "Bilgi", "Hiçbir değişiklik yapılmadı.")
                return

        # Onay mesajı
        if change_summary:
            confirm_msg = "Aşağıdaki değişiklikler yapılacak:\n\n" + "\n".join(change_summary) + "\n\nDevam etmek istiyor musunuz?"
            reply = QMessageBox.question(
                self, "Değişiklikleri Onayla",
                confirm_msg,
                QMessageBox.Yes | QMessageBox.No
            )
            if reply == QMessageBox.No:
                return

        # Proje ID'sini al
        project_data = self.combo_project.currentData()
        project_id = None
        if project_data and isinstance(project_data, dict):
            project_id = project_data.get('id')

        data = {
            "customer": customer,
            "product": self.combo_type.currentText(),
            "thickness": int(self.combo_thickness.currentText()),
            "width": self.original_order.get('width', 0),
            "height": self.original_order.get('height', 0),
            "quantity": qty,
            "total_m2": total_m2,
            "priority": self.combo_priority.currentText(),
            "date": new_date_str,
            "route": route_str,
            "notes": self.txt_notes.toPlainText().strip(),
            "project_id": project_id
        }

        if db:
            try:
                success, message = db.update_order(self.order_id, data)
                if success:
                    QMessageBox.information(self, "Başarılı",
                        f"Sipariş '{self.original_order.get('order_code')}' güncellendi.\n\n" +
                        ("\n".join(change_summary) if change_summary else "Değişiklikler kaydedildi."))
                    self.accept()
                else:
                    QMessageBox.critical(self, "Hata", f"Güncelleme başarısız:\n{message}")
            except Exception as e:
                QMessageBox.critical(self, "Hata", f"Güncelleme hatası:\n{str(e)}")
        else:
            QMessageBox.information(self, "Test", f"Sipariş güncellenecek:\n{data}")
            self.accept()


if __name__ == "__main__":
    from PySide6.QtWidgets import QApplication
    import sys

    app = QApplication(sys.argv)
    app.setFont(QFont("Segoe UI", 9))

    # Test için varsayılan order_id
    dialog = EditOrderDialog(order_id=1)
    dialog.show()

    sys.exit(app.exec())
