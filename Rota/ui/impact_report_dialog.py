"""
ETKİ ANALİZİ RAPOR POPUP'I

Sipariş değişikliklerinin etkilerini görsel olarak gösteren dialog.
Excel tarzı minimal tasarım.
"""

from datetime import datetime
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel,
    QPushButton, QScrollArea, QWidget, QFrame, QTableWidget,
    QTableWidgetItem, QHeaderView
)
from PySide6.QtCore import Qt
from PySide6.QtGui import QFont, QColor


class ImpactReportDialog(QDialog):
    """Etki analizi sonuçlarını gösteren popup dialog - Excel tarzı"""

    def __init__(self, analysis_result: dict, selected_order: dict,
                 current_position: int = None, target_position: int = None, parent=None):
        """
        Args:
            analysis_result: ImpactAnalyzer.analyze_reorder_impact() sonucu
            selected_order: Değiştirilen sipariş bilgisi
            current_position: Mevcut pozisyon (0-based, opsiyonel)
            target_position: Hedef pozisyon (0-based, opsiyonel)
            parent: Ana pencere
        """
        super().__init__(parent)
        self.analysis = analysis_result
        self.selected_order = selected_order
        self.current_position = current_position
        self.target_position = target_position
        self.user_confirmed = False

        self.setWindowTitle("Etki Analizi Raporu")
        self.setMinimumWidth(900)
        self.setMinimumHeight(600)

        self._setup_ui()

    def _setup_ui(self):
        """UI bileşenlerini oluştur"""
        layout = QVBoxLayout(self)
        layout.setSpacing(0)
        layout.setContentsMargins(0, 0, 0, 0)

        # Stil tanımları
        self.setStyleSheet("""
            QDialog {
                background-color: #FFFFFF;
            }
            QLabel {
                color: #1A1A1A;
            }
        """)

        # Başlık
        self._add_header(layout)

        # Özet bilgi
        self._add_summary(layout)

        # Tablo
        self._add_table(layout)

        # Alt butonlar
        self._add_buttons(layout)

    def _add_header(self, layout):
        """Başlık bölümü - Excel tarzı"""
        header_widget = QWidget()
        header_widget.setStyleSheet("""
            QWidget {
                background-color: #F3F3F3;
                border-bottom: 2px solid #D4D4D4;
            }
        """)
        header_layout = QVBoxLayout(header_widget)
        header_layout.setContentsMargins(20, 15, 20, 15)
        header_layout.setSpacing(8)

        # Başlık
        title = QLabel("Etki Analizi Raporu")
        title_font = QFont()
        title_font.setPointSize(13)
        title_font.setBold(True)
        title.setFont(title_font)
        title.setStyleSheet("color: #1A1A1A; background: transparent; border: none;")
        header_layout.addWidget(title)

        # Sipariş bilgisi
        order_code = self.selected_order.get('order_code', 'N/A')
        customer = self.selected_order.get('customer_name', 'N/A')

        info_text = f"Sipariş: {order_code} | Müşteri: {customer}"

        if self.current_position is not None and self.target_position is not None:
            info_text += f" | Değişiklik: {self.current_position + 1}. sıra → {self.target_position + 1}. sıra"

        info_label = QLabel(info_text)
        info_label.setStyleSheet("color: #666666; font-size: 10pt; background: transparent; border: none;")
        header_layout.addWidget(info_label)

        layout.addWidget(header_widget)

    def _add_summary(self, layout):
        """Özet istatistikler - Minimal"""
        summary = self.analysis.get('summary', {})
        total = summary.get('total_affected', 0)
        delayed = summary.get('delayed_count', 0)
        improved = summary.get('improved_count', 0)
        exceeded = summary.get('deadline_exceeded_count', 0)

        if total == 0:
            return

        summary_widget = QWidget()
        summary_widget.setStyleSheet("""
            QWidget {
                background-color: #F9F9F9;
                border-bottom: 1px solid #E0E0E0;
            }
        """)
        summary_layout = QHBoxLayout(summary_widget)
        summary_layout.setContentsMargins(20, 12, 20, 12)
        summary_layout.setSpacing(30)

        # İstatistikler
        def create_stat(label, value, color):
            stat_layout = QHBoxLayout()
            stat_layout.setSpacing(8)

            label_widget = QLabel(label + ":")
            label_widget.setStyleSheet(f"color: #666666; font-size: 10pt; background: transparent;")

            value_widget = QLabel(str(value))
            value_font = QFont()
            value_font.setBold(True)
            value_font.setPointSize(11)
            value_widget.setFont(value_font)
            value_widget.setStyleSheet(f"color: {color}; background: transparent;")

            stat_layout.addWidget(label_widget)
            stat_layout.addWidget(value_widget)
            stat_layout.addStretch()

            return stat_layout

        summary_layout.addLayout(create_stat("Etkilenen", total, "#1A1A1A"))

        if delayed > 0:
            summary_layout.addLayout(create_stat("Gecikecek", delayed, "#C00000"))

        if exceeded > 0:
            summary_layout.addLayout(create_stat("Termin Aşan", exceeded, "#C00000"))

        if improved > 0:
            summary_layout.addLayout(create_stat("İyileşen", improved, "#107C41"))

        summary_layout.addStretch()

        layout.addWidget(summary_widget)

    def _add_table(self, layout):
        """Etkilenen siparişler tablosu"""
        affected_orders = self.analysis.get('affected_orders', [])

        if not affected_orders:
            no_data = QLabel("Etkilenen sipariş yok.")
            no_data.setAlignment(Qt.AlignCenter)
            no_data.setStyleSheet("color: #999999; padding: 40px; font-size: 11pt;")
            layout.addWidget(no_data)
            return

        # Tablo
        table = QTableWidget()
        table.setColumnCount(7)
        table.setRowCount(len(affected_orders))

        # Başlıklar
        headers = ["Sipariş No", "Müşteri", "Termin", "Mevcut Teslim", "Yeni Teslim", "Fark", "Durum"]
        table.setHorizontalHeaderLabels(headers)

        # Excel tarzı stil
        table.setStyleSheet("""
            QTableWidget {
                background-color: white;
                border: none;
                gridline-color: #E0E0E0;
                font-size: 10pt;
            }
            QTableWidget::item {
                padding: 8px;
                border-bottom: 1px solid #E0E0E0;
            }
            QTableWidget::item:selected {
                background-color: #E3F2FD;
                color: #1A1A1A;
            }
            QHeaderView::section {
                background-color: #F3F3F3;
                padding: 10px;
                border: none;
                border-bottom: 2px solid #D4D4D4;
                border-right: 1px solid #E0E0E0;
                font-weight: bold;
                font-size: 10pt;
                color: #1A1A1A;
            }
        """)

        # Satırları doldur
        for row, affected in enumerate(affected_orders):
            order = affected['order']
            diff_days = affected['diff_days']
            severity = affected['severity']
            exceeds = affected['exceeds_deadline']

            # Renk belirle
            if severity == 'critical' or exceeds:
                row_color = QColor(253, 232, 232)  # Açık kırmızı
                text_color = QColor(192, 0, 0)
            elif severity == 'warning':
                row_color = QColor(255, 243, 224)  # Açık turuncu
                text_color = QColor(198, 89, 17)
            elif severity == 'improved':
                row_color = QColor(230, 244, 234)  # Açık yeşil
                text_color = QColor(16, 124, 65)
            else:
                row_color = QColor(255, 255, 255)
                text_color = QColor(26, 26, 26)

            # Sütunlar
            items = [
                order.get('order_code', 'N/A'),
                order.get('customer_name', 'N/A')[:20],  # Kısalt
                order.get('delivery_date', 'N/A'),
                affected['old_completion_date'].strftime('%Y-%m-%d') if affected['old_completion_date'] else 'N/A',
                affected['new_completion_date'].strftime('%Y-%m-%d') if affected['new_completion_date'] else 'N/A',
                f"{diff_days:+d} gün" if diff_days != 0 else "0 gün",
                "Termin Aşan!" if exceeds else ("Gecikme" if diff_days > 0 else "İyileşme" if diff_days < 0 else "Değişmedi")
            ]

            for col, text in enumerate(items):
                item = QTableWidgetItem(str(text))
                item.setBackground(row_color)
                item.setForeground(text_color)

                # Fark sütunu bold
                if col == 5:
                    font = QFont()
                    font.setBold(True)
                    item.setFont(font)

                # Durum sütunu bold
                if col == 6:
                    font = QFont()
                    font.setBold(True)
                    item.setFont(font)

                # Merkez hizala (bazı sütunlar)
                if col in [2, 3, 4, 5]:
                    item.setTextAlignment(Qt.AlignCenter | Qt.AlignVCenter)

                table.setItem(row, col, item)

        # Sütun genişlikleri
        table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeToContents)  # Sipariş No
        table.horizontalHeader().setSectionResizeMode(1, QHeaderView.Stretch)  # Müşteri
        table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeToContents)  # Termin
        table.horizontalHeader().setSectionResizeMode(3, QHeaderView.ResizeToContents)  # Mevcut
        table.horizontalHeader().setSectionResizeMode(4, QHeaderView.ResizeToContents)  # Yeni
        table.horizontalHeader().setSectionResizeMode(5, QHeaderView.ResizeToContents)  # Fark
        table.horizontalHeader().setSectionResizeMode(6, QHeaderView.ResizeToContents)  # Durum

        # Dikey header gizle
        table.verticalHeader().setVisible(False)

        # Seçim modu
        table.setSelectionBehavior(QTableWidget.SelectRows)
        table.setSelectionMode(QTableWidget.SingleSelection)

        layout.addWidget(table)

    def _add_buttons(self, layout):
        """Alt butonlar - Minimal"""
        button_widget = QWidget()
        button_widget.setStyleSheet("""
            QWidget {
                background-color: #F9F9F9;
                border-top: 1px solid #D4D4D4;
            }
        """)
        button_layout = QHBoxLayout(button_widget)
        button_layout.setContentsMargins(20, 12, 20, 12)
        button_layout.setSpacing(10)

        button_layout.addStretch()

        # İptal butonu
        cancel_btn = QPushButton("İptal")
        cancel_btn.setMinimumWidth(100)
        cancel_btn.setMinimumHeight(32)
        cancel_btn.setStyleSheet("""
            QPushButton {
                background-color: #FFFFFF;
                color: #1A1A1A;
                border: 1px solid #D4D4D4;
                border-radius: 2px;
                padding: 6px 16px;
                font-size: 10pt;
            }
            QPushButton:hover {
                background-color: #F3F3F3;
                border: 1px solid #B4B4B4;
            }
        """)
        cancel_btn.clicked.connect(self.reject)
        button_layout.addWidget(cancel_btn)

        # Onayla butonu
        confirm_btn = QPushButton("Onayla ve Uygula")
        confirm_btn.setMinimumWidth(140)
        confirm_btn.setMinimumHeight(32)
        confirm_btn.setStyleSheet("""
            QPushButton {
                background-color: #217346;
                color: white;
                border: none;
                border-radius: 2px;
                padding: 6px 16px;
                font-size: 10pt;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #1D6640;
            }
        """)
        confirm_btn.clicked.connect(self._confirm)
        button_layout.addWidget(confirm_btn)

        layout.addWidget(button_widget)

    def _confirm(self):
        """Kullanıcı onayladı"""
        self.user_confirmed = True
        self.accept()

    def is_confirmed(self) -> bool:
        """Kullanıcı değişikliği onayladı mı?"""
        return self.user_confirmed
