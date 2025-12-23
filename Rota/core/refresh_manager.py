# -*- coding: utf-8 -*-
"""
EFES ROTA X - Refresh Manager
Event-driven refresh sistemi - Timer polling'i ortadan kaldırır

Özellikler:
- Dirty tracking (sadece değişen veri refresh edilir)
- Version tracking (versiyon kontrolü)
- Debounce (çok sık refresh engelleme)
- Event-driven (timer yerine signal-based)
"""

from datetime import datetime, timedelta
from typing import Dict, Callable, Optional, Set, Any
from PySide6.QtCore import QObject, Signal, QTimer
from collections import defaultdict
import threading


class DataVersion:
    """Veri versiyonunu takip eder"""
    def __init__(self, version: int = 0, timestamp: datetime = None):
        self.version = version
        self.timestamp = timestamp or datetime.now()
        self.dirty = False

    def increment(self):
        """Versiyon artır ve dirty flag'i set et"""
        self.version += 1
        self.timestamp = datetime.now()
        self.dirty = True

    def mark_clean(self):
        """Clean duruma al"""
        self.dirty = False


class DebounceTimer:
    """
    Debounce mekanizması - Çok sık refresh'i engeller

    Örnek: 100ms içinde 10 tane refresh isteği gelirse,
    sadece 1 tane execute eder
    """
    def __init__(self, delay_ms: int = 500):
        self.delay_ms = delay_ms
        self.timer = None
        self.callback = None
        self.lock = threading.Lock()

    def trigger(self, callback: Callable):
        """
        Debounce'lu trigger
        Eğer delay süresi içinde tekrar çağrılırsa, timer resetlenir
        """
        with self.lock:
            if self.timer is not None:
                self.timer.stop()
                self.timer.deleteLater()

            self.callback = callback
            self.timer = QTimer()
            self.timer.setSingleShot(True)
            self.timer.timeout.connect(self._execute)
            self.timer.start(self.delay_ms)

    def _execute(self):
        """Callback'i çalıştır"""
        if self.callback:
            self.callback()
            self.callback = None

    def cancel(self):
        """İptal et"""
        with self.lock:
            if self.timer:
                self.timer.stop()
                self.timer.deleteLater()
                self.timer = None
            self.callback = None


class RefreshManager(QObject):
    """
    Merkezi Refresh Yöneticisi

    Timer polling yerine event-driven refresh sistemi sağlar.

    Kullanım:
        refresh_mgr = RefreshManager()

        # View'ı kaydet
        refresh_mgr.register_view('orders', orders_view.refresh_data)

        # Veri değiştiğinde bildir
        refresh_mgr.mark_dirty('orders')

        # RefreshManager otomatik olarak debounce ile refresh eder
    """

    # Signals
    data_changed = Signal(str)  # data_key değişti

    def __init__(self, debounce_ms: int = 500):
        super().__init__()

        # Veri versiyonları
        self._versions: Dict[str, DataVersion] = {}

        # View callbacks
        self._view_callbacks: Dict[str, Set[Callable]] = defaultdict(set)

        # Debounce timer'lar (her data_key için)
        self._debouncers: Dict[str, DebounceTimer] = {}

        # Debounce delay
        self.debounce_ms = debounce_ms

        # Dependency mapping (bir data değiştiğinde hangileri etkilenir)
        self._dependencies: Dict[str, Set[str]] = defaultdict(set)

        # Lock
        self._lock = threading.Lock()

    def register_view(self, data_key: str, callback: Callable, dependencies: list = None):
        """
        View'ı refresh sistemine kaydet

        Args:
            data_key: Veri anahtarı (örn: 'orders', 'production_logs')
            callback: Refresh fonksiyonu
            dependencies: Bu view hangi data'lara bağımlı? (örn: ['orders', 'stations'])
        """
        with self._lock:
            self._view_callbacks[data_key].add(callback)

            # Versiyonu başlat
            if data_key not in self._versions:
                self._versions[data_key] = DataVersion()

            # Debouncer oluştur
            if data_key not in self._debouncers:
                self._debouncers[data_key] = DebounceTimer(self.debounce_ms)

            # Dependency mapping
            if dependencies:
                for dep in dependencies:
                    self._dependencies[dep].add(data_key)

    def unregister_view(self, data_key: str, callback: Callable):
        """View'ı sistemden çıkar"""
        with self._lock:
            if data_key in self._view_callbacks:
                self._view_callbacks[data_key].discard(callback)

    def mark_dirty(self, data_key: str, propagate: bool = True):
        """
        Veriyi 'dirty' olarak işaretle ve refresh tetikle

        Args:
            data_key: Değişen veri
            propagate: Bağımlı data'ları da dirty yap mı?
        """
        with self._lock:
            # Versiyon artır
            if data_key not in self._versions:
                self._versions[data_key] = DataVersion()

            self._versions[data_key].increment()

            # Signal gönder
            self.data_changed.emit(data_key)

            # Debounce ile refresh tetikle
            if data_key in self._debouncers:
                self._debouncers[data_key].trigger(
                    lambda: self._refresh_views(data_key)
                )

            # Bağımlı data'ları da dirty yap
            if propagate and data_key in self._dependencies:
                for dependent in self._dependencies[data_key]:
                    self.mark_dirty(dependent, propagate=False)

    def _refresh_views(self, data_key: str):
        """
        İlgili tüm view'ları refresh et
        """
        callbacks = self._view_callbacks.get(data_key, set())

        for callback in callbacks:
            try:
                callback()
            except Exception as e:
                print(f"Refresh error for {data_key}: {e}")

        # Dirty flag'i temizle
        if data_key in self._versions:
            self._versions[data_key].mark_clean()

    def force_refresh(self, data_key: str):
        """
        Debounce'u bypass et, hemen refresh et
        """
        # Debouncer'ı iptal et
        if data_key in self._debouncers:
            self._debouncers[data_key].cancel()

        # Hemen refresh
        self._refresh_views(data_key)

    def get_version(self, data_key: str) -> Optional[DataVersion]:
        """Veri versiyonunu al"""
        return self._versions.get(data_key)

    def is_dirty(self, data_key: str) -> bool:
        """Veri dirty mi?"""
        version = self._versions.get(data_key)
        return version.dirty if version else False

    def set_debounce_delay(self, delay_ms: int):
        """Global debounce delay'i değiştir"""
        self.debounce_ms = delay_ms

        # Mevcut debouncer'ları güncelle
        with self._lock:
            for debouncer in self._debouncers.values():
                debouncer.delay_ms = delay_ms


# Global instance
refresh_manager = RefreshManager(debounce_ms=500)


# Convenience decorators
def mark_dirty(data_key: str):
    """
    Decorator: Fonksiyon çalıştığında veriyi dirty yap

    Kullanım:
        @mark_dirty('orders')
        def add_order(self, order_data):
            # Sipariş ekle
            ...
    """
    def decorator(func):
        def wrapper(*args, **kwargs):
            result = func(*args, **kwargs)
            refresh_manager.mark_dirty(data_key)
            return result
        return wrapper
    return decorator


def requires_refresh(data_key: str):
    """
    Decorator: Fonksiyon çalışmadan önce fresh data garanti et

    Kullanım:
        @requires_refresh('orders')
        def process_orders(self):
            # Orders kesinlikle güncel
            ...
    """
    def decorator(func):
        def wrapper(*args, **kwargs):
            # Eğer dirty ise refresh et
            if refresh_manager.is_dirty(data_key):
                refresh_manager.force_refresh(data_key)
            return func(*args, **kwargs)
        return wrapper
    return decorator
