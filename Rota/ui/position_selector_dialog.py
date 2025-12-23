"""
HEDEF POZİSYON SEÇİCİ DIALOG

Kullanıcının siparişi hangi sıraya taşımak istediğini seçmesini sağlar.
"""

from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel,
    QPushButton, QSpinBox, QRadioButton, QButtonGroup,
    QFrame
)
from PySide6.QtCore import Qt
from PySide6.QtGui import QFont


class PositionSelectorDialog(QDialog):
    """Hedef pozisyon seçim dialog'u"""

    def __init__(self, current_position: int, total_orders: int, parent=None):
        """
        Args:
            current_position: Mevcut sıra (0-based)
            total_orders: Toplam sipariş sayısı
            parent: Ana pencere
        """
        super().__init__(parent)
        self.current_position = current_position
        self.total_orders = total_orders
        self.selected_position = None

        self.setWindowTitle("Hedef Pozisyon Seçin")
        self.setMinimumWidth(450)
        self.setModal(True)

        self._setup_ui()

    def _setup_ui(self):
        """UI bileşenlerini oluştur"""
        layout = QVBoxLayout(self)
        layout.setSpacing(15)
        layout.setContentsMargins(20, 20, 20, 20)

        # Başlık
        title = QLabel("📍 Hedef Pozisyon Seçin")
        title_font = QFont()
        title_font.setPointSize(12)
        title_font.setBold(True)
        title.setFont(title_font)
        title.setStyleSheet("color: #1A1A1A; margin-bottom: 5px;")
        layout.addWidget(title)

        # Açıklama
        desc = QLabel(
            f"Seçili sipariş şu anda <b>{self.current_position + 1}. sırada</b>.<br>"
            f"Hangi sıraya taşımak istersiniz?"
        )
        desc.setStyleSheet("color: #666666; font-size: 10pt;")
        desc.setWordWrap(True)
        layout.addWidget(desc)

        # Ayırıcı
        separator = QFrame()
        separator.setFrameShape(QFrame.HLine)
        separator.setStyleSheet("background-color: #D4D4D4; margin: 10px 0;")
        layout.addWidget(separator)

        # Seçenekler
        self.button_group = QButtonGroup(self)

        # Hızlı seçenekler
        quick_options = QVBoxLayout()
        quick_options.setSpacing(10)

        # 1. En Üst
        self.radio_top = QRadioButton(f"🔝 En üste taşı (1. sıra)")
        self.radio_top.setStyleSheet("font-size: 10pt;")
        self.button_group.addButton(self.radio_top, 0)
        quick_options.addWidget(self.radio_top)

        # 2. Yukarı
        if self.current_position > 0:
            up_target = max(0, self.current_position - 3)
            self.radio_up = QRadioButton(f"⬆️ 3 sıra yukarı ({up_target + 1}. sıra)")
            self.radio_up.setStyleSheet("font-size: 10pt;")
            self.button_group.addButton(self.radio_up, 1)
            quick_options.addWidget(self.radio_up)

        # 3. Aşağı
        if self.current_position < self.total_orders - 1:
            down_target = min(self.total_orders - 1, self.current_position + 3)
            self.radio_down = QRadioButton(f"⬇️ 3 sıra aşağı ({down_target + 1}. sıra)")
            self.radio_down.setStyleSheet("font-size: 10pt;")
            self.button_group.addButton(self.radio_down, 2)
            quick_options.addWidget(self.radio_down)

        # 4. En Alt
        self.radio_bottom = QRadioButton(f"🔻 En alta taşı ({self.total_orders}. sıra)")
        self.radio_bottom.setStyleSheet("font-size: 10pt;")
        self.button_group.addButton(self.radio_bottom, 3)
        quick_options.addWidget(self.radio_bottom)

        # 5. Manuel seçim
        manual_layout = QHBoxLayout()
        self.radio_manual = QRadioButton("✏️ Manuel:")
        self.radio_manual.setStyleSheet("font-size: 10pt;")
        self.button_group.addButton(self.radio_manual, 4)
        manual_layout.addWidget(self.radio_manual)

        self.spin_manual = QSpinBox()
        self.spin_manual.setMinimum(1)
        self.spin_manual.setMaximum(self.total_orders)
        self.spin_manual.setValue(1)
        self.spin_manual.setSuffix(". sıra")
        self.spin_manual.setStyleSheet("font-size: 10pt; padding: 5px;")
        self.spin_manual.valueChanged.connect(self._on_manual_changed)
        manual_layout.addWidget(self.spin_manual)
        manual_layout.addStretch()

        quick_options.addLayout(manual_layout)

        layout.addLayout(quick_options)

        # Varsayılan: En üst seçili
        self.radio_top.setChecked(True)

        # Ayırıcı
        separator2 = QFrame()
        separator2.setFrameShape(QFrame.HLine)
        separator2.setStyleSheet("background-color: #D4D4D4; margin: 10px 0;")
        layout.addWidget(separator2)

        # Butonlar
        button_layout = QHBoxLayout()
        button_layout.addStretch()

        # İptal
        cancel_btn = QPushButton("❌ İptal")
        cancel_btn.setMinimumHeight(35)
        cancel_btn.setStyleSheet("""
            QPushButton {
                background-color: #F44336;
                color: white;
                border: none;
                border-radius: 5px;
                padding: 8px 20px;
                font-size: 10pt;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #D32F2F;
            }
        """)
        cancel_btn.clicked.connect(self.reject)
        button_layout.addWidget(cancel_btn)

        # Analiz Yap
        analyze_btn = QPushButton("📊 Analiz Yap")
        analyze_btn.setMinimumHeight(35)
        analyze_btn.setStyleSheet("""
            QPushButton {
                background-color: #4CAF50;
                color: white;
                border: none;
                border-radius: 5px;
                padding: 8px 20px;
                font-size: 10pt;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #45A049;
            }
        """)
        analyze_btn.clicked.connect(self._confirm)
        button_layout.addWidget(analyze_btn)

        layout.addLayout(button_layout)

    def _on_manual_changed(self):
        """Manuel spin box değiştiğinde manuel radio'yu seç"""
        self.radio_manual.setChecked(True)

    def _confirm(self):
        """Kullanıcı onayladı"""
        selected_id = self.button_group.checkedId()

        if selected_id == 0:
            # En üst
            self.selected_position = 0
        elif selected_id == 1:
            # 3 yukarı
            self.selected_position = max(0, self.current_position - 3)
        elif selected_id == 2:
            # 3 aşağı
            self.selected_position = min(self.total_orders - 1, self.current_position + 3)
        elif selected_id == 3:
            # En alt
            self.selected_position = self.total_orders - 1
        elif selected_id == 4:
            # Manuel
            self.selected_position = self.spin_manual.value() - 1  # 0-based index

        self.accept()

    def get_target_position(self) -> int:
        """Seçilen hedef pozisyonu döndür (0-based)"""
        return self.selected_position if self.selected_position is not None else self.current_position
