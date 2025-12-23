"""
EFES ROTA X - Sevkiyat Yonetim Ekrani
Excel temali, patron odakli tasarim

Ozellikler:
- Bugun sevk edilecekler (kritik)
- Geciken sevkiyatlar (cok kritik - kirmizi uyari)
- Hazir bekleyenler
- Hizli sevkiyat ozeti
- Sehpa yonetimi
- Tek tikla sevkiyat
"""

import sys
from datetime import datetime, timedelta

try:
    from utils.timezone_helper import now_turkey, get_current_date_turkey
except ImportError:
    # Fallback: timezone_helper bulunamazsa normal datetime kullan
    from datetime import datetime as _dt
    now_turkey = lambda: _dt.now()
    get_current_date_turkey = lambda: _dt.now().date()
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel,
    QTableWidget, QTableWidgetItem, QHeaderView,
    QPushButton, QAbstractItemView, QInputDialog,
    QListWidget, QFrame, QMessageBox, QComboBox,
    QScrollArea, QSplitter, QApplication, QListWidgetItem,
    QLineEdit, QDialog, QTextEdit
)
from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QColor, QFont

try:
    from core.db_manager import db
except ImportError:
    db = None


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
    SELECTION = "#B4D7FF"
    ACCENT = "#217346"
    ROW_ALT = "#F9F9F9"
    
    CRITICAL = "#C00000"
    CRITICAL_BG = "#FDE8E8"
    WARNING = "#C65911"
    WARNING_BG = "#FFF3E0"
    SUCCESS = "#107C41"
    SUCCESS_BG = "#E6F4EA"
    INFO = "#0066CC"
    INFO_BG = "#E3F2FD"
    
    PURPLE = "#7C3AED"
    PURPLE_BG = "#F3E8FF"


# =============================================================================
# ANA WIDGET
# =============================================================================
class ShippingView(QWidget):
    """Sevkiyat Yonetim Ekrani"""
    
    def __init__(self):
        super().__init__()
        self.ready_orders = []
        self.all_ready_orders = []  # Filtreleme icin tum siparisler
        self.delayed_orders = []
        self.today_orders = []
        self.setup_ui()
        
        # Otomatik yenileme (30 saniye - optimal)
        self.timer = QTimer(self)
        self.timer.timeout.connect(self.refresh_data)
        self.timer.start(30000)  # 30 saniye ✅

        # 🚀 RefreshManager kaydı
        try:
            from core.refresh_manager import refresh_manager
            refresh_manager.register_view(
                data_key='shipments',
                callback=self.refresh_data,
                dependencies=['orders']
            )
        except:
            pass

        self.refresh_data()
    
    def setup_ui(self):
        self.setStyleSheet(f"background-color: {Colors.BG};")
        
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        
        # Toolbar
        toolbar = self._create_toolbar()
        layout.addWidget(toolbar)
        
        # Ozet kartlari
        summary_bar = self._create_summary_bar()
        layout.addWidget(summary_bar)
        
        # Ana icerik
        content = QSplitter(Qt.Horizontal)
        content.setStyleSheet(f"QSplitter::handle {{ background-color: {Colors.BORDER}; width: 1px; }}")
        
        # Sol panel: Siparisler
        left_panel = self._create_orders_panel()
        content.addWidget(left_panel)
        
        # Sag panel: Sehpa yonetimi
        right_panel = self._create_pallet_panel()
        content.addWidget(right_panel)
        
        content.setSizes([600, 400])
        
        layout.addWidget(content, 1)
        
        # Status bar
        statusbar = self._create_statusbar()
        layout.addWidget(statusbar)
    
    def _create_toolbar(self):
        toolbar = QFrame()
        toolbar.setFixedHeight(32)
        toolbar.setStyleSheet(f"""
            QFrame {{
                background-color: {Colors.HEADER_BG};
                border-bottom: 1px solid {Colors.BORDER};
            }}
        """)
        
        layout = QHBoxLayout(toolbar)
        layout.setContentsMargins(8, 0, 8, 0)
        layout.setSpacing(8)
        
        lbl_title = QLabel("Sevkiyat Yonetimi")
        lbl_title.setStyleSheet(f"font-size: 12px; font-weight: bold; color: {Colors.TEXT};")
        layout.addWidget(lbl_title)
        
        self._add_separator(layout)
        
        # Tarih
        today = now_turkey().strftime('%d.%m.%Y %A')
        lbl_date = QLabel(today)
        lbl_date.setStyleSheet(f"font-size: 11px; color: {Colors.TEXT_SECONDARY};")
        layout.addWidget(lbl_date)
        
        layout.addStretch()

        # Siparis arama
        lbl_search = QLabel("Ara:")
        lbl_search.setStyleSheet(f"font-size: 11px; color: {Colors.TEXT_SECONDARY};")
        layout.addWidget(lbl_search)

        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("Sipariş kodu veya müşteri...")
        self.search_input.setFixedWidth(200)
        self.search_input.setStyleSheet(f"""
            QLineEdit {{
                border: 1px solid {Colors.BORDER};
                border-radius: 2px;
                padding: 4px 8px;
                font-size: 11px;
                background-color: {Colors.BG};
            }}
            QLineEdit:focus {{
                border: 1px solid {Colors.ACCENT};
            }}
        """)
        self.search_input.textChanged.connect(self.filter_orders)
        layout.addWidget(self.search_input)

        self._add_separator(layout)

        # Geçmiş sevkiyatlar
        btn_history = QPushButton("Geçmiş Sevkiyatlar")
        btn_history.setStyleSheet(f"""
            QPushButton {{
                background: transparent;
                border: 1px solid transparent;
                border-radius: 2px;
                padding: 4px 10px;
                color: {Colors.TEXT};
                font-size: 11px;
            }}
            QPushButton:hover {{
                background-color: #E5E5E5;
                border: 1px solid {Colors.BORDER};
            }}
        """)
        btn_history.clicked.connect(self.show_history)
        layout.addWidget(btn_history)

        # Yenile
        btn_refresh = QPushButton("Yenile")
        btn_refresh.setStyleSheet(f"""
            QPushButton {{
                background: transparent;
                border: 1px solid transparent;
                border-radius: 2px;
                padding: 4px 10px;
                color: {Colors.TEXT};
                font-size: 11px;
            }}
            QPushButton:hover {{
                background-color: #E5E5E5;
                border: 1px solid {Colors.BORDER};
            }}
        """)
        btn_refresh.clicked.connect(self.refresh_data)
        layout.addWidget(btn_refresh)

        return toolbar
    
    def _create_summary_bar(self):
        """Modern, kompakt ozet cubugu"""
        bar = QFrame()
        bar.setFixedHeight(36)
        bar.setStyleSheet(f"""
            QFrame {{
                background-color: {Colors.BG};
                border-bottom: 1px solid {Colors.BORDER};
            }}
        """)
        
        layout = QHBoxLayout(bar)
        layout.setContentsMargins(12, 0, 12, 0)
        layout.setSpacing(24)
        
        # Geciken (kirmizi vurgulu)
        delayed_container = QHBoxLayout()
        delayed_container.setSpacing(6)
        
        self.lbl_delayed_count = QLabel("0")
        self.lbl_delayed_count.setStyleSheet(f"""
            background-color: {Colors.CRITICAL};
            color: white;
            padding: 2px 8px;
            border-radius: 10px;
            font-size: 12px;
            font-weight: bold;
            min-width: 20px;
        """)
        self.lbl_delayed_count.setAlignment(Qt.AlignCenter)
        delayed_container.addWidget(self.lbl_delayed_count)
        
        lbl_delayed_text = QLabel("Geciken")
        lbl_delayed_text.setStyleSheet(f"font-size: 11px; color: {Colors.CRITICAL}; font-weight: 600;")
        delayed_container.addWidget(lbl_delayed_text)
        
        layout.addLayout(delayed_container)
        
        # Bugun teslim (turuncu)
        today_container = QHBoxLayout()
        today_container.setSpacing(6)
        
        self.lbl_today_count = QLabel("0")
        self.lbl_today_count.setStyleSheet(f"""
            background-color: {Colors.WARNING};
            color: white;
            padding: 2px 8px;
            border-radius: 10px;
            font-size: 12px;
            font-weight: bold;
            min-width: 20px;
        """)
        self.lbl_today_count.setAlignment(Qt.AlignCenter)
        today_container.addWidget(self.lbl_today_count)
        
        lbl_today_text = QLabel("Bugun Teslim")
        lbl_today_text.setStyleSheet(f"font-size: 11px; color: {Colors.WARNING}; font-weight: 600;")
        today_container.addWidget(lbl_today_text)
        
        layout.addLayout(today_container)
        
        # Ayirici
        sep1 = QFrame()
        sep1.setFixedSize(1, 20)
        sep1.setStyleSheet(f"background-color: {Colors.BORDER};")
        layout.addWidget(sep1)
        
        # Sevke hazir
        ready_container = QHBoxLayout()
        ready_container.setSpacing(6)
        
        self.lbl_ready_count = QLabel("0")
        self.lbl_ready_count.setStyleSheet(f"""
            background-color: {Colors.SUCCESS};
            color: white;
            padding: 2px 8px;
            border-radius: 10px;
            font-size: 12px;
            font-weight: bold;
            min-width: 20px;
        """)
        self.lbl_ready_count.setAlignment(Qt.AlignCenter)
        ready_container.addWidget(self.lbl_ready_count)
        
        lbl_ready_text = QLabel("Sevke Hazir")
        lbl_ready_text.setStyleSheet(f"font-size: 11px; color: {Colors.SUCCESS}; font-weight: 600;")
        ready_container.addWidget(lbl_ready_text)
        
        layout.addLayout(ready_container)
        
        # Toplam m2
        m2_container = QHBoxLayout()
        m2_container.setSpacing(4)
        
        self.lbl_m2_value = QLabel("0")
        self.lbl_m2_value.setStyleSheet(f"font-size: 13px; color: {Colors.TEXT}; font-weight: bold;")
        m2_container.addWidget(self.lbl_m2_value)
        
        lbl_m2_unit = QLabel("m²")
        lbl_m2_unit.setStyleSheet(f"font-size: 11px; color: {Colors.TEXT_MUTED};")
        m2_container.addWidget(lbl_m2_unit)
        
        layout.addLayout(m2_container)
        
        layout.addStretch()
        
        # Sag taraf: Aktif sehpa sayisi
        pallet_container = QHBoxLayout()
        pallet_container.setSpacing(6)
        
        self.lbl_pallet_count = QLabel("0")
        self.lbl_pallet_count.setStyleSheet(f"""
            background-color: {Colors.PURPLE_BG};
            color: {Colors.PURPLE};
            padding: 2px 8px;
            border-radius: 10px;
            font-size: 12px;
            font-weight: bold;
            min-width: 20px;
        """)
        self.lbl_pallet_count.setAlignment(Qt.AlignCenter)
        pallet_container.addWidget(self.lbl_pallet_count)
        
        lbl_pallet_text = QLabel("Aktif Sehpa")
        lbl_pallet_text.setStyleSheet(f"font-size: 11px; color: {Colors.PURPLE}; font-weight: 600;")
        pallet_container.addWidget(lbl_pallet_text)
        
        layout.addLayout(pallet_container)
        
        return bar
    
    def _create_orders_panel(self):
        panel = QFrame()
        panel.setStyleSheet(f"background-color: {Colors.BG};")
        
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        
        # Baslik
        header = QFrame()
        header.setFixedHeight(28)
        header.setStyleSheet(f"""
            QFrame {{
                background-color: {Colors.HEADER_BG};
                border-bottom: 1px solid {Colors.BORDER};
            }}
        """)
        header_layout = QHBoxLayout(header)
        header_layout.setContentsMargins(12, 0, 12, 0)
        
        lbl = QLabel("Sevke Hazir Siparisler")
        lbl.setStyleSheet(f"font-size: 11px; font-weight: bold; color: {Colors.TEXT};")
        header_layout.addWidget(lbl)
        
        layout.addWidget(header)
        
        # Tablo
        self.table_orders = QTableWidget()
        self.table_orders.setColumnCount(7)
        self.table_orders.setHorizontalHeaderLabels([
            "Kod", "Musteri", "Urun", "Adet", "m2", "Teslim", "Durum"
        ])
        
        self.table_orders.verticalHeader().setVisible(False)
        self.table_orders.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.table_orders.setSelectionMode(QAbstractItemView.SingleSelection)
        self.table_orders.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.table_orders.setAlternatingRowColors(True)
        self.table_orders.setShowGrid(True)
        
        self.table_orders.setStyleSheet(f"""
            QTableWidget {{
                background-color: {Colors.BG};
                alternate-background-color: {Colors.ROW_ALT};
                gridline-color: {Colors.GRID};
                border: none;
                font-size: 11px;
            }}
            QTableWidget::item {{
                padding: 4px 8px;
            }}
            QTableWidget::item:selected {{
                background-color: {Colors.SELECTION};
                color: {Colors.TEXT};
            }}
            QHeaderView::section {{
                background-color: {Colors.HEADER_BG};
                color: {Colors.TEXT};
                padding: 6px 8px;
                border: none;
                border-right: 1px solid {Colors.GRID};
                border-bottom: 1px solid {Colors.BORDER};
                font-size: 11px;
                font-weight: 600;
            }}
        """)
        
        header = self.table_orders.horizontalHeader()
        header.setSectionResizeMode(QHeaderView.Interactive)
        self.table_orders.setColumnWidth(0, 90)
        self.table_orders.setColumnWidth(1, 150)
        self.table_orders.setColumnWidth(2, 80)
        self.table_orders.setColumnWidth(3, 50)
        self.table_orders.setColumnWidth(4, 50)
        self.table_orders.setColumnWidth(5, 80)
        self.table_orders.setColumnWidth(6, 80)
        header.setStretchLastSection(True)
        
        self.table_orders.verticalHeader().setDefaultSectionSize(26)
        
        layout.addWidget(self.table_orders, 1)
        
        # Alt butonlar
        btn_bar = QFrame()
        btn_bar.setFixedHeight(50)
        btn_bar.setStyleSheet(f"""
            QFrame {{
                background-color: {Colors.HEADER_BG};
                border-top: 1px solid {Colors.BORDER};
            }}
        """)
        btn_layout = QHBoxLayout(btn_bar)
        btn_layout.setContentsMargins(12, 8, 12, 8)
        btn_layout.setSpacing(8)
        
        # Sehpaya ekle
        btn_add = QPushButton("Sehpaya Ekle")
        btn_add.setFixedHeight(34)
        btn_add.setStyleSheet(f"""
            QPushButton {{
                background-color: {Colors.ACCENT};
                border: none;
                border-radius: 4px;
                padding: 0 16px;
                color: white;
                font-size: 11px;
                font-weight: bold;
            }}
            QPushButton:hover {{
                background-color: #1D6640;
            }}
        """)
        btn_add.clicked.connect(self.add_to_pallet)
        btn_layout.addWidget(btn_add)
        
        # Hizli sevk
        btn_quick_ship = QPushButton("Hizli Sevk (Sehpasiz)")
        btn_quick_ship.setFixedHeight(34)
        btn_quick_ship.setStyleSheet(f"""
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
        btn_quick_ship.clicked.connect(self.quick_ship_order)
        btn_layout.addWidget(btn_quick_ship)
        
        btn_layout.addStretch()
        
        layout.addWidget(btn_bar)
        
        return panel
    
    def _create_pallet_panel(self):
        panel = QFrame()
        panel.setStyleSheet(f"""
            QFrame {{
                background-color: {Colors.BG};
                border-left: 1px solid {Colors.BORDER};
            }}
        """)
        
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        
        # Baslik
        header = QFrame()
        header.setFixedHeight(28)
        header.setStyleSheet(f"""
            QFrame {{
                background-color: {Colors.HEADER_BG};
                border-bottom: 1px solid {Colors.BORDER};
            }}
        """)
        header_layout = QHBoxLayout(header)
        header_layout.setContentsMargins(12, 0, 12, 0)
        
        lbl = QLabel("Sehpa Yonetimi")
        lbl.setStyleSheet(f"font-size: 11px; font-weight: bold; color: {Colors.TEXT};")
        header_layout.addWidget(lbl)
        
        layout.addWidget(header)
        
        # Icerik
        content = QWidget()
        content_layout = QVBoxLayout(content)
        content_layout.setContentsMargins(12, 12, 12, 12)
        content_layout.setSpacing(12)
        
        # Sehpa secimi
        lbl_select = QLabel("Aktif Sehpa:")
        lbl_select.setStyleSheet(f"font-size: 11px; color: {Colors.TEXT_SECONDARY}; font-weight: bold;")
        content_layout.addWidget(lbl_select)
        
        select_row = QHBoxLayout()
        
        self.combo_pallets = QComboBox()
        self.combo_pallets.setStyleSheet(f"""
            QComboBox {{
                border: 1px solid {Colors.BORDER};
                border-radius: 3px;
                padding: 6px 10px;
                font-size: 11px;
                background-color: {Colors.BG};
            }}
        """)
        self.combo_pallets.currentIndexChanged.connect(self.load_pallet_content)
        select_row.addWidget(self.combo_pallets, 1)

        # Sehpa Kapat Butonu (3 SABİT SEHPA İÇİN)
        btn_close = QPushButton("Kapat")
        btn_close.setFixedHeight(32)
        btn_close.setStyleSheet(f"""
            QPushButton {{
                background-color: {Colors.CRITICAL};
                border: none;
                border-radius: 3px;
                color: white;
                font-size: 11px;
                font-weight: bold;
                padding: 0 12px;
            }}
            QPushButton:hover {{
                background-color: #A00000;
            }}
        """)
        btn_close.setToolTip("Sehpayi Kapat ve Musteriye Gonder")
        btn_close.clicked.connect(self.close_active_sehpa)
        select_row.addWidget(btn_close)
        
        content_layout.addLayout(select_row)
        
        # Sehpa bilgisi
        self.lbl_pallet_info = QLabel("")
        self.lbl_pallet_info.setStyleSheet(f"font-size: 10px; color: {Colors.TEXT_MUTED};")
        content_layout.addWidget(self.lbl_pallet_info)
        
        # Sehpa icerigi
        lbl_content = QLabel("Sehpa Icerigi:")
        lbl_content.setStyleSheet(f"font-size: 11px; color: {Colors.TEXT_SECONDARY}; font-weight: bold;")
        content_layout.addWidget(lbl_content)
        
        self.list_pallet = QListWidget()
        self.list_pallet.setStyleSheet(f"""
            QListWidget {{
                background-color: {Colors.BG};
                border: 1px solid {Colors.BORDER};
                border-radius: 4px;
                font-size: 11px;
            }}
            QListWidget::item {{
                padding: 8px;
                border-bottom: 1px solid {Colors.GRID};
            }}
            QListWidget::item:selected {{
                background-color: {Colors.SELECTION};
            }}
        """)
        content_layout.addWidget(self.list_pallet, 1)
        
        # Sehpa ozeti
        self.lbl_pallet_summary = QLabel("0 siparis, 0 m2")
        self.lbl_pallet_summary.setStyleSheet(f"""
            font-size: 11px; 
            color: {Colors.INFO}; 
            font-weight: bold;
            padding: 8px;
            background-color: {Colors.INFO_BG};
            border-radius: 4px;
        """)
        content_layout.addWidget(self.lbl_pallet_summary)
        
        # Butonlar
        btn_remove = QPushButton("Secili Siparisi Cikar")
        btn_remove.setFixedHeight(32)
        btn_remove.setStyleSheet(f"""
            QPushButton {{
                background-color: {Colors.WARNING_BG};
                border: 1px solid {Colors.WARNING};
                border-radius: 4px;
                color: {Colors.WARNING};
                font-size: 11px;
                font-weight: bold;
            }}
            QPushButton:hover {{
                background-color: {Colors.WARNING};
                color: white;
            }}
        """)
        btn_remove.clicked.connect(self.remove_from_pallet)
        content_layout.addWidget(btn_remove)
        
        btn_ship = QPushButton("SEHPAYI SEVK ET")
        btn_ship.setFixedHeight(40)
        btn_ship.setStyleSheet(f"""
            QPushButton {{
                background-color: {Colors.ACCENT};
                border: none;
                border-radius: 4px;
                color: white;
                font-size: 12px;
                font-weight: bold;
            }}
            QPushButton:hover {{
                background-color: #1D6640;
            }}
        """)
        btn_ship.clicked.connect(self.ship_pallet)
        content_layout.addWidget(btn_ship)
        
        layout.addWidget(content, 1)
        
        # Tamamlanan sevkiyatlar
        completed_header = QFrame()
        completed_header.setFixedHeight(28)
        completed_header.setStyleSheet(f"""
            QFrame {{
                background-color: {Colors.HEADER_BG};
                border-top: 1px solid {Colors.BORDER};
                border-bottom: 1px solid {Colors.BORDER};
            }}
        """)
        ch_layout = QHBoxLayout(completed_header)
        ch_layout.setContentsMargins(12, 0, 12, 0)
        
        lbl_completed = QLabel("Son Sevkiyatlar")
        lbl_completed.setStyleSheet(f"font-size: 11px; font-weight: bold; color: {Colors.TEXT};")
        ch_layout.addWidget(lbl_completed)
        
        layout.addWidget(completed_header)
        
        # Son sevkiyatlar listesi
        self.list_completed = QListWidget()
        self.list_completed.setFixedHeight(120)
        self.list_completed.setStyleSheet(f"""
            QListWidget {{
                background-color: {Colors.BG};
                border: none;
                font-size: 10px;
            }}
            QListWidget::item {{
                padding: 6px 12px;
                border-bottom: 1px solid {Colors.GRID};
                color: {Colors.TEXT_SECONDARY};
            }}
        """)
        layout.addWidget(self.list_completed)
        
        return panel
    
    def _create_statusbar(self):
        statusbar = QFrame()
        statusbar.setFixedHeight(22)
        statusbar.setStyleSheet(f"""
            QFrame {{
                background-color: {Colors.HEADER_BG};
                border-top: 1px solid {Colors.BORDER};
            }}
        """)
        
        layout = QHBoxLayout(statusbar)
        layout.setContentsMargins(8, 0, 8, 0)
        
        self.status_label = QLabel("Hazir")
        self.status_label.setStyleSheet(f"color: {Colors.TEXT_SECONDARY}; font-size: 11px;")
        layout.addWidget(self.status_label)
        
        layout.addStretch()
        
        return statusbar
    
    def _add_separator(self, layout):
        sep = QFrame()
        sep.setFixedWidth(1)
        sep.setFixedHeight(20)
        sep.setStyleSheet(f"background-color: {Colors.BORDER};")
        layout.addWidget(sep)
    
    # =========================================================================
    # VERI ISLEMLERI
    # =========================================================================
    
    def refresh_data(self):
        """Tum verileri yenile"""
        try:
            self._load_ready_orders()
            self._load_pallets()
            self._load_completed_shipments()
            self._update_summary()
            self.status_label.setText(f"Guncellendi: {now_turkey().strftime('%H:%M:%S')}")
        except Exception as e:
            self.status_label.setText(f"Hata: {str(e)}")
    
    def _load_ready_orders(self):
        """Sevke hazir siparisleri yukle"""
        self.table_orders.setRowCount(0)
        self.ready_orders = []
        self.delayed_orders = []
        self.today_orders = []
        
        if not db:
            return
        
        try:
            all_orders = db.get_production_matrix_advanced()
            today = now_turkey().date()
            
            # Orders tablosundan ek bilgileri al
            orders_info = {}
            try:
                with db.get_connection() as conn:
                    rows = conn.execute("""
                        SELECT id, delivery_date, declared_total_m2, pallet_id, status,
                               COALESCE(shipped_quantity, 0) as shipped
                        FROM orders
                        WHERE status NOT IN ('Sevk Edildi')
                    """).fetchall()

                    for row in rows:
                        orders_info[row['id']] = {
                            'delivery_date': row['delivery_date'],
                            'm2': row['declared_total_m2'] or 0,
                            'pallet_id': row['pallet_id'],
                            'status': row['status'],
                            'shipped': row['shipped']
                        }
            except Exception as e:
                print(f"⚠️ Orders info error: {e}")
                import traceback
                traceback.print_exc()

            ready_list = []

            for order in all_orders:
                order_id = order.get('id')

                # KISMI SEVKİYAT: Hazır adet sayısını hesapla
                try:
                    ready_qty = db.get_ready_quantity_for_shipping(order_id)
                except Exception as e:
                    print(f"⚠️ Ready qty error for order {order_id}: {e}")
                    ready_qty = 0

                # Hazır adedi yoksa geç
                if ready_qty <= 0:
                    continue

                # Bilgileri zenginleştir
                info = orders_info.get(order_id, {})
                order['delivery_date'] = info.get('delivery_date', '')
                order['m2'] = info.get('m2', 0)
                order['ready_quantity'] = ready_qty  # ← YENI: Hazır adet
                order['shipped_quantity'] = info.get('shipped', 0)  # ← YENI: Sevk edilmiş
                order['pallet_id'] = info.get('pallet_id')
                
                # Teslim tarihi analizi
                delivery_str = order['delivery_date']
                if delivery_str:
                    try:
                        delivery_date = datetime.strptime(delivery_str, '%Y-%m-%d').date()
                        days_diff = (delivery_date - today).days
                        order['days_diff'] = days_diff
                        
                        if days_diff < 0:
                            order['status_type'] = 'delayed'
                            self.delayed_orders.append(order)
                        elif days_diff == 0:
                            order['status_type'] = 'today'
                            self.today_orders.append(order)
                        else:
                            order['status_type'] = 'normal'
                    except:
                        order['status_type'] = 'normal'
                        order['days_diff'] = 999
                else:
                    order['status_type'] = 'normal'
                    order['days_diff'] = 999
                
                ready_list.append(order)
            
            # Oncelik sirasina gore sirala: geciken > bugun > diger
            ready_list.sort(key=lambda x: (
                0 if x.get('status_type') == 'delayed' else (1 if x.get('status_type') == 'today' else 2),
                x.get('days_diff', 999)
            ))
            
            self.ready_orders = ready_list
            self.all_ready_orders = ready_list.copy()  # Filtreleme için kaydet

            # Tabloyu doldur
            self._populate_orders_table()

        except Exception as e:
            print(f"Siparis yukleme hatasi: {e}")
    
    def _load_pallets(self):
        """3 SABİT SEHPAYI YÜKLE"""
        if not db:
            return

        current_name = self.combo_pallets.currentText()
        self.combo_pallets.clear()

        try:
            # 3 sabit sehpayı direkt ekle
            standard_pallets = ["Büyük L", "Küçük L", "Büyük A"]

            with db.get_connection() as conn:
                for sehpa_name in standard_pallets:
                    # Her sehpanın ID'sini bul
                    sehpa = conn.execute(
                        "SELECT id FROM shipments WHERE pallet_name = ? AND status = 'Aktif'",
                        (sehpa_name,)
                    ).fetchone()

                    if sehpa:
                        # Sehpada kaç sipariş var?
                        order_count = conn.execute(
                            "SELECT COUNT(*) FROM orders WHERE pallet_id = ?",
                            (sehpa['id'],)
                        ).fetchone()[0]

                        display_text = f"{sehpa_name} ({order_count} sipariş)"
                        self.combo_pallets.addItem(display_text, sehpa['id'])

            # Önceki seçimi geri yükle
            if current_name:
                for i in range(self.combo_pallets.count()):
                    if current_name in self.combo_pallets.itemText(i):
                        self.combo_pallets.setCurrentIndex(i)
                        break

            self.load_pallet_content()

        except Exception as e:
            print(f"Sehpa yukleme hatasi: {e}")
    
    def _load_completed_shipments(self):
        """Son sevkiyatlari yukle"""
        self.list_completed.clear()
        
        if not db:
            return
        
        try:
            completed = db.get_shipped_pallets()
            
            for p in completed[:10]:  # Son 10 sevkiyat
                date_str = p.get('shipped_at', p.get('created_at', ''))
                if date_str:
                    try:
                        dt = datetime.strptime(date_str, '%Y-%m-%d %H:%M:%S')
                        date_str = dt.strftime('%d.%m %H:%M')
                    except:
                        pass
                
                item = QListWidgetItem(
                    f"{p.get('pallet_name', '-')} - {p.get('customer_name', '-')} ({date_str})"
                )
                self.list_completed.addItem(item)
                
        except Exception as e:
            print(f"Tamamlanan sevkiyat yukleme hatasi: {e}")
    
    def _update_summary(self):
        """Ozet istatistiklerini guncelle"""
        # Geciken
        delayed_count = len(self.delayed_orders)
        self.lbl_delayed_count.setText(str(delayed_count))
        # Geciken yoksa gizle
        self.lbl_delayed_count.setVisible(delayed_count > 0)
        
        # Bugun
        today_count = len(self.today_orders)
        self.lbl_today_count.setText(str(today_count))
        self.lbl_today_count.setVisible(today_count > 0)
        
        # Hazir
        self.lbl_ready_count.setText(str(len(self.ready_orders)))
        
        # Toplam m2
        total_m2 = sum(o.get('m2', 0) for o in self.ready_orders)
        self.lbl_m2_value.setText(f"{total_m2:,.0f}".replace(",", "."))
        
        # Aktif sehpa
        self.lbl_pallet_count.setText(str(self.combo_pallets.count()))
    
    def load_pallet_content(self):
        """Secili sehpa icerigini yukle"""
        self.list_pallet.clear()
        self.lbl_pallet_summary.setText("0 siparis, 0 m2")
        self.lbl_pallet_info.setText("")
        
        pallet_id = self.combo_pallets.currentData()
        if not pallet_id or not db:
            return
        
        try:
            with db.get_connection() as conn:
                # Sehpa bilgisi (shipments tablosundan)
                pallet = conn.execute(
                    "SELECT * FROM shipments WHERE id = ?", (pallet_id,)
                ).fetchone()

                if pallet:
                    self.lbl_pallet_info.setText(
                        f"Musteri: {pallet['customer_name'] if pallet['customer_name'] else 'Genel'}"
                    )
                
                # Sehpadaki siparisler (KISMI SEVKİYAT: shipped_quantity kullan)
                rows = conn.execute("""
                    SELECT order_code, customer_name, product_type, quantity,
                           COALESCE(shipped_quantity, 0) as shipped_qty,
                           declared_total_m2
                    FROM orders
                    WHERE pallet_id = ?
                    ORDER BY order_code
                """, (pallet_id,)).fetchall()

                # DEBUG
                print(f"\n🔍 DEBUG Sehpa İçeriği (pallet_id={pallet_id}):")
                for r in rows:
                    print(f"   {r['order_code']}: shipped_qty={r['shipped_qty']}, total={r['quantity']}")

                total_m2 = 0
                for r in rows:
                    # Sevk edilen adede göre m2 hesapla (oransal)
                    total_order_m2 = r['declared_total_m2'] or 0
                    total_order_qty = r['quantity']
                    shipped_qty = r['shipped_qty']

                    if total_order_qty > 0:
                        shipped_m2 = (shipped_qty / total_order_qty) * total_order_m2
                    else:
                        shipped_m2 = 0

                    total_m2 += shipped_m2

                    item = QListWidgetItem(
                        f"{r['order_code']} - {r['customer_name']} ({shipped_qty}/{total_order_qty} adet, {shipped_m2:.0f} m2)"
                    )
                    item.setData(Qt.UserRole, r['order_code'])
                    self.list_pallet.addItem(item)

                self.lbl_pallet_summary.setText(f"{len(rows)} siparis, {total_m2:.0f} m2")
                
        except Exception as e:
            print(f"Sehpa icerigi yukleme hatasi: {e}")
    
    # =========================================================================
    # AKSIYONLAR
    # =========================================================================
    
    def create_new_pallet(self):
        """Yeni sehpa olustur - ARTIK KULLANILMIYOR (3 sabit sehpa var)"""
        QMessageBox.information(
            self,
            "Bilgi",
            "3 sabit sehpa kullanılıyor:\n"
            "• Büyük L\n"
            "• Küçük L\n"
            "• Büyük A\n\n"
            "Siparişleri bu sehpalara ekleyebilirsiniz."
        )

    def close_active_sehpa(self):
        """Aktif sehpayı kapat (müşteriye gönderildi olarak işaretle)"""
        sehpa_name = self.combo_pallets.currentText()

        if not sehpa_name or sehpa_name == "-- Sehpa Yok --":
            QMessageBox.warning(self, "Uyarı", "Lütfen bir sehpa seçin.")
            return

        # Sehpada sipariş var mı kontrol et
        if self.list_pallet.count() == 0:
            QMessageBox.warning(self, "Uyarı", f"{sehpa_name} sehpası boş!")
            return

        reply = QMessageBox.question(
            self,
            "Sehpa Kapatma Onayı",
            f"'{sehpa_name}' sehpası kapatılacak ve müşteriye gönderildi olarak işaretlenecek.\n\n"
            f"Sehpada {self.list_pallet.count()} sipariş var.\n\n"
            f"Devam etmek istiyor musunuz?",
            QMessageBox.Yes | QMessageBox.No
        )

        if reply == QMessageBox.Yes and db:
            try:
                db.close_sehpa(sehpa_name)
                self.status_label.setText(f"✅ '{sehpa_name}' sehpası kapatıldı ve müşteriye gönderildi")
                self.refresh_data()
            except Exception as e:
                QMessageBox.critical(self, "Hata", f"Sehpa kapatılamadı:\n{str(e)}")

    def add_to_pallet(self):
        """KISMI SEVKİYAT: Secili siparisi sehpaya ekle"""
        pallet_id = self.combo_pallets.currentData()

        if not pallet_id:
            QMessageBox.warning(self, "Uyari", "Lutfen once bir sehpa secin.")
            return

        selected = self.table_orders.selectedItems()
        if not selected:
            QMessageBox.warning(self, "Uyari", "Lutfen bir siparis secin.")
            return

        row = selected[0].row()
        order_id = self.table_orders.item(row, 0).data(Qt.UserRole)
        order_code = self.table_orders.item(row, 0).text()
        customer = self.table_orders.item(row, 1).text()

        # Sehpa adını al
        sehpa_text = self.combo_pallets.currentText()
        # "Büyük L (2 sipariş)" formatından sadece "Büyük L" kısmını al
        sehpa_name = sehpa_text.split(' (')[0] if '(' in sehpa_text else sehpa_text

        # Hazır adedi al
        order_data = None
        for o in self.ready_orders:
            if o.get('id') == order_id:
                order_data = o
                break

        if not order_data:
            QMessageBox.warning(self, "Hata", "Sipariş bilgisi bulunamadı!")
            return

        ready_qty = order_data.get('ready_quantity', 0)
        total_qty = max((s.get('total', 0) for s in order_data.get('status_map', {}).values()), default=0)

        if ready_qty <= 0:
            QMessageBox.warning(self, "Uyarı", "Sevke hazır adet yok!")
            return

        # Kaç adet sevk edilecek?
        quantity, ok = QInputDialog.getInt(
            self,
            "Sevk Miktarı",
            f"Sipariş: {order_code}\n"
            f"Müşteri: {customer}\n"
            f"Sehpa: {sehpa_name}\n"
            f"Hazır Adet: {ready_qty}\n"
            f"Toplam Adet: {total_qty}\n\n"
            f"Kaç adet sehpaya eklenecek?",
            ready_qty,  # Varsayılan: hepsi
            1,  # Minimum
            ready_qty  # Maksimum
        )

        if not ok or quantity <= 0:
            return

        if db:
            try:
                # KISMI SEVKİYAT fonksiyonunu kullan
                db.ship_partial_order(order_id, quantity, sehpa_name)
                self.status_label.setText(f"✅ '{order_code}' - {quantity} adet '{sehpa_name}' sehpasına eklendi")
                self.refresh_data()
            except Exception as e:
                QMessageBox.critical(self, "Hata", f"Eklenemedi:\n{str(e)}")
    
    def remove_from_pallet(self):
        """Secili siparisi sehpadan cikar"""
        selected = self.list_pallet.currentItem()
        if not selected:
            QMessageBox.warning(self, "Uyari", "Lutfen cikarilacak siparisi secin.")
            return
        
        order_code = selected.data(Qt.UserRole)
        
        if db:
            try:
                with db.get_connection() as conn:
                    conn.execute(
                        "UPDATE orders SET pallet_id = NULL WHERE order_code = ?",
                        (order_code,)
                    )
                self.status_label.setText(f"'{order_code}' sehpadan cikarildi")
                self.refresh_data()
            except Exception as e:
                QMessageBox.critical(self, "Hata", f"Cikarilmadi:\n{str(e)}")
    
    def ship_pallet(self):
        """Sehpayi sevk et"""
        pallet_id = self.combo_pallets.currentData()
        
        if not pallet_id:
            QMessageBox.warning(self, "Uyari", "Lutfen bir sehpa secin.")
            return
        
        pallet_name = self.combo_pallets.currentText()
        
        # Sehpada siparis var mi?
        if self.list_pallet.count() == 0:
            QMessageBox.warning(self, "Uyari", "Sehpa bos! Once siparis ekleyin.")
            return
        
        reply = QMessageBox.question(
            self, "Sevkiyat Onayi",
            f"'{pallet_name}' sehpasini sevk etmek istediginizden emin misiniz?\n\n"
            f"Icerik: {self.lbl_pallet_summary.text()}\n\n"
            "Bu islem geri alinamaz.",
            QMessageBox.Yes | QMessageBox.No
        )
        
        if reply == QMessageBox.Yes and db:
            try:
                db.ship_pallet(pallet_id)
                self.status_label.setText(f"'{pallet_name}' sevk edildi")
                self.refresh_data()
            except Exception as e:
                QMessageBox.critical(self, "Hata", f"Sevk edilemedi:\n{str(e)}")
    
    def quick_ship_order(self):
        """KISMI SEVKİYAT: Seçili siparişi sehpaya ekle"""
        selected = self.table_orders.selectedItems()
        if not selected:
            QMessageBox.warning(self, "Uyari", "Lutfen bir siparis secin.")
            return

        row = selected[0].row()
        order_id = self.table_orders.item(row, 0).data(Qt.UserRole)
        order_code = self.table_orders.item(row, 0).text()
        customer = self.table_orders.item(row, 1).text()

        # Hazır adedi al
        order_data = None
        for o in self.ready_orders:
            if o.get('id') == order_id:
                order_data = o
                break

        if not order_data:
            QMessageBox.warning(self, "Hata", "Sipariş bilgisi bulunamadı!")
            return

        ready_qty = order_data.get('ready_quantity', 0)
        total_qty = max((s.get('total', 0) for s in order_data.get('status_map', {}).values()), default=0)

        if ready_qty <= 0:
            QMessageBox.warning(self, "Uyarı", "Sevke hazır adet yok!")
            return

        # 1. Kaç adet sevk edilecek?
        quantity, ok = QInputDialog.getInt(
            self,
            "Sevk Miktarı",
            f"Sipariş: {order_code}\n"
            f"Müşteri: {customer}\n"
            f"Hazır Adet: {ready_qty}\n"
            f"Toplam Adet: {total_qty}\n\n"
            f"Kaç adet sevk edilecek?",
            ready_qty,  # Varsayılan: hepsi
            1,  # Minimum
            ready_qty  # Maksimum
        )

        if not ok or quantity <= 0:
            return

        # 2. Hangi sehpaya?
        sehpa_name, ok2 = QInputDialog.getItem(
            self,
            "Sehpa Seç",
            f"{quantity} adet hangi sehpaya yüklenecek?",
            ["Büyük L", "Küçük L", "Büyük A"],
            0,
            False
        )

        if not ok2 or not sehpa_name:
            return

        # DEBUG: Değerleri kontrol et
        print(f"🔍 DEBUG Sevkiyat:")
        print(f"   ready_qty: {ready_qty}")
        print(f"   total_qty: {total_qty}")
        print(f"   quantity (girilen): {quantity}")

        # 3. Sevkiyatı kaydet
        if db:
            try:
                db.ship_partial_order(order_id, quantity, sehpa_name)
                self.status_label.setText(f"✅ {quantity} adet (Hazır: {ready_qty}, Toplam: {total_qty}) '{sehpa_name}' sehpasına eklendi")
                self.refresh_data()
            except Exception as e:
                QMessageBox.critical(self, "Hata", f"Sevk edilemedi:\n{str(e)}")

    def filter_orders(self):
        """Siparisleri arama kutusuna gore filtrele"""
        search_text = self.search_input.text().lower()

        if not search_text:
            # Arama bossa tum siparisleri goster
            self.ready_orders = self.all_ready_orders.copy()
        else:
            # Arama varsa filtrele
            self.ready_orders = []
            for order in self.all_ready_orders:
                code = order.get('code', '').lower()
                customer = order.get('customer', '').lower()

                if search_text in code or search_text in customer:
                    self.ready_orders.append(order)

        # Tabloyu yeniden doldur
        self._populate_orders_table()

    def _populate_orders_table(self):
        """Tabloyu mevcut ready_orders listesiyle doldur"""
        self.table_orders.setRowCount(0)
        self.table_orders.setRowCount(len(self.ready_orders))

        for row, order in enumerate(self.ready_orders):
            # Siparis kodu
            code_item = QTableWidgetItem(order.get('code', '-'))
            code_item.setData(Qt.UserRole, order.get('id'))
            self.table_orders.setItem(row, 0, code_item)

            # Musteri
            self.table_orders.setItem(row, 1, QTableWidgetItem(order.get('customer', '-')))

            # Urun
            self.table_orders.setItem(row, 2, QTableWidgetItem("Cam"))

            # Adet (KISMI SEVKİYAT: Hazır / Toplam formatında)
            ready_qty = order.get('ready_quantity', 0)
            status_map = order.get('status_map', {})
            total_qty = max((s.get('total', 0) for s in status_map.values()), default=0)
            shipped_qty = order.get('shipped_quantity', 0)

            # Hazır/Toplam (Sevk edilmiş varsa göster)
            if shipped_qty > 0:
                qty_text = f"{ready_qty}/{total_qty} ({shipped_qty} sevk)"
            else:
                qty_text = f"{ready_qty}/{total_qty}"
            self.table_orders.setItem(row, 3, QTableWidgetItem(qty_text))

            # m2
            m2 = order.get('m2', 0)
            self.table_orders.setItem(row, 4, QTableWidgetItem(f"{m2:.0f}"))

            # Teslim tarihi
            delivery_str = order.get('delivery_date', '-')
            self.table_orders.setItem(row, 5, QTableWidgetItem(delivery_str))

            # Durum
            status_type = order.get('status_type', 'normal')
            days_diff = order.get('days_diff', 999)

            if status_type == 'delayed':
                status_text = f"GECIKTI ({abs(days_diff)}g)"
                status_color = Colors.CRITICAL
                bg_color = Colors.CRITICAL_BG
            elif status_type == 'today':
                status_text = "BUGUN!"
                status_color = Colors.WARNING
                bg_color = Colors.WARNING_BG
            else:
                status_text = "Hazir"
                status_color = Colors.SUCCESS
                bg_color = None

            status_item = QTableWidgetItem(status_text)
            status_item.setForeground(QColor(status_color))
            if bg_color:
                status_item.setBackground(QColor(bg_color))
            self.table_orders.setItem(row, 6, status_item)

            # Satir arka plan rengi
            if status_type == 'delayed':
                for col in range(6):
                    item = self.table_orders.item(row, col)
                    if item:
                        item.setBackground(QColor(Colors.CRITICAL_BG))
            elif status_type == 'today':
                for col in range(6):
                    item = self.table_orders.item(row, col)
                    if item:
                        item.setBackground(QColor(Colors.WARNING_BG))

    def show_history(self):
        """Gecmis sevkiyatlari goster"""
        dialog = ShippingHistoryDialog(self)
        dialog.exec()


# =============================================================================
# GEÇMİŞ SEVKİYATLAR DIALOG
# =============================================================================
class ShippingHistoryDialog(QDialog):
    """Tamamlanan sevkiyatlari gosteren dialog"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Geçmiş Sevkiyatlar")
        self.resize(1000, 600)
        self.setup_ui()
        self.load_data()

    def setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # Baslik
        header = QFrame()
        header.setFixedHeight(50)
        header.setStyleSheet(f"""
            QFrame {{
                background-color: {Colors.HEADER_BG};
                border-bottom: 1px solid {Colors.BORDER};
            }}
        """)
        header_layout = QHBoxLayout(header)
        header_layout.setContentsMargins(16, 0, 16, 0)

        lbl_title = QLabel("Geçmiş Sevkiyatlar")
        lbl_title.setStyleSheet(f"font-size: 14px; font-weight: bold; color: {Colors.TEXT};")
        header_layout.addWidget(lbl_title)

        header_layout.addStretch()

        btn_close = QPushButton("Kapat")
        btn_close.setFixedSize(80, 32)
        btn_close.setStyleSheet(f"""
            QPushButton {{
                background-color: {Colors.BG};
                border: 1px solid {Colors.BORDER};
                border-radius: 4px;
                color: {Colors.TEXT};
                font-size: 11px;
            }}
            QPushButton:hover {{
                background-color: {Colors.HEADER_BG};
            }}
        """)
        btn_close.clicked.connect(self.close)
        header_layout.addWidget(btn_close)

        layout.addWidget(header)

        # Tablo
        self.table = QTableWidget()
        self.table.setColumnCount(7)
        self.table.setHorizontalHeaderLabels([
            "Tarih", "Sehpa", "Sipariş Kodu", "Müşteri", "Adet", "m²", "Durum"
        ])

        self.table.verticalHeader().setVisible(False)
        self.table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.SingleSelection)
        self.table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.table.setAlternatingRowColors(True)
        self.table.setShowGrid(True)

        self.table.setStyleSheet(f"""
            QTableWidget {{
                background-color: {Colors.BG};
                alternate-background-color: {Colors.ROW_ALT};
                gridline-color: {Colors.GRID};
                border: none;
                font-size: 11px;
            }}
            QTableWidget::item {{
                padding: 4px 8px;
            }}
            QTableWidget::item:selected {{
                background-color: {Colors.SELECTION};
                color: {Colors.TEXT};
            }}
            QHeaderView::section {{
                background-color: {Colors.HEADER_BG};
                color: {Colors.TEXT};
                padding: 8px;
                border: none;
                border-right: 1px solid {Colors.GRID};
                border-bottom: 1px solid {Colors.BORDER};
                font-size: 11px;
                font-weight: 600;
            }}
        """)

        header = self.table.horizontalHeader()
        header.setSectionResizeMode(QHeaderView.Interactive)
        self.table.setColumnWidth(0, 130)
        self.table.setColumnWidth(1, 120)
        self.table.setColumnWidth(2, 120)
        self.table.setColumnWidth(3, 200)
        self.table.setColumnWidth(4, 80)
        self.table.setColumnWidth(5, 80)
        header.setStretchLastSection(True)

        self.table.verticalHeader().setDefaultSectionSize(28)

        layout.addWidget(self.table, 1)

        # Alt bilgi
        footer = QFrame()
        footer.setFixedHeight(40)
        footer.setStyleSheet(f"""
            QFrame {{
                background-color: {Colors.HEADER_BG};
                border-top: 1px solid {Colors.BORDER};
            }}
        """)
        footer_layout = QHBoxLayout(footer)
        footer_layout.setContentsMargins(16, 0, 16, 0)

        self.lbl_info = QLabel("Yükleniyor...")
        self.lbl_info.setStyleSheet(f"font-size: 11px; color: {Colors.TEXT_SECONDARY};")
        footer_layout.addWidget(self.lbl_info)

        footer_layout.addStretch()

        layout.addWidget(footer)

    def load_data(self):
        """Sevk edilmis siparisleri yukle"""
        if not db:
            self.lbl_info.setText("Veritabanı bağlantısı yok")
            return

        try:
            # Sevk Edildi durumundaki tum siparisleri al
            with db.get_connection() as conn:
                rows = conn.execute("""
                    SELECT
                        o.order_code,
                        o.customer_name,
                        o.quantity,
                        o.declared_total_m2,
                        o.status,
                        o.updated_at,
                        s.pallet_name,
                        s.shipped_at
                    FROM orders o
                    LEFT JOIN shipments s ON o.pallet_id = s.id
                    WHERE o.status = 'Sevk Edildi'
                    ORDER BY o.updated_at DESC
                    LIMIT 500
                """).fetchall()

            self.table.setRowCount(len(rows))

            for row_idx, row in enumerate(rows):
                # Tarih
                date_str = row['shipped_at'] or row['updated_at'] or ''
                if date_str:
                    try:
                        dt = datetime.strptime(date_str, '%Y-%m-%d %H:%M:%S')
                        date_str = dt.strftime('%d.%m.%Y %H:%M')
                    except:
                        pass
                self.table.setItem(row_idx, 0, QTableWidgetItem(date_str))

                # Sehpa
                sehpa = row['pallet_name'] or '-'
                self.table.setItem(row_idx, 1, QTableWidgetItem(sehpa))

                # Siparis kodu
                self.table.setItem(row_idx, 2, QTableWidgetItem(row['order_code']))

                # Musteri
                self.table.setItem(row_idx, 3, QTableWidgetItem(row['customer_name']))

                # Adet
                self.table.setItem(row_idx, 4, QTableWidgetItem(str(row['quantity'])))

                # m2
                m2 = row['declared_total_m2'] or 0
                self.table.setItem(row_idx, 5, QTableWidgetItem(f"{m2:.0f}"))

                # Durum
                status_item = QTableWidgetItem("✓ Sevk Edildi")
                status_item.setForeground(QColor(Colors.SUCCESS))
                self.table.setItem(row_idx, 6, status_item)

            self.lbl_info.setText(f"Toplam {len(rows)} sevkiyat kaydı")

        except Exception as e:
            self.lbl_info.setText(f"Hata: {str(e)}")
            print(f"Gecmis sevkiyat yukleme hatasi: {e}")


if __name__ == "__main__":
    app = QApplication(sys.argv)
    app.setStyle("Fusion")
    app.setFont(QFont("Segoe UI", 9))
    
    window = ShippingView()
    window.setWindowTitle("EFES ROTA X - Sevkiyat Yonetimi")
    window.resize(1200, 700)
    window.show()
    
    sys.exit(app.exec())