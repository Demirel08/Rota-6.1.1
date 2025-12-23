# -*- coding: utf-8 -*-
"""
EFES ROTA X - Cache Manager
LRU (Least Recently Used) + TTL (Time To Live) Cache Sistemi

Performans iyileştirmesi için veritabanı sorgularını cache'ler.
"""

from collections import OrderedDict
from datetime import datetime, timedelta
from typing import Any, Optional, Callable
import threading
import hashlib
import json


class CacheEntry:
    """Tek bir cache kaydı"""
    def __init__(self, value: Any, ttl_seconds: int):
        self.value = value
        self.created_at = datetime.now()
        self.ttl = timedelta(seconds=ttl_seconds)
        self.access_count = 0
        self.last_access = datetime.now()

    def is_expired(self) -> bool:
        """Cache süresi doldu mu?"""
        return datetime.now() - self.created_at > self.ttl

    def touch(self):
        """Access kaydı tut (LRU için)"""
        self.access_count += 1
        self.last_access = datetime.now()


class LRUCache:
    """
    LRU (Least Recently Used) Cache

    Özellikler:
    - Maksimum size (bellek kontrolü)
    - TTL (Time To Live)
    - Thread-safe
    - Hit/miss istatistikleri
    """

    def __init__(self, max_size: int = 1000, ttl_seconds: int = 60):
        """
        Args:
            max_size: Maksimum cache entry sayısı
            ttl_seconds: Cache geçerlilik süresi (saniye)
        """
        self.max_size = max_size
        self.ttl_seconds = ttl_seconds
        self._cache = OrderedDict()
        self._lock = threading.Lock()

        # İstatistikler
        self.hits = 0
        self.misses = 0
        self.evictions = 0  # Çıkarılan entry sayısı

    def get(self, key: str) -> Optional[Any]:
        """
        Cache'den veri çek

        Returns:
            Cached value veya None (miss/expired)
        """
        with self._lock:
            if key in self._cache:
                entry = self._cache[key]

                # Expired check
                if entry.is_expired():
                    del self._cache[key]
                    self.misses += 1
                    return None

                # Hit!
                entry.touch()
                self._cache.move_to_end(key)  # LRU güncelle
                self.hits += 1
                return entry.value
            else:
                # Miss
                self.misses += 1
                return None

    def set(self, key: str, value: Any, ttl_seconds: Optional[int] = None):
        """
        Cache'e veri ekle

        Args:
            key: Cache anahtarı
            value: Değer
            ttl_seconds: Özel TTL (None ise default kullanılır)
        """
        ttl = ttl_seconds if ttl_seconds is not None else self.ttl_seconds

        with self._lock:
            # Mevcut entry'yi güncelle
            if key in self._cache:
                del self._cache[key]

            # Yeni entry ekle
            self._cache[key] = CacheEntry(value, ttl)

            # Size kontrolü - LRU çıkar
            while len(self._cache) > self.max_size:
                # En eski (least recently used) entry'yi çıkar
                oldest_key = next(iter(self._cache))
                del self._cache[oldest_key]
                self.evictions += 1

    def delete(self, key: str):
        """Belirli bir entry'yi sil"""
        with self._lock:
            if key in self._cache:
                del self._cache[key]

    def clear(self):
        """Tüm cache'i temizle"""
        with self._lock:
            self._cache.clear()
            self.hits = 0
            self.misses = 0
            self.evictions = 0

    def cleanup_expired(self):
        """Süresi dolmuş entry'leri temizle"""
        with self._lock:
            expired_keys = [
                key for key, entry in self._cache.items()
                if entry.is_expired()
            ]
            for key in expired_keys:
                del self._cache[key]

    def get_stats(self) -> dict:
        """Cache istatistiklerini döndür"""
        total_requests = self.hits + self.misses
        hit_rate = (self.hits / total_requests * 100) if total_requests > 0 else 0

        return {
            "size": len(self._cache),
            "max_size": self.max_size,
            "hits": self.hits,
            "misses": self.misses,
            "evictions": self.evictions,
            "hit_rate": round(hit_rate, 2),
            "total_requests": total_requests
        }

    def __len__(self):
        return len(self._cache)

    def __contains__(self, key):
        with self._lock:
            return key in self._cache and not self._cache[key].is_expired()


class QueryCache:
    """
    SQL Query Cache (LRU Cache'in üzerine query-specific özellikler)

    Özellikler:
    - Query parametrelerine göre otomatik key oluşturma
    - Query invalidation (belirli tablolar değiştiğinde)
    """

    def __init__(self, max_size: int = 500, ttl_seconds: int = 30):
        self.cache = LRUCache(max_size, ttl_seconds)
        self._table_keys = {}  # {table_name: [cache_keys]}
        self._lock = threading.Lock()

    def _make_key(self, query: str, params: tuple = None) -> str:
        """
        Query + parametrelerden unique key oluştur

        Args:
            query: SQL query
            params: Query parametreleri

        Returns:
            SHA256 hash
        """
        # Query ve parametreleri JSON'a çevir
        data = {
            'query': query.strip().lower(),
            'params': params or ()
        }
        json_str = json.dumps(data, sort_keys=True)

        # Hash oluştur
        return hashlib.sha256(json_str.encode()).hexdigest()

    def get(self, query: str, params: tuple = None) -> Optional[Any]:
        """Query sonucunu cache'den çek"""
        key = self._make_key(query, params)
        return self.cache.get(key)

    def set(self, query: str, params: tuple, result: Any, affected_tables: list = None):
        """
        Query sonucunu cache'le

        Args:
            query: SQL query
            params: Query parametreleri
            result: Query sonucu
            affected_tables: Bu query hangi tabloları okuyor? (invalidation için)
        """
        key = self._make_key(query, params)
        self.cache.set(key, result)

        # Table mapping kaydet
        if affected_tables:
            with self._lock:
                for table in affected_tables:
                    if table not in self._table_keys:
                        self._table_keys[table] = set()
                    self._table_keys[table].add(key)

    def invalidate_table(self, table_name: str):
        """
        Belirli bir tabloya ait tüm cache'leri geçersiz kıl

        Kullanım:
            query_cache.invalidate_table('orders')  # orders değişti, tüm order cache'leri temizle
        """
        with self._lock:
            if table_name in self._table_keys:
                keys = self._table_keys[table_name]
                for key in keys:
                    self.cache.delete(key)
                del self._table_keys[table_name]

    def clear(self):
        """Tüm cache'i temizle"""
        self.cache.clear()
        with self._lock:
            self._table_keys.clear()

    def get_stats(self) -> dict:
        """Cache istatistiklerini döndür"""
        stats = self.cache.get_stats()
        stats['cached_tables'] = len(self._table_keys)
        return stats


def cached(cache_instance: LRUCache, ttl: int = None):
    """
    Fonksiyon sonucunu cache'leyen decorator

    Kullanım:
        @cached(order_cache, ttl=60)
        def get_orders():
            # Pahalı işlem
            return orders
    """
    def decorator(func: Callable):
        def wrapper(*args, **kwargs):
            # Key oluştur (fonksiyon adı + parametreler)
            key_data = {
                'func': func.__name__,
                'args': args,
                'kwargs': kwargs
            }
            key = hashlib.sha256(
                json.dumps(key_data, sort_keys=True, default=str).encode()
            ).hexdigest()

            # Cache'den dene
            result = cache_instance.get(key)
            if result is not None:
                return result

            # Miss - fonksiyonu çalıştır
            result = func(*args, **kwargs)

            # Cache'le
            cache_instance.set(key, result, ttl_seconds=ttl)

            return result

        return wrapper
    return decorator


# ============================================================================
# GLOBAL CACHE INSTANCE'LARI
# ============================================================================

# Genel amaçlı cache
general_cache = LRUCache(max_size=1000, ttl_seconds=60)

# Sipariş cache'i (sık erişilir)
order_cache = LRUCache(max_size=500, ttl_seconds=30)

# İstasyon cache'i (nadiren değişir)
station_cache = LRUCache(max_size=100, ttl_seconds=300)

# Query cache (SQL sorguları için)
query_cache = QueryCache(max_size=500, ttl_seconds=30)

# Production logs cache (orta sıklıkta değişir)
production_cache = LRUCache(max_size=200, ttl_seconds=15)
