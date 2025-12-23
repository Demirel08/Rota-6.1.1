"""
EFES ROTA X - Chatbot Widget v2.1
Sürüklenebilir Chat Paneli - Düzeltilmiş

Düzeltmeler:
- Sürükleme mantığı düzeltildi
- Boyutlandırma düzeltildi  
- Parent içinde düzgün çalışıyor
"""

import re
import random
from datetime import datetime
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel,
    QPushButton, QFrame, QScrollArea, QLineEdit,
    QGraphicsDropShadowEffect, QSizePolicy
)
from PySide6.QtCore import Qt, Signal, QPoint, QSize, QTimer, QEvent, QRect, QThread, QPropertyAnimation, QEasingCurve
from PySide6.QtGui import QColor, QCursor, QMouseEvent

try:
    from utils.timezone_helper import now_turkey
except ImportError:
    # Fallback: timezone_helper bulunamazsa normal datetime kullan
    now_turkey = lambda: datetime.now()

# Chatbot motorunu import et
try:
    from core.chatbot import bot
except ImportError:
    try:
        from chatbot import bot
    except ImportError:
        bot = None


# =============================================================================
# THREADING - ANA THREAD'İ DONDURMAMAK İÇİN
# =============================================================================
class BotWorker(QThread):
    """Arka planda bot işlemlerini çalıştıran worker thread"""

    # Sinyal: İşlem tamamlandığında response'u gönder
    response_ready = Signal(dict)

    def __init__(self, message, parent=None):
        super().__init__(parent)
        self.message = message

    def run(self):
        """Arka planda çalışacak işlem"""
        try:
            if bot:
                response = bot.process_message(self.message)
            else:
                response = {
                    'text': '⚠️ Asistan şu an kullanılamıyor.',
                    'buttons': []
                }

            # Sinyal ile ana thread'e gönder
            self.response_ready.emit(response)
        except Exception as e:
            # Hata durumunda kullanıcıya bilgi ver
            error_response = {
                'text': f'⚠️ Bir hata oluştu: {str(e)}',
                'buttons': []
            }
            self.response_ready.emit(error_response)


# =============================================================================
# RENKLER
# =============================================================================
class ChatColors:
    PRIMARY = "#217346"
    PRIMARY_DARK = "#1D6640"
    PRIMARY_LIGHT = "#2D8B57"
    
    PANEL_BG = "#FFFFFF"
    HEADER_BG = "#217346"
    HEADER_TEXT = "#FFFFFF"
    
    BOT_BG = "#F0F4F0"
    BOT_TEXT = "#1A1A1A"
    USER_BG = "#217346"
    USER_TEXT = "#FFFFFF"
    
    QUICK_BTN_BG = "#E8F5E9"
    QUICK_BTN_TEXT = "#217346"
    QUICK_BTN_BORDER = "#A5D6A7"
    QUICK_BTN_HOVER = "#C8E6C9"
    
    BORDER = "#E0E0E0"
    INPUT_BG = "#F5F5F5"
    INPUT_FOCUS = "#E8F5E9"


# =============================================================================
# TYPING INDICATOR
# =============================================================================
class TypingIndicator(QFrame):
    """Bot yazıyor göstergesi"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setup_ui()

        # Animasyon timer
        self.animation_timer = QTimer()
        self.animation_timer.timeout.connect(self._animate)
        self.dot_count = 0

    def setup_ui(self):
        self.setStyleSheet(f"""
            QFrame {{
                background-color: {ChatColors.BOT_BG};
                border-radius: 12px;
            }}
        """)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(12, 10, 12, 10)
        layout.setSpacing(4)

        self.label = QLabel("yazıyor")
        self.label.setStyleSheet(f"""
            QLabel {{
                color: {ChatColors.BOT_TEXT};
                font-size: 13px;
                font-style: italic;
                background: transparent;
            }}
        """)
        layout.addWidget(self.label)
        layout.addStretch()

    def start(self):
        """Animasyonu başlat"""
        self.animation_timer.start(400)

    def stop(self):
        """Animasyonu durdur"""
        self.animation_timer.stop()

    def _animate(self):
        """Nokta animasyonu"""
        self.dot_count = (self.dot_count + 1) % 4
        dots = "." * self.dot_count
        self.label.setText(f"yazıyor{dots}")


# =============================================================================
# MESAJ BALONU
# =============================================================================
class MessageBubble(QFrame):
    """Tek bir mesaj balonu"""

    button_clicked = Signal(str)

    def __init__(self, text, is_bot=True, buttons=None, parent=None):
        super().__init__(parent)
        self.is_bot = is_bot
        self.buttons = buttons or []
        self.setup_ui(text)
    
    def setup_ui(self, text):
        if self.is_bot:
            bg_color = ChatColors.BOT_BG
            text_color = ChatColors.BOT_TEXT
            border = f"border-left: 3px solid {ChatColors.PRIMARY};"
        else:
            bg_color = ChatColors.USER_BG
            text_color = ChatColors.USER_TEXT
            border = ""

        self.setStyleSheet(f"""
            QFrame {{
                background-color: {bg_color};
                border-radius: 14px;
                {border}
            }}
        """)
        
        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 10, 12, 8)
        layout.setSpacing(8)
        
        # Mesaj metni
        lbl_text = QLabel()
        lbl_text.setWordWrap(True)
        lbl_text.setTextFormat(Qt.RichText)
        
        formatted = self._format_text(text)
        lbl_text.setText(formatted)
        
        lbl_text.setStyleSheet(f"""
            QLabel {{
                color: {text_color};
                font-size: 13px;
                line-height: 1.5;
                background: transparent;
            }}
        """)
        layout.addWidget(lbl_text)
        
        # Hızlı butonlar
        if self.is_bot and self.buttons:
            btn_container = QWidget()
            btn_layout = QHBoxLayout(btn_container)
            btn_layout.setContentsMargins(0, 4, 0, 0)
            btn_layout.setSpacing(6)
            
            for btn_text in self.buttons[:3]:
                btn = QPushButton(btn_text)
                btn.setCursor(Qt.PointingHandCursor)
                btn.setStyleSheet(f"""
                    QPushButton {{
                        background-color: {ChatColors.QUICK_BTN_BG};
                        color: {ChatColors.QUICK_BTN_TEXT};
                        border: 1px solid {ChatColors.QUICK_BTN_BORDER};
                        border-radius: 12px;
                        padding: 5px 10px;
                        font-size: 11px;
                        font-weight: 500;
                    }}
                    QPushButton:hover {{
                        background-color: {ChatColors.QUICK_BTN_HOVER};
                    }}
                """)
                btn.clicked.connect(lambda checked, t=btn_text: self.button_clicked.emit(t))
                btn_layout.addWidget(btn)
            
            btn_layout.addStretch()
            layout.addWidget(btn_container)
        
        # Zaman (Türkiye saati)
        time_text = now_turkey().strftime("%H:%M")
        lbl_time = QLabel(time_text)
        time_color = '#888888' if self.is_bot else 'rgba(255,255,255,0.7)'
        lbl_time.setStyleSheet(f"color: {time_color}; font-size: 10px; background: transparent;")
        lbl_time.setAlignment(Qt.AlignRight if not self.is_bot else Qt.AlignLeft)
        layout.addWidget(lbl_time)
    
    def _format_text(self, text):
        """Basit markdown formatlama"""
        # Satır sonları
        text = text.replace('\n', '<br>')

        # **Bold** → <b>Bold</b>
        text = re.sub(r'\*\*(.+?)\*\*', r'<b>\1</b>', text)

        # *Italic* → <i>Italic</i>
        text = re.sub(r'\*(.+?)\*', r'<i>\1</i>', text)

        # `code` → <code>code</code>
        text = re.sub(r'`(.+?)`', r'<code style="background:#f0f0f0;padding:2px 4px;border-radius:3px;">\1</code>', text)

        return text


# =============================================================================
# CHAT PANELİ - SÜRÜKLENEBİLİR
# =============================================================================
class ChatPanel(QFrame):
    """Ana chat paneli - sürüklenebilir ve boyutlandırılabilir"""
    
    close_requested = Signal()
    
    # Boyutlandırma kenar kalınlığı
    RESIZE_MARGIN = 8
    
    def __init__(self, parent=None):
        super().__init__(parent)

        # Sürükleme değişkenleri
        self._drag_active = False
        self._drag_start_pos = None
        self._drag_start_geometry = None

        # Boyutlandırma değişkenleri
        self._resize_active = False
        self._resize_edge = None

        # Typing indicator
        self.typing_indicator = None

        # Worker thread (veritabanı işlemleri için)
        self.worker = None

        self.setMouseTracking(True)
        self.setup_ui()

        # Başlangıç mesajı
        if bot:
            greeting = bot.get_greeting()
            self.add_bot_message(greeting['text'], greeting.get('buttons'))
    
    def setup_ui(self):
        self.setMinimumSize(300, 350)
        self.resize(380, 480)
        
        self.setStyleSheet(f"""
            QFrame#chatPanel {{
                background-color: {ChatColors.PANEL_BG};
                border: 1px solid {ChatColors.BORDER};
                border-radius: 12px;
            }}
        """)
        self.setObjectName("chatPanel")
        
        # Gölge
        shadow = QGraphicsDropShadowEffect()
        shadow.setBlurRadius(25)
        shadow.setColor(QColor(0, 0, 0, 50))
        shadow.setOffset(0, 4)
        self.setGraphicsEffect(shadow)
        
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        
        # Header (sürükleme alanı)
        self.header = self._create_header()
        layout.addWidget(self.header)
        
        # Mesaj Alanı
        self.scroll_area = QScrollArea()
        self.scroll_area.setWidgetResizable(True)
        self.scroll_area.setFrameShape(QFrame.NoFrame)
        self.scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.scroll_area.setStyleSheet("""
            QScrollArea { background: transparent; border: none; }
            QScrollBar:vertical {
                background: #F0F0F0; width: 6px; border-radius: 3px; margin: 2px;
            }
            QScrollBar::handle:vertical {
                background: #C0C0C0; border-radius: 3px; min-height: 30px;
            }
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical { height: 0; }
        """)
        
        self.message_container = QWidget()
        self.message_container.setStyleSheet("background: transparent;")
        self.message_layout = QVBoxLayout(self.message_container)
        self.message_layout.setContentsMargins(10, 10, 10, 10)
        self.message_layout.setSpacing(10)
        self.message_layout.addStretch()
        
        self.scroll_area.setWidget(self.message_container)
        layout.addWidget(self.scroll_area, 1)
        
        # Input Alanı
        input_frame = self._create_input()
        layout.addWidget(input_frame)
    
    def _create_header(self):
        """Sürüklenebilir başlık"""
        header = QFrame()
        header.setFixedHeight(48)
        header.setObjectName("chatHeader")
        header.setStyleSheet(f"""
            QFrame#chatHeader {{
                background-color: {ChatColors.HEADER_BG};
                border-top-left-radius: 12px;
                border-top-right-radius: 12px;
                border: none;
            }}
        """)
        
        layout = QHBoxLayout(header)
        layout.setContentsMargins(14, 0, 10, 0)
        layout.setSpacing(10)
        
        # Bot ikonu ve durumu
        icon_container = QWidget()
        icon_layout = QHBoxLayout(icon_container)
        icon_layout.setContentsMargins(0, 0, 0, 0)
        icon_layout.setSpacing(6)

        # Çevrimiçi göstergesi (daha minimal)
        online_indicator = QLabel("●")
        online_indicator.setStyleSheet("color: #4CAF50; font-size: 12px; background: transparent;")
        online_indicator.setToolTip("Çevrimiçi")
        icon_layout.addWidget(online_indicator)

        layout.addWidget(icon_container)

        # Başlık
        title_layout = QVBoxLayout()
        title_layout.setSpacing(0)

        lbl_name = QLabel("Rota Asistan")
        lbl_name.setStyleSheet(f"color: {ChatColors.HEADER_TEXT}; font-size: 14px; font-weight: bold; background: transparent;")
        title_layout.addWidget(lbl_name)

        lbl_hint = QLabel("Üretim Yardımcınız")
        lbl_hint.setStyleSheet("color: rgba(255,255,255,0.8); font-size: 10px; background: transparent;")
        title_layout.addWidget(lbl_hint)
        
        layout.addLayout(title_layout)
        layout.addStretch()
        
        # Kapat butonu
        btn_close = QPushButton("✕")
        btn_close.setFixedSize(28, 28)
        btn_close.setCursor(Qt.PointingHandCursor)
        btn_close.setStyleSheet(f"""
            QPushButton {{
                background-color: transparent;
                color: {ChatColors.HEADER_TEXT};
                font-size: 16px;
                font-weight: bold;
                border: none;
                border-radius: 14px;
            }}
            QPushButton:hover {{
                background-color: rgba(255,255,255,0.2);
            }}
        """)
        btn_close.clicked.connect(self.close_requested.emit)
        layout.addWidget(btn_close)
        
        return header
    
    def _create_input(self):
        """Mesaj giriş alanı"""
        input_frame = QFrame()
        input_frame.setFixedHeight(60)
        input_frame.setStyleSheet(f"""
            QFrame {{
                background-color: {ChatColors.PANEL_BG};
                border-top: 1px solid {ChatColors.BORDER};
                border-bottom-left-radius: 12px;
                border-bottom-right-radius: 12px;
            }}
        """)
        
        layout = QHBoxLayout(input_frame)
        layout.setContentsMargins(12, 10, 12, 10)
        layout.setSpacing(10)
        
        self.input_field = QLineEdit()
        self.input_field.setPlaceholderText("Mesajınızı yazın...")
        self.input_field.setStyleSheet(f"""
            QLineEdit {{
                background-color: {ChatColors.INPUT_BG};
                border: 2px solid {ChatColors.BORDER};
                border-radius: 20px;
                padding: 10px 16px;
                font-size: 13px;
                color: #333;
            }}
            QLineEdit:focus {{
                border-color: {ChatColors.PRIMARY};
                background-color: {ChatColors.INPUT_FOCUS};
            }}
            QLineEdit:hover {{
                border-color: {ChatColors.PRIMARY_LIGHT};
            }}
        """)
        self.input_field.returnPressed.connect(self._send_message)
        layout.addWidget(self.input_field, 1)
        
        btn_send = QPushButton("➤")
        btn_send.setFixedSize(36, 36)
        btn_send.setCursor(Qt.PointingHandCursor)
        btn_send.setStyleSheet(f"""
            QPushButton {{
                background-color: {ChatColors.PRIMARY};
                color: white;
                font-size: 14px;
                border: none;
                border-radius: 18px;
            }}
            QPushButton:hover {{
                background-color: {ChatColors.PRIMARY_DARK};
            }}
        """)
        btn_send.clicked.connect(self._send_message)
        layout.addWidget(btn_send)
        
        return input_frame
    
    # =========================================================================
    # SÜRÜKLEME VE BOYUTLANDIRMA
    # =========================================================================
    
    def _get_resize_edge(self, pos):
        """Fare pozisyonuna göre hangi kenarın boyutlandırılacağını belirle"""
        rect = self.rect()
        margin = self.RESIZE_MARGIN
        
        edges = []
        
        if pos.x() <= margin:
            edges.append('left')
        elif pos.x() >= rect.width() - margin:
            edges.append('right')
            
        if pos.y() <= margin:
            edges.append('top')
        elif pos.y() >= rect.height() - margin:
            edges.append('bottom')
        
        return tuple(edges) if edges else None
    
    def _update_cursor(self, pos):
        """Fare pozisyonuna göre cursor'ı güncelle"""
        edge = self._get_resize_edge(pos)
        
        if edge is None:
            # Header üzerindeyse sürükleme cursor'ı
            if pos.y() <= self.header.height():
                self.setCursor(Qt.OpenHandCursor)
            else:
                self.setCursor(Qt.ArrowCursor)
        elif edge in [('left',), ('right',)]:
            self.setCursor(Qt.SizeHorCursor)
        elif edge in [('top',), ('bottom',)]:
            self.setCursor(Qt.SizeVerCursor)
        elif edge in [('left', 'top'), ('right', 'bottom')]:
            self.setCursor(Qt.SizeFDiagCursor)
        elif edge in [('right', 'top'), ('left', 'bottom')]:
            self.setCursor(Qt.SizeBDiagCursor)
        else:
            self.setCursor(Qt.ArrowCursor)
    
    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            pos = event.position().toPoint()
            edge = self._get_resize_edge(pos)
            
            if edge:
                # Boyutlandırma başlat
                self._resize_active = True
                self._resize_edge = edge
                self._drag_start_pos = event.globalPosition().toPoint()
                self._drag_start_geometry = self.geometry()
                event.accept()
            elif pos.y() <= self.header.height():
                # Sürükleme başlat
                self._drag_active = True
                self._drag_start_pos = event.globalPosition().toPoint()
                self._drag_start_geometry = self.geometry()
                self.setCursor(Qt.ClosedHandCursor)
                event.accept()
            else:
                super().mousePressEvent(event)
        else:
            super().mousePressEvent(event)
    
    def mouseMoveEvent(self, event):
        if self._drag_active and self._drag_start_pos:
            # Sürükleme
            delta = event.globalPosition().toPoint() - self._drag_start_pos
            new_pos = self._drag_start_geometry.topLeft() + delta
            
            # Parent sınırları içinde tut
            if self.parent():
                parent_rect = self.parent().rect()
                new_pos.setX(max(0, min(new_pos.x(), parent_rect.width() - self.width())))
                new_pos.setY(max(0, min(new_pos.y(), parent_rect.height() - self.height())))
            
            self.move(new_pos)
            event.accept()
            
        elif self._resize_active and self._resize_edge:
            # Boyutlandırma
            delta = event.globalPosition().toPoint() - self._drag_start_pos
            new_geo = QRect(self._drag_start_geometry)
            
            min_w, min_h = self.minimumWidth(), self.minimumHeight()
            
            if 'left' in self._resize_edge:
                new_left = new_geo.left() + delta.x()
                new_width = new_geo.right() - new_left + 1
                if new_width >= min_w:
                    new_geo.setLeft(new_left)
                    
            if 'right' in self._resize_edge:
                new_width = self._drag_start_geometry.width() + delta.x()
                if new_width >= min_w:
                    new_geo.setWidth(new_width)
                    
            if 'top' in self._resize_edge:
                new_top = new_geo.top() + delta.y()
                new_height = new_geo.bottom() - new_top + 1
                if new_height >= min_h:
                    new_geo.setTop(new_top)
                    
            if 'bottom' in self._resize_edge:
                new_height = self._drag_start_geometry.height() + delta.y()
                if new_height >= min_h:
                    new_geo.setHeight(new_height)
            
            # Parent sınırları içinde tut
            if self.parent():
                parent_rect = self.parent().rect()
                new_geo = new_geo.intersected(parent_rect)
            
            self.setGeometry(new_geo)
            event.accept()
            
        else:
            # Cursor güncelle
            self._update_cursor(event.position().toPoint())
            super().mouseMoveEvent(event)
    
    def mouseReleaseEvent(self, event):
        if event.button() == Qt.LeftButton:
            if self._drag_active:
                self._drag_active = False
                self._update_cursor(event.position().toPoint())
            if self._resize_active:
                self._resize_active = False
                self._resize_edge = None
            
            self._drag_start_pos = None
            self._drag_start_geometry = None
            event.accept()
        else:
            super().mouseReleaseEvent(event)
    
    def leaveEvent(self, event):
        if not self._drag_active and not self._resize_active:
            self.setCursor(Qt.ArrowCursor)
        super().leaveEvent(event)
    
    # =========================================================================
    # MESAJ FONKSİYONLARI
    # =========================================================================
    
    def add_bot_message(self, text, buttons=None):
        """Bot mesajı ekle"""
        bubble = MessageBubble(text, is_bot=True, buttons=buttons, parent=self.message_container)
        bubble.button_clicked.connect(self._on_quick_button)
        
        self.message_layout.takeAt(self.message_layout.count() - 1)
        self.message_layout.addWidget(bubble, alignment=Qt.AlignLeft)
        self.message_layout.addStretch()
        
        self._scroll_to_bottom()
    
    def add_user_message(self, text):
        """Kullanıcı mesajı ekle"""
        bubble = MessageBubble(text, is_bot=False, parent=self.message_container)
        
        self.message_layout.takeAt(self.message_layout.count() - 1)
        self.message_layout.addWidget(bubble, alignment=Qt.AlignRight)
        self.message_layout.addStretch()
        
        self._scroll_to_bottom()
    
    def _send_message(self):
        """Mesaj gönder"""
        text = self.input_field.text().strip()
        if not text:
            return

        self.add_user_message(text)
        self.input_field.clear()

        # Typing indicator göster
        self._show_typing_indicator()

        # 1-1.5 saniye gecikme ile yanıt ver (daha canlı hissiyat)
        delay = random.randint(1000, 1500)  # 1000-1500ms arası rastgele
        QTimer.singleShot(delay, lambda: self._process_and_respond(text))

    def _process_and_respond(self, text):
        """Mesajı işle ve yanıt ver (arka planda thread ile)"""
        # Önceki worker varsa temizle
        if self.worker and self.worker.isRunning():
            self.worker.wait()

        # Yeni worker thread başlat (ana thread donmayacak!)
        self.worker = BotWorker(text, self)
        self.worker.response_ready.connect(self._on_response_ready)
        self.worker.finished.connect(self._on_worker_finished)
        self.worker.start()

    def _on_response_ready(self, response):
        """Worker thread cevabı hazırladığında çağrılır"""
        # Typing indicator'ı kaldır
        self._hide_typing_indicator()

        # Cevabı ekrana bas
        self.add_bot_message(response.get('text', ''), response.get('buttons'))

    def _on_worker_finished(self):
        """Worker thread bittiğinde temizlik yap"""
        if self.worker:
            self.worker.deleteLater()
            self.worker = None

    def _show_typing_indicator(self):
        """Typing indicator göster"""
        if self.typing_indicator is None:
            self.typing_indicator = TypingIndicator(self.message_container)
            self.message_layout.takeAt(self.message_layout.count() - 1)
            self.message_layout.addWidget(self.typing_indicator, alignment=Qt.AlignLeft)
            self.message_layout.addStretch()
            self.typing_indicator.start()
            self._scroll_to_bottom()

    def _hide_typing_indicator(self):
        """Typing indicator gizle"""
        if self.typing_indicator:
            self.typing_indicator.stop()
            self.message_layout.removeWidget(self.typing_indicator)
            self.typing_indicator.deleteLater()
            self.typing_indicator = None
    
    def _on_quick_button(self, text):
        """Hızlı buton tıklandı"""
        clean_text = re.sub(r'^[^\w]+', '', text).strip()

        self.add_user_message(text)

        # Typing indicator göster
        self._show_typing_indicator()

        # 1-1.5 saniye gecikme ile yanıt ver (daha canlı hissiyat)
        delay = random.randint(1000, 1500)  # 1000-1500ms arası rastgele
        QTimer.singleShot(delay, lambda: self._process_button_response(clean_text))

    def _process_button_response(self, text):
        """Buton yanıtını işle (arka planda thread ile)"""
        # Önceki worker varsa temizle
        if self.worker and self.worker.isRunning():
            self.worker.wait()

        # Yeni worker thread başlat (ana thread donmayacak!)
        self.worker = BotWorker(text, self)
        self.worker.response_ready.connect(self._on_response_ready)
        self.worker.finished.connect(self._on_worker_finished)
        self.worker.start()
    
    def _scroll_to_bottom(self):
        """Scroll'u en alta getir"""
        QTimer.singleShot(50, lambda: self.scroll_area.verticalScrollBar().setValue(
            self.scroll_area.verticalScrollBar().maximum()
        ))


# =============================================================================
# FLOATING BUTON
# =============================================================================
class ChatFloatingButton(QPushButton):
    """Sağ alt köşedeki floating buton"""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.is_open = False
        self.setup_ui()
    
    def setup_ui(self):
        self.setFixedSize(52, 52)
        self.setCursor(Qt.PointingHandCursor)
        self.setText("💬")
        self.update_style()
        
        shadow = QGraphicsDropShadowEffect()
        shadow.setBlurRadius(15)
        shadow.setColor(QColor(0, 0, 0, 50))
        shadow.setOffset(0, 3)
        self.setGraphicsEffect(shadow)
    
    def update_style(self):
        bg = ChatColors.PRIMARY_DARK if self.is_open else ChatColors.PRIMARY
        self.setStyleSheet(f"""
            QPushButton {{
                background-color: {bg};
                color: white;
                font-size: 22px;
                border: none;
                border-radius: 26px;
            }}
            QPushButton:hover {{
                background-color: {ChatColors.PRIMARY_LIGHT};
            }}
        """)
    
    def set_open_state(self, is_open):
        self.is_open = is_open
        self.setText("✕" if is_open else "💬")
        self.update_style()


# =============================================================================
# ANA CHATBOT WIDGET
# =============================================================================
class ChatbotWidget(QWidget):
    """
    Dashboard'a eklenecek ana chatbot widget'ı.
    Sürüklenebilir panel + floating buton.
    """
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setAttribute(Qt.WA_TransparentForMouseEvents, False)

        self.is_open = False
        self.slide_animation = None  # Slide animasyonu
        self.fade_animation = None   # Fade animasyonu
        self.setup_ui()

        if parent:
            parent.installEventFilter(self)
    
    def setup_ui(self):
        # Bu widget görünmez, sadece koordinasyon için
        self.resize(0, 0)
        
        # Chat paneli - parent'ın child'ı olarak
        self.chat_panel = ChatPanel(self.parent())
        self.chat_panel.close_requested.connect(self.close_chat)
        self.chat_panel.hide()
        
        # Floating buton - parent'ın child'ı olarak
        self.float_button = ChatFloatingButton(self.parent())
        self.float_button.clicked.connect(self.toggle_chat)
        
        self._update_positions()
    
    def toggle_chat(self):
        """Chat panelini aç/kapat"""
        if self.is_open:
            self.close_chat()
        else:
            self.open_chat()
    
    def open_chat(self):
        """Chat panelini aç (sağdan sola slide + fade-in)"""
        if self.slide_animation and self.slide_animation.state() == QPropertyAnimation.Running:
            return  # Animasyon devam ediyorsa bekle

        self.is_open = True
        self._position_panel()

        # Panel'i ekranın sağ dışına yerleştir (başlangıç pozisyonu)
        start_pos = self.chat_panel.pos()
        off_screen_pos = QPoint(start_pos.x() + 400, start_pos.y())

        self.chat_panel.move(off_screen_pos)
        self.chat_panel.setWindowOpacity(0.0)  # Başlangıçta görünmez
        self.chat_panel.show()
        self.chat_panel.raise_()

        # Sağdan sola kayma animasyonu
        self.slide_animation = QPropertyAnimation(self.chat_panel, b"pos")
        self.slide_animation.setDuration(350)  # 350ms
        self.slide_animation.setStartValue(off_screen_pos)
        self.slide_animation.setEndValue(start_pos)
        self.slide_animation.setEasingCurve(QEasingCurve.OutCubic)  # Smooth deceleration

        # Fade-in animasyonu
        self.fade_animation = QPropertyAnimation(self.chat_panel, b"windowOpacity")
        self.fade_animation.setDuration(350)
        self.fade_animation.setStartValue(0.0)
        self.fade_animation.setEndValue(1.0)
        self.fade_animation.setEasingCurve(QEasingCurve.OutCubic)

        # Animasyonlar bitince focus
        self.slide_animation.finished.connect(lambda: self.chat_panel.input_field.setFocus())

        # Animasyonları başlat
        self.slide_animation.start()
        self.fade_animation.start()

        self.float_button.set_open_state(True)
        self.float_button.raise_()

    def close_chat(self):
        """Chat panelini kapat (sola sağa slide + fade-out)"""
        if self.slide_animation and self.slide_animation.state() == QPropertyAnimation.Running:
            return  # Animasyon devam ediyorsa bekle

        self.is_open = False

        # Panel'in mevcut pozisyonu
        current_pos = self.chat_panel.pos()
        off_screen_pos = QPoint(current_pos.x() + 400, current_pos.y())

        # Soldan sağa kayma animasyonu
        self.slide_animation = QPropertyAnimation(self.chat_panel, b"pos")
        self.slide_animation.setDuration(300)  # 300ms
        self.slide_animation.setStartValue(current_pos)
        self.slide_animation.setEndValue(off_screen_pos)
        self.slide_animation.setEasingCurve(QEasingCurve.InCubic)  # Smooth acceleration

        # Fade-out animasyonu
        self.fade_animation = QPropertyAnimation(self.chat_panel, b"windowOpacity")
        self.fade_animation.setDuration(300)
        self.fade_animation.setStartValue(1.0)
        self.fade_animation.setEndValue(0.0)
        self.fade_animation.setEasingCurve(QEasingCurve.InCubic)

        # Animasyonlar bitince gizle
        self.slide_animation.finished.connect(self.chat_panel.hide)

        # Animasyonları başlat
        self.slide_animation.start()
        self.fade_animation.start()

        self.float_button.set_open_state(False)
    
    def eventFilter(self, obj, event):
        """Parent resize olduğunda konumu güncelle"""
        if event.type() == QEvent.Resize:
            self._update_positions()
        return super().eventFilter(obj, event)
    
    def _update_positions(self):
        """Buton konumunu güncelle"""
        parent = self.parent()
        if not parent:
            return
        
        parent_rect = parent.rect()
        margin = 20
        
        # Floating buton - sağ alt köşe
        btn_x = parent_rect.width() - self.float_button.width() - margin
        btn_y = parent_rect.height() - self.float_button.height() - margin
        self.float_button.move(btn_x, btn_y)
        self.float_button.raise_()
    
    def _position_panel(self):
        """Panel için başlangıç konumu"""
        parent = self.parent()
        if not parent:
            return
        
        parent_rect = parent.rect()
        margin = 20
        
        # Panel - butonun üstünde, sağ alt köşede
        panel_w = self.chat_panel.width()
        panel_h = self.chat_panel.height()
        
        panel_x = parent_rect.width() - panel_w - margin
        panel_y = parent_rect.height() - panel_h - self.float_button.height() - margin - 10
        
        # Sınırlar içinde tut
        panel_x = max(margin, min(panel_x, parent_rect.width() - panel_w - margin))
        panel_y = max(margin, min(panel_y, parent_rect.height() - panel_h - margin))
        
        self.chat_panel.move(panel_x, panel_y)
    
    def showEvent(self, event):
        """Widget gösterildiğinde"""
        super().showEvent(event)
        self._update_positions()
        self.float_button.show()
        self.float_button.raise_()
    
    def hideEvent(self, event):
        """Widget gizlendiğinde"""
        super().hideEvent(event)
        self.chat_panel.hide()
        self.float_button.hide()