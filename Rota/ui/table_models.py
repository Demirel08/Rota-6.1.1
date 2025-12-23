# -*- coding: utf-8 -*-
"""
EFES ROTA X - Table Models (Model/View Pattern)

QTableWidget yerine QAbstractTableModel kullanımı:
- Virtual scrolling (1000+ satır sorunsuz)
- Incremental update (sadece değişen hücreler)
- Minimal memory footprint
- Daha hızlı rendering
"""

from PySide6.QtCore import Qt, QAbstractTableModel, QModelIndex, QVariant
from PySide6.QtGui import QColor, QFont
from typing import List, Dict, Any, Optional
from datetime import datetime


class OrderTableModel(QAbstractTableModel):
    """
    Sipariş Tablosu için Model

    Virtual scrolling sayesinde 10,000+ sipariş sorunsuz gösterilir.
    Sadece görünür satırlar render edilir.
    """

    # Kolon tanımları
    COLUMNS = [
        {"key": "order_code", "header": "Kod", "width": 90},
        {"key": "customer_name", "header": "Müşteri", "width": 140},
        {"key": "product_type", "header": "Ürün", "width": 90},
        {"key": "quantity", "header": "Adet", "width": 60},
        {"key": "declared_total_m2", "header": "m²", "width": 60},
        {"key": "thickness", "header": "Kalınlık", "width": 70},
        {"key": "status", "header": "Durum", "width": 90},
        {"key": "priority", "header": "Öncelik", "width": 80},
        {"key": "delivery_date", "header": "Termin", "width": 90},
        {"key": "notes", "header": "Not", "width": 200},
    ]

    def __init__(self, data: List[Dict] = None):
        super().__init__()
        self._data = data or []
        self._column_keys = [col["key"] for col in self.COLUMNS]
        self._column_headers = [col["header"] for col in self.COLUMNS]

        # Renk mapping
        self._status_colors = {
            "Beklemede": ("#0066CC", "#E3F2FD"),
            "Üretimde": ("#107C41", "#E6F4EA"),
            "Tamamlandı": ("#2E7D32", "#E8F5E9"),
            "Sevk Edildi": "#666666",
        }

        self._priority_colors = {
            "Kritik": ("#C00000", "#FDE8E8"),
            "Çok Acil": ("#C65911", "#FFF3E0"),
            "Acil": ("#FF6B00", "#FFF4E6"),
            "Normal": "#1A1A1A",
        }

    def rowCount(self, parent=QModelIndex()):
        """Satır sayısı"""
        return len(self._data)

    def columnCount(self, parent=QModelIndex()):
        """Kolon sayısı"""
        return len(self.COLUMNS)

    def data(self, index: QModelIndex, role=Qt.DisplayRole):
        """
        Hücre verisi döndür

        Qt otomatik olarak sadece görünür hücreleri çizer (virtual scrolling)
        """
        if not index.isValid():
            return QVariant()

        row = index.row()
        col = index.column()

        if row >= len(self._data) or col >= len(self._column_keys):
            return QVariant()

        order = self._data[row]
        col_key = self._column_keys[col]

        # Display role (metin)
        if role == Qt.DisplayRole:
            value = order.get(col_key, "")

            # Formatlama
            if col_key == "declared_total_m2":
                return f"{value:.1f}" if isinstance(value, (int, float)) else str(value)
            elif col_key == "quantity":
                return str(value) if value else "0"
            elif col_key == "notes":
                # Not çok uzunsa kısalt
                note = str(value) if value else ""
                return note[:50] + "..." if len(note) > 50 else note
            else:
                return str(value) if value else ""

        # Text align
        elif role == Qt.TextAlignmentRole:
            if col_key in ["quantity", "declared_total_m2", "thickness"]:
                return Qt.AlignRight | Qt.AlignVCenter
            else:
                return Qt.AlignLeft | Qt.AlignVCenter

        # Foreground color (metin rengi)
        elif role == Qt.ForegroundRole:
            if col_key == "status":
                status = order.get("status", "")
                if status in self._status_colors:
                    fg = self._status_colors[status]
                    if isinstance(fg, tuple):
                        return QColor(fg[0])
                    return QColor(fg)

            elif col_key == "priority":
                priority = order.get("priority", "")
                if priority in self._priority_colors:
                    fg = self._priority_colors[priority]
                    if isinstance(fg, tuple):
                        return QColor(fg[0])
                    return QColor(fg)

            return QColor("#1A1A1A")  # Default text color

        # Background color
        elif role == Qt.BackgroundRole:
            if col_key == "status":
                status = order.get("status", "")
                if status in self._status_colors:
                    color_data = self._status_colors[status]
                    if isinstance(color_data, tuple):
                        return QColor(color_data[1])

            elif col_key == "priority":
                priority = order.get("priority", "")
                if priority in self._priority_colors:
                    color_data = self._priority_colors[priority]
                    if isinstance(color_data, tuple):
                        return QColor(color_data[1])

            # Alternating row colors
            if row % 2 == 1:
                return QColor("#F9F9F9")

        # Font (bold için)
        elif role == Qt.FontRole:
            if col_key in ["order_code", "priority"]:
                font = QFont()
                if col_key == "priority":
                    priority = order.get("priority", "")
                    if priority in ["Kritik", "Çok Acil"]:
                        font.setBold(True)
                else:
                    font.setBold(True)
                return font

        # Tooltip
        elif role == Qt.ToolTipRole:
            if col_key == "notes":
                note = order.get("notes", "")
                return str(note) if note else None

        return QVariant()

    def headerData(self, section, orientation, role=Qt.DisplayRole):
        """Başlık verisi"""
        if role == Qt.DisplayRole:
            if orientation == Qt.Horizontal:
                if section < len(self._column_headers):
                    return self._column_headers[section]
            else:
                return str(section + 1)

        elif role == Qt.FontRole:
            font = QFont()
            font.setBold(True)
            return font

        elif role == Qt.ForegroundRole:
            return QColor("#1A1A1A")

        elif role == Qt.BackgroundRole:
            return QColor("#F3F3F3")

        return QVariant()

    def get_order(self, row: int) -> Optional[Dict]:
        """Belirli bir satırdaki siparişi döndür"""
        if 0 <= row < len(self._data):
            return self._data[row]
        return None

    def update_data(self, new_data: List[Dict]):
        """
        Veriyi güncelle (incremental)

        layoutChanged signal'i ile Qt'ye bildir
        """
        self.beginResetModel()
        self._data = new_data
        self.endResetModel()

    def update_row(self, row: int, order_data: Dict):
        """Tek bir satırı güncelle (daha hızlı)"""
        if 0 <= row < len(self._data):
            self._data[row] = order_data

            # Sadece değişen satırı güncelle
            top_left = self.index(row, 0)
            bottom_right = self.index(row, self.columnCount() - 1)
            self.dataChanged.emit(top_left, bottom_right)

    def insert_row_data(self, row: int, order_data: Dict):
        """Yeni satır ekle"""
        self.beginInsertRows(QModelIndex(), row, row)
        self._data.insert(row, order_data)
        self.endInsertRows()

    def remove_row_data(self, row: int):
        """Satır sil"""
        if 0 <= row < len(self._data):
            self.beginRemoveRows(QModelIndex(), row, row)
            self._data.pop(row)
            self.endRemoveRows()

    def sort(self, column: int, order=Qt.AscendingOrder):
        """Sıralama"""
        if column < len(self._column_keys):
            key = self._column_keys[column]
            reverse = (order == Qt.DescendingOrder)

            self.layoutAboutToBeChanged.emit()

            self._data.sort(
                key=lambda x: x.get(key, ""),
                reverse=reverse
            )

            self.layoutChanged.emit()


class ProductionMatrixModel(QAbstractTableModel):
    """
    Üretim Matrisi için Model

    Sipariş × İstasyon matrisi gösterir
    Virtual scrolling ile büyük veri setlerini destekler
    """

    def __init__(self, data: List[Dict] = None, stations: List[str] = None):
        super().__init__()
        self._data = data or []
        self._stations = stations or []

        # Kolonlar: [Sipariş Kodu, Müşteri, ...istasyonlar..., Durum]
        self._base_columns = ["order_code", "customer_name", "priority"]
        self._column_keys = self._base_columns + self._stations + ["status"]

    def rowCount(self, parent=QModelIndex()):
        return len(self._data)

    def columnCount(self, parent=QModelIndex()):
        return len(self._column_keys)

    def data(self, index: QModelIndex, role=Qt.DisplayRole):
        if not index.isValid():
            return QVariant()

        row = index.row()
        col = index.column()

        if row >= len(self._data):
            return QVariant()

        order = self._data[row]
        col_key = self._column_keys[col]

        # Display role
        if role == Qt.DisplayRole:
            # Base kolonlar
            if col_key in self._base_columns:
                return str(order.get(col_key, ""))

            # İstasyon kolonları
            elif col_key in self._stations:
                status_map = order.get("status_map", {})
                if col_key in status_map:
                    info = status_map[col_key]
                    status = info["status"]
                    done = info["done"]
                    total = info["total"]
                    return f"{done}/{total}"
                return "-"

            # Durum
            elif col_key == "status":
                return str(order.get("status", ""))

        # Background color (istasyon durumu)
        elif role == Qt.BackgroundRole:
            if col_key in self._stations:
                status_map = order.get("status_map", {})
                if col_key in status_map:
                    st_status = status_map[col_key]["status"]
                    if st_status == "Bitti":
                        return QColor("#E6F4EA")  # Yeşil
                    elif st_status == "Kısmi":
                        return QColor("#FFF3E0")  # Turuncu
                    else:  # Bekliyor
                        return QColor("#F5F5F5")  # Gri

        # Text align
        elif role == Qt.TextAlignmentRole:
            if col_key in self._stations:
                return Qt.AlignCenter | Qt.AlignVCenter
            return Qt.AlignLeft | Qt.AlignVCenter

        return QVariant()

    def headerData(self, section, orientation, role=Qt.DisplayRole):
        if role == Qt.DisplayRole:
            if orientation == Qt.Horizontal:
                if section < len(self._column_keys):
                    key = self._column_keys[section]
                    # Header isimlendirme
                    headers = {
                        "order_code": "Kod",
                        "customer_name": "Müşteri",
                        "priority": "Öncelik",
                        "status": "Durum"
                    }
                    return headers.get(key, key)
            else:
                return str(section + 1)

        elif role == Qt.FontRole:
            font = QFont()
            font.setBold(True)
            font.setPointSize(9)
            return font

        return QVariant()

    def update_data(self, new_data: List[Dict], stations: List[str] = None):
        """Veriyi güncelle"""
        self.beginResetModel()
        self._data = new_data
        if stations:
            self._stations = stations
            self._column_keys = self._base_columns + self._stations + ["status"]
        self.endResetModel()
