"""
EFES ROTA X - Dashboard'a Chatbot Entegrasyonu

Bu dosya, mevcut dashboard_view.py'ye eklenecek değişiklikleri gösterir.
Aşağıdaki adımları takip edin:

=============================================================================
ADIM 1: Import'ları ekleyin (Dosyanın başına)
=============================================================================
"""

# Mevcut import'ların altına ekleyin:
try:
    from views.chatbot_widget import ChatbotWidget
    CHATBOT_AVAILABLE = True
except ImportError:
    CHATBOT_AVAILABLE = False


"""
=============================================================================
ADIM 2: DashboardView sınıfının __init__ metoduna ekleyin
=============================================================================
setup_ui() çağrısından SONRA ekleyin:
"""

# setup_ui() çağrısından sonra:
def init_chatbot_example(self):
    """Chatbot'u başlat"""
    if CHATBOT_AVAILABLE:
        self.chatbot = ChatbotWidget(self)
        self.chatbot.show()
    else:
        self.chatbot = None


"""
=============================================================================
ADIM 3: Alternatif olarak sidebar'a chatbot butonu ekleyin
=============================================================================
_create_sidebar metodunda, menu_items listesinden sonra ekleyebilirsiniz:
"""

def add_chatbot_button_to_sidebar_example(layout):
    """Sidebar'a chatbot butonu ekle"""
    # Stretch'ten önce ekleyin
    
    # Separator
    sep = QFrame()
    sep.setFixedHeight(1)
    sep.setStyleSheet("background-color: rgba(255,255,255,0.1);")
    layout.addWidget(sep)
    
    # Chatbot butonu
    btn_chat = QPushButton("💬 Rota Asistan")
    btn_chat.setCursor(Qt.PointingHandCursor)
    btn_chat.setStyleSheet("""
        QPushButton {
            background-color: rgba(33, 115, 70, 0.3);
            color: #FFFFFF;
            text-align: left;
            padding: 10px 12px;
            font-size: 12px;
            font-weight: 500;
            border: none;
            border-radius: 4px;
        }
        QPushButton:hover {
            background-color: rgba(33, 115, 70, 0.5);
        }
    """)
    # btn_chat.clicked.connect(self._toggle_chatbot)  # Metodu tanımlamanız gerekir
    layout.addWidget(btn_chat)


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
    QPushButton, QFrame, QStackedWidget, QButtonGroup, 
    QScrollArea, QGridLayout, QProgressBar, QSizePolicy,
    QGraphicsDropShadowEffect, QListWidget, QAbstractItemView,
    QTableWidget, QTableWidgetItem, QHeaderView
)
from PySide6.QtCore import Qt, Signal, QTimer
from PySide6.QtGui import QFont, QColor

try:
    from core.db_manager import db
except ImportError:
    db = None

# Chatbot import
try:
    from views.chatbot_widget import ChatbotWidget
    CHATBOT_AVAILABLE = True
except ImportError:
    try:
        from chatbot_widget import ChatbotWidget
        CHATBOT_AVAILABLE = True
    except ImportError:
        CHATBOT_AVAILABLE = False

# View importları
try:
    from views.orders_view import OrdersView
    from views.production_view import ProductionView
    from views.planning_view import PlanningView
    from views.projects_view import ProjectsView
    from views.stock_view import StockView
    from views.report_view import ReportView
    from views.logs_view import LogsView
    from views.settings_view import SettingsView
    from views.shipping_view import ShippingView
    from views.decision_view import DecisionView
except ImportError:
    OrdersView = None
    ProductionView = None
    PlanningView = None
    ProjectsView = None
    StockView = None
    ReportView = None
    LogsView = None
    SettingsView = None
    ShippingView = None
    DecisionView = None


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
    
    SIDEBAR_BG = "#1E3A2F"
    SIDEBAR_TEXT = "#FFFFFF"
    SIDEBAR_HOVER = "#2D5A47"
    SIDEBAR_ACTIVE = "#217346"
    
    CRITICAL = "#C00000"
    CRITICAL_BG = "#FDE8E8"
    WARNING = "#C65911"
    WARNING_BG = "#FFF3E0"
    SUCCESS = "#107C41"
    SUCCESS_BG = "#E6F4EA"
    INFO = "#0066CC"
    INFO_BG = "#E3F2FD"


# =============================================================================
# METRIK KARTI
# =============================================================================
class MetricCard(QFrame):
    """Büyük metrik kartı"""
    
    def __init__(self, title, value, subtitle="", color=Colors.TEXT):
        super().__init__()
        self.color = color
        self.setup_ui(title, value, subtitle)
    
    def setup_ui(self, title, value, subtitle):
        self.setStyleSheet(f"""
            QFrame {{
                background-color: {Colors.BG};
                border: 1px solid {Colors.BORDER};
                border-radius: 6px;
            }}
        """)
        
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 14, 16, 14)
        layout.setSpacing(4)
        
        lbl_title = QLabel(title)
        lbl_title.setStyleSheet(f"font-size: 11px; color: {Colors.TEXT_MUTED}; font-weight: 500;")
        layout.addWidget(lbl_title)
        
        self.lbl_value = QLabel(str(value))
        self.lbl_value.setStyleSheet(f"font-size: 28px; font-weight: bold; color: {self.color};")
        layout.addWidget(self.lbl_value)
        
        if subtitle:
            self.lbl_subtitle = QLabel(subtitle)
            self.lbl_subtitle.setStyleSheet(f"font-size: 10px; color: {Colors.TEXT_SECONDARY};")
            layout.addWidget(self.lbl_subtitle)
        else:
            self.lbl_subtitle = None
    
    def set_value(self, value, subtitle=None):
        self.lbl_value.setText(str(value))
        if subtitle and self.lbl_subtitle:
            self.lbl_subtitle.setText(subtitle)


# =============================================================================
# UYARI KARTI
# =============================================================================
class AlertCard(QFrame):
    """Uyarı/bildirim kartı"""
    
    def __init__(self, title, color=Colors.CRITICAL):
        super().__init__()
        self.title_text = title
        self.color = color
        self.setup_ui()
    
    def setup_ui(self):
        self.setStyleSheet(f"""
            QFrame {{
                background-color: {Colors.BG};
                border: 1px solid {Colors.BORDER};
                border-radius: 8px;
            }}
        """)
        
        shadow = QGraphicsDropShadowEffect()
        shadow.setBlurRadius(15)
        shadow.setColor(QColor(0, 0, 0, 20))
        shadow.setOffset(0, 2)
        self.setGraphicsEffect(shadow)
        
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        
        # Header
        header = QFrame()
        header.setStyleSheet(f"""
            QFrame {{
                background-color: {Colors.HEADER_BG};
                border-bottom: 1px solid {Colors.BORDER};
                border-top-left-radius: 8px;
                border-top-right-radius: 8px;
            }}
        """)
        header_layout = QHBoxLayout(header)
        header_layout.setContentsMargins(15, 10, 15, 10)
        
        dot = QLabel("●")
        dot.setStyleSheet(f"color: {self.color}; font-size: 14px; border:none; background:transparent;")
        header_layout.addWidget(dot)
        
        lbl_title = QLabel(self.title_text)
        lbl_title.setStyleSheet(f"font-weight: bold; color: {Colors.TEXT}; font-size: 13px; border:none; background:transparent;")
        header_layout.addWidget(lbl_title)
        
        header_layout.addStretch()
        
        self.lbl_count = QLabel("0")
        self.lbl_count.setStyleSheet(f"""
            background-color: {self.color};
            color: white;
            font-weight: bold;
            border-radius: 10px;
            padding: 2px 8px;
            font-size: 11px;
        """)
        header_layout.addWidget(self.lbl_count)
        
        layout.addWidget(header)
        
        # Liste
        self.list_widget = QListWidget()
        self.list_widget.setFocusPolicy(Qt.NoFocus)
        self.list_widget.setStyleSheet(f"""
            QListWidget {{
                border: none;
                background: transparent;
                outline: none;
            }}
            QListWidget::item {{
                padding: 10px 15px;
                border-bottom: 1px solid {Colors.BORDER};
                color: {Colors.TEXT};
                font-size: 12px;
            }}
        """)
        layout.addWidget(self.list_widget)
    
    def set_items(self, items):
        self.list_widget.clear()
        self.lbl_count.setText(str(len(items)))
        
        if not items:
            self.list_widget.addItem("Kayıt bulunamadı.")
            return

        for item_text in items[:6]:
            self.list_widget.addItem(item_text)
            
        if len(items) > 6:
            self.list_widget.addItem(f"... ve {len(items)-6} diğer kayıt")


# =============================================================================
# KAPASITE ÇUBUĞU
# =============================================================================
class CapacityBar(QFrame):
    """İstasyon kapasite çubuğu (PERFORMANS: Güncelleme desteğiyle)"""

    def __init__(self, name, percent, status="Normal"):
        super().__init__()
        self.setup_ui(name, percent, status)

    def setup_ui(self, name, percent, status):
        self.setFixedHeight(32)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(12)

        self.lbl_name = QLabel(name)
        self.lbl_name.setFixedWidth(100)
        self.lbl_name.setStyleSheet(f"font-size: 11px; font-weight: bold; color: {Colors.TEXT};")
        layout.addWidget(self.lbl_name)

        self.bar = QProgressBar()
        self.bar.setFixedHeight(8)
        self.bar.setValue(min(percent, 100))
        self.bar.setTextVisible(False)

        if status == "Kritik" or percent > 90:
            bar_color = Colors.CRITICAL
        elif status == "Yogun" or percent > 70:
            bar_color = Colors.WARNING
        else:
            bar_color = Colors.SUCCESS

        self.bar.setStyleSheet(f"""
            QProgressBar {{
                background-color: {Colors.GRID};
                border: none;
                border-radius: 4px;
            }}
            QProgressBar::chunk {{
                background-color: {bar_color};
                border-radius: 4px;
            }}
        """)
        layout.addWidget(self.bar, 1)

        self.lbl_pct = QLabel(f"%{percent}")
        self.lbl_pct.setFixedWidth(45)
        self.lbl_pct.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        self.lbl_pct.setStyleSheet(f"font-size: 11px; font-weight: bold; color: {bar_color};")
        layout.addWidget(self.lbl_pct)

        self.lbl_status = QLabel(status)
        self.lbl_status.setFixedWidth(50)
        self.lbl_status.setStyleSheet(f"font-size: 10px; color: {Colors.TEXT_MUTED};")
        layout.addWidget(self.lbl_status)

    def set_value(self, percent, status="Normal"):
        """PERFORMANS: Widget'ı yeniden oluşturmadan güncelle"""
        self.bar.setValue(min(percent, 100))
        self.lbl_pct.setText(f"%{percent}")
        self.lbl_status.setText(status)

        # Renk güncelle
        if status == "Kritik" or percent > 90:
            bar_color = Colors.CRITICAL
        elif status == "Yogun" or percent > 70:
            bar_color = Colors.WARNING
        else:
            bar_color = Colors.SUCCESS

        self.bar.setStyleSheet(f"""
            QProgressBar {{
                background-color: {Colors.GRID};
                border: none;
                border-radius: 4px;
            }}
            QProgressBar::chunk {{
                background-color: {bar_color};
                border-radius: 4px;
            }}
        """)
        self.lbl_pct.setStyleSheet(f"font-size: 11px; font-weight: bold; color: {bar_color};")


# =============================================================================
# ANA DASHBOARD
# =============================================================================
class DashboardView(QWidget):
    logout_signal = Signal()
    
    def __init__(self, user_data):
        super().__init__()
        self.user = user_data
        self.setup_ui()
        
        # Canlı yenileme (30 saniye - Performans optimizasyonu)
        # Cam fabrikası için 5 saniye çok sık, 30 saniye yeterli ✅
        self.timer = QTimer(self)
        self.timer.timeout.connect(self.update_dashboard)
        self.timer.start(30000)  # 5000ms -> 30000ms (6x daha az sorgu)

        # 🚀 RefreshManager kaydı
        try:
            from core.refresh_manager import refresh_manager
            refresh_manager.register_view(
                data_key='orders',
                callback=self.update_dashboard,
                dependencies=['production_logs', 'stocks']
            )
        except:
            pass
        
        # ============================================
        # CHATBOT ENTEGRASYONU
        # ============================================
        if CHATBOT_AVAILABLE:
            self.chatbot = ChatbotWidget(self)
            self.chatbot.show()
        else:
            self.chatbot = None
    
    def setup_ui(self):
        self.setStyleSheet(f"background-color: {Colors.HEADER_BG};")
        
        main_layout = QHBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)
        
        # SIDEBAR
        sidebar = self._create_sidebar()
        main_layout.addWidget(sidebar)
        
        # İÇERİK ALANI
        content = QWidget()
        content.setStyleSheet(f"background-color: {Colors.HEADER_BG};")
        
        self.content_layout = QVBoxLayout(content)
        self.content_layout.setContentsMargins(0, 0, 0, 0)
        
        self.stack = QStackedWidget()
        self.content_layout.addWidget(self.stack)
        
        self._load_pages()
        
        main_layout.addWidget(content, 1)
        
        self.menu_group.button(0).click()
    
    def _create_sidebar(self):
        """Sol menü"""
        sidebar = QFrame()
        sidebar.setFixedWidth(220)
        sidebar.setStyleSheet(f"QFrame {{ background-color: {Colors.SIDEBAR_BG}; }}")
        
        layout = QVBoxLayout(sidebar)
        layout.setContentsMargins(16, 24, 16, 16)
        layout.setSpacing(4)
        
        # Logo
        lbl_logo = QLabel("REFLEKS 360 ROTA")
        lbl_logo.setStyleSheet(f"font-size: 18px; font-weight: bold; color: {Colors.SIDEBAR_TEXT}; padding-bottom: 4px;")
        layout.addWidget(lbl_logo)
        
        # Kullanıcı
        lbl_user = QLabel(self.user.get('full_name', 'Admin').upper())
        lbl_user.setStyleSheet(f"font-size: 10px; color: {Colors.TEXT_MUTED}; letter-spacing: 1px; padding-bottom: 20px;")
        layout.addWidget(lbl_user)
        
        # Menü grubu
        self.menu_group = QButtonGroup(self)
        self.menu_group.setExclusive(True)
        
        menu_items = [
            ("Genel Bakis", 0),
            ("Siparisler", 1),
            ("Projeler", 2),
            ("Uretim Takip", 3),
            ("Is Yuku (Gantt)", 4),
            ("Stok Depo", 5),
            ("Sevkiyat", 6),
            ("Raporlama", 7),
            ("Islem Gecmisi", 8),
            ("Ayarlar", 9),
            ("Karar Destek", 10)
        ]
        
        for text, idx in menu_items:
            btn = QPushButton(text)
            btn.setCheckable(True)
            btn.setCursor(Qt.PointingHandCursor)
            btn.setStyleSheet(f"""
                QPushButton {{
                    background-color: transparent;
                    color: {Colors.SIDEBAR_TEXT};
                    text-align: left;
                    padding: 10px 12px;
                    font-size: 12px;
                    font-weight: 500;
                    border: none;
                    border-radius: 4px;
                }}
                QPushButton:hover {{ background-color: {Colors.SIDEBAR_HOVER}; }}
                QPushButton:checked {{ background-color: {Colors.SIDEBAR_ACTIVE}; font-weight: bold; }}
            """)
            btn.clicked.connect(lambda checked, i=idx: self._load_page_on_demand(i))
            self.menu_group.addButton(btn, idx)
            layout.addWidget(btn)
        
        # ============================================
        # CHATBOT BUTONU (Sidebar'da)
        # ============================================
        layout.addSpacing(10)
        
        sep = QFrame()
        sep.setFixedHeight(1)
        sep.setStyleSheet("background-color: rgba(255,255,255,0.15);")
        layout.addWidget(sep)
        
        layout.addSpacing(10)
        
        btn_chatbot = QPushButton("💬 Rota Asistan")
        btn_chatbot.setCursor(Qt.PointingHandCursor)
        btn_chatbot.setStyleSheet(f"""
            QPushButton {{
                background-color: rgba(33, 115, 70, 0.3);
                color: {Colors.SIDEBAR_TEXT};
                text-align: left;
                padding: 10px 12px;
                font-size: 12px;
                font-weight: 500;
                border: 1px solid rgba(255,255,255,0.2);
                border-radius: 4px;
            }}
            QPushButton:hover {{
                background-color: rgba(33, 115, 70, 0.5);
                border-color: rgba(255,255,255,0.3);
            }}
        """)
        btn_chatbot.clicked.connect(self._toggle_chatbot)
        layout.addWidget(btn_chatbot)
        
        layout.addStretch()
        
        # Çıkış butonu
        btn_logout = QPushButton("Oturumu Kapat")
        btn_logout.setCursor(Qt.PointingHandCursor)
        btn_logout.setStyleSheet(f"""
            QPushButton {{
                background-color: transparent;
                color: {Colors.TEXT_MUTED};
                text-align: left;
                padding: 10px 12px;
                font-size: 11px;
                border: none;
                border-radius: 4px;
            }}
            QPushButton:hover {{
                color: {Colors.CRITICAL};
                background-color: rgba(192, 0, 0, 0.1);
            }}
        """)
        btn_logout.clicked.connect(self.logout_signal.emit)
        layout.addWidget(btn_logout)
        
        return sidebar
    
    def _toggle_chatbot(self):
        """Chatbot panelini aç/kapat"""
        if hasattr(self, 'chatbot') and self.chatbot:
            self.chatbot.toggle_chat()
    
    def _load_pages(self):
        """Sayfaları LAZY LOADING ile yükle - Performans optimizasyonu"""
        # SADECE Dashboard'u başlangıçta yükle, diğerleri ihtiyaç duyulduğunda yüklenecek

        # Sayfa cache'i - None = henüz yüklenmedi
        self.page_cache = {}

        # 0. Dashboard - Hemen yükle
        self.dashboard_page = QWidget()
        self._setup_dashboard_page()
        self.stack.addWidget(self.dashboard_page)
        self.page_cache[0] = self.dashboard_page

        # 1-11. Diğer sayfalar - Placeholder'lar ekle, gerçek sayfa tıklanınca yüklenecek
        page_names = [
            "Siparisler", "Projeler", "Uretim Takip", "Is Yuku", "Stok Depo",
            "Sevkiyat", "Raporlama", "Islem Gecmisi", "Ayarlar",
            "Karar Destek"
        ]

        for i, name in enumerate(page_names, start=1):
            placeholder = self._placeholder_loading(name)
            self.stack.addWidget(placeholder)
            self.page_cache[i] = None  # Henüz yüklenmedi         
        
    
    def _load_page_on_demand(self, page_index):
        """Sayfa ihtiyaç duyulduğunda yükle (Lazy Loading)"""
        # Eğer sayfa daha önce yüklenmişse direkt göster
        if self.page_cache.get(page_index) is not None:
            self.stack.setCurrentIndex(page_index)
            return

        # Sayfa yüklenmediyse şimdi yükle
        page_map = {
            1: (OrdersView, "Siparisler"),
            2: (ProjectsView, "Projeler"),
            3: (ProductionView, "Uretim Takip"),
            4: (PlanningView, "Is Yuku"),
            5: (StockView, "Stok Depo"),
            6: (ShippingView, "Sevkiyat"),
            7: (ReportView, "Raporlama"),
            8: (LogsView, "Islem Gecmisi"),
            9: (SettingsView, "Ayarlar"),
            10: (DecisionView, "Karar Destek")
        }

        if page_index in page_map:
            view_class, name = page_map[page_index]
            try:
                # Yeni view oluştur
                new_view = view_class() if view_class else self._placeholder(name)

                # Eski placeholder'ı değiştir
                old_widget = self.stack.widget(page_index)
                self.stack.removeWidget(old_widget)
                old_widget.deleteLater()

                # Yeni view'i ekle
                self.stack.insertWidget(page_index, new_view)
                self.page_cache[page_index] = new_view

            except Exception as e:
                # Hata durumunda placeholder göster
                error_widget = self._placeholder(f"{name} (Hata: {str(e)})")
                old_widget = self.stack.widget(page_index)
                self.stack.removeWidget(old_widget)
                old_widget.deleteLater()
                self.stack.insertWidget(page_index, error_widget)

        # Sayfayı göster
        self.stack.setCurrentIndex(page_index)

    def _placeholder_loading(self, name):
        """Yükleniyor placeholder'ı"""
        w = QWidget()
        layout = QVBoxLayout(w)
        layout.setAlignment(Qt.AlignCenter)

        lbl = QLabel(f"⏳ {name} yükleniyor...")
        lbl.setStyleSheet(f"font-size: 16px; color: {Colors.TEXT_MUTED};")
        lbl.setAlignment(Qt.AlignCenter)
        layout.addWidget(lbl)

        return w

    def _placeholder(self, name):
        """Hata placeholder'ı"""
        w = QWidget()
        layout = QVBoxLayout(w)
        layout.setAlignment(Qt.AlignCenter)

        lbl = QLabel(f"{name} modulu yuklenemedi")
        lbl.setStyleSheet(f"font-size: 16px; color: {Colors.TEXT_MUTED};")
        lbl.setAlignment(Qt.AlignCenter)
        layout.addWidget(lbl)

        return w

    def _setup_dashboard_page(self):
        """Dashboard sayfasını oluştur"""
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.NoFrame)
        scroll.setStyleSheet(f"background-color: {Colors.HEADER_BG};")
        
        content = QWidget()
        content.setStyleSheet(f"background-color: {Colors.HEADER_BG};")
        layout = QVBoxLayout(content)
        layout.setContentsMargins(24, 20, 24, 20)
        layout.setSpacing(20)
        
        # HEADER
        header = QHBoxLayout()
        
        title_layout = QVBoxLayout()
        title_layout.setSpacing(4)
        
        lbl_title = QLabel("Genel Bakis")
        lbl_title.setStyleSheet(f"font-size: 22px; font-weight: bold; color: {Colors.TEXT};")
        title_layout.addWidget(lbl_title)
        
        self.lbl_time = QLabel(now_turkey().strftime("Son guncelleme: %H:%M:%S"))
        self.lbl_time.setStyleSheet(f"font-size: 11px; color: {Colors.TEXT_MUTED};")
        title_layout.addWidget(self.lbl_time)
        
        header.addLayout(title_layout)
        header.addStretch()
        
        btn_refresh = QPushButton("Yenile")
        btn_refresh.setFixedHeight(32)
        btn_refresh.setCursor(Qt.PointingHandCursor)
        btn_refresh.clicked.connect(self.update_dashboard)
        btn_refresh.setStyleSheet(f"""
            QPushButton {{
                background-color: {Colors.ACCENT};
                color: white;
                border: none;
                border-radius: 4px;
                padding: 0 16px;
                font-size: 11px;
                font-weight: bold;
            }}
            QPushButton:hover {{ background-color: #1D6640; }}
        """)
        header.addWidget(btn_refresh)
        
        layout.addLayout(header)
        
        # METRİKLER
        metrics_layout = QHBoxLayout()
        metrics_layout.setSpacing(16)

        self.metric_projects = MetricCard("Aktif Projeler", "0", "Devam eden projeler", "#6B46C1")
        self.metric_active = MetricCard("Aktif Siparisler", "0", "Beklemede + Uretimde", Colors.INFO)
        self.metric_today_done = MetricCard("Bugun Tamamlanan", "0", "Adet", Colors.SUCCESS)
        self.metric_urgent = MetricCard("Acil / Kritik", "0", "Oncelikli isler", Colors.WARNING)
        self.metric_fire = MetricCard("Fire / Hata", "0", "Toplam", Colors.CRITICAL)

        metrics_layout.addWidget(self.metric_projects, 1)
        metrics_layout.addWidget(self.metric_active, 1)
        metrics_layout.addWidget(self.metric_today_done, 1)
        metrics_layout.addWidget(self.metric_urgent, 1)
        metrics_layout.addWidget(self.metric_fire, 1)
        
        layout.addLayout(metrics_layout)
        
        # UYARILAR
        alerts_layout = QHBoxLayout()
        alerts_layout.setSpacing(16)
        
        self.alert_overdue = AlertCard("Geciken Siparişler", Colors.CRITICAL)
        alerts_layout.addWidget(self.alert_overdue, 1)
        
        self.alert_today = AlertCard("Bugün Teslim", Colors.WARNING)
        alerts_layout.addWidget(self.alert_today, 1)
        
        layout.addLayout(alerts_layout)
        
        # DARBOĞAZ ANALİZİ
        bottom_layout = QHBoxLayout()
        bottom_layout.setSpacing(16)
        
        bottleneck_frame = QFrame()
        bottleneck_frame.setStyleSheet(f"""
            QFrame {{
                background-color: {Colors.BG};
                border: 1px solid {Colors.BORDER};
                border-radius: 6px;
            }}
        """)
        bottleneck_layout = QVBoxLayout(bottleneck_frame)
        bottleneck_layout.setContentsMargins(16, 14, 16, 14)
        bottleneck_layout.setSpacing(12)
        
        bottleneck_header = QHBoxLayout()
        lbl_bottleneck = QLabel("Istasyon Doluluk Orani")
        lbl_bottleneck.setStyleSheet(f"font-size: 13px; font-weight: bold; color: {Colors.TEXT};")
        bottleneck_header.addWidget(lbl_bottleneck)
        bottleneck_header.addStretch()
        
        legend = QHBoxLayout()
        legend.setSpacing(12)
        for color, text in [(Colors.CRITICAL, "Kritik"), (Colors.WARNING, "Yogun"), (Colors.SUCCESS, "Normal")]:
            dot = QLabel("●")
            dot.setStyleSheet(f"font-size: 10px; color: {color};")
            legend.addWidget(dot)
            lbl = QLabel(text)
            lbl.setStyleSheet(f"font-size: 10px; color: {Colors.TEXT_MUTED};")
            legend.addWidget(lbl)
        bottleneck_header.addLayout(legend)
        
        bottleneck_layout.addLayout(bottleneck_header)
        
        self.capacity_layout = QVBoxLayout()
        self.capacity_layout.setSpacing(8)
        bottleneck_layout.addLayout(self.capacity_layout)
        
        bottom_layout.addWidget(bottleneck_frame, 1)

        layout.addLayout(bottom_layout)
        
        layout.addStretch()
        
        scroll.setWidget(content)
        
        page_layout = QVBoxLayout(self.dashboard_page)
        page_layout.setContentsMargins(0, 0, 0, 0)
        page_layout.addWidget(scroll)
        
        self.update_dashboard()
    
    def update_dashboard(self):
        """Dashboard verilerini güncelle (Mevcut Arayüzle Uyumlu)"""
        if not db: return
        
        try:
            self.lbl_time.setText(f"Son Güncelleme: {now_turkey().strftime('%H:%M:%S')}")
            
            # 1. İstatistikleri Çek
            stats = db.get_dashboard_stats()
            
            # 2. Metrik Kartlarını Güncelle (Sadece arayüzde olanları)
            # Aktif Projeler (Hata korumalı)
            try:
                if hasattr(db, 'get_active_projects_count'):
                    proj_count = db.get_active_projects_count()
                    self.metric_projects.set_value(proj_count)
                else:
                    self.metric_projects.set_value("0")
            except:
                self.metric_projects.set_value("0")

            self.metric_active.set_value(stats.get('active', 0))
            self.metric_urgent.set_value(stats.get('urgent', 0))
            self.metric_fire.set_value(stats.get('fire', 0))
            
            # Bugün Tamamlanan (Loglardan tarihli çekim)
            try:
                today_completed = db.get_today_completed_count()
            except AttributeError:
                today_completed = 0
            self.metric_today_done.set_value(today_completed)
            
            # 3. Geciken ve Bugün Teslim Edilecekler (Sadece aktif siparişleri tara)
            active_orders = db.get_orders_by_status(['Beklemede', 'Üretimde'])
            today = now_turkey().date()
            overdue_list = []
            today_list = []
            
            for o in active_orders:
                if o.get('delivery_date'):
                    try:
                        # Tarih formatını güvenli çevir
                        d_str = o.get('delivery_date')
                        if isinstance(d_str, str):
                            d_date = datetime.strptime(d_str, '%Y-%m-%d').date()
                        else:
                            d_date = d_str
                            
                        if d_date < today: 
                            days = (today - d_date).days
                            overdue_list.append(f"{o['order_code']} - {o['customer_name']} ({days} gün)")
                        elif d_date == today: 
                            today_list.append(f"{o['order_code']} - {o['customer_name']}")
                    except: pass
            
            self.alert_overdue.set_items(overdue_list)
            self.alert_today.set_items(today_list)
            
            # 4. Kapasite Grafikleri (PERFORMANS: Widget'ları yeniden oluşturma yerine güncelle)
            station_loads = db.get_station_loads()

            # İlk yüklemede veya istasyon sayısı değiştiyse widget'ları yeniden oluştur
            if not hasattr(self, '_capacity_bars') or len(self._capacity_bars) != len(station_loads[:12]):
                # Cache temizle
                while self.capacity_layout.count():
                    child = self.capacity_layout.takeAt(0)
                    if child.widget(): child.widget().deleteLater()

                # Yeni widget'ları oluştur ve cache'le
                self._capacity_bars = []
                for st in station_loads[:12]:
                    bar = CapacityBar(st['name'], st['percent'], st['status'])
                    self.capacity_layout.addWidget(bar)
                    self._capacity_bars.append(bar)
            else:
                # Mevcut widget'ları güncelle (çok daha hızlı!)
                for i, st in enumerate(station_loads[:12]):
                    if i < len(self._capacity_bars):
                        bar = self._capacity_bars[i]
                        bar.set_value(st['percent'], st['status'])
                
        except Exception as e: 
            print(f"Dashboard güncelleme hatası: {e}")
    
    def resizeEvent(self, event):
        """Pencere boyutu değiştiğinde chatbot konumunu güncelle"""
        super().resizeEvent(event)
        if hasattr(self, 'chatbot') and self.chatbot:
            self.chatbot._update_positions()