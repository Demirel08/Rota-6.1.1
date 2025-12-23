# -*- coding: utf-8 -*-
"""
EFES ROTA X - PERFORMANS TEST SCRIPT
"""

import sys
import time
from datetime import datetime

sys.path.insert(0, 'c:\\Users\\okand\\Desktop\\Rota')

from core.db_manager import db
from core.smart_planner import planner

def timer_decorator(func):
    def wrapper(*args, **kwargs):
        start = time.perf_counter()
        result = func(*args, **kwargs)
        end = time.perf_counter()
        duration = (end - start) * 1000
        print(f"  [TIME] {func.__name__}: {duration:.2f} ms")
        return result, duration
    return wrapper

print("=" * 70)
print("EFES ROTA X - PERFORMANS ANALIZ RAPORU")
print("=" * 70)
print(f"Test Zamani: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
print()

# TEST 1: Dashboard Stats
print("TEST 1: DASHBOARD STATS")
print("-" * 70)

@timer_decorator
def test_db_stats():
    return db.get_dashboard_stats()

stats, duration1 = test_db_stats()
print(f"  Aktif: {stats['active']}, Acil: {stats['urgent']}, Fire: {stats['fire']}")
print()

# TEST 2: Get Orders
print("TEST 2: SIPARIS LISTESI")
print("-" * 70)

@timer_decorator
def test_get_orders():
    return db.get_orders_by_status(["Beklemede", "Uretimde"])

orders, duration2 = test_get_orders()
print(f"  Siparis sayisi: {len(orders)}")
print()

# TEST 3: Production Matrix (KRITIK)
print("TEST 3: PRODUCTION MATRIX (N+1 SORUNU)")
print("-" * 70)

@timer_decorator
def test_production_matrix():
    return db.get_production_matrix_advanced()

matrix_data, duration3 = test_production_matrix()
print(f"  Matris satir: {len(matrix_data)}")
print()

# TEST 4: Station Loads
print("TEST 4: STATION LOADS")
print("-" * 70)

@timer_decorator
def test_station_loads():
    return db.get_station_loads()

loads, duration4 = test_station_loads()
print(f"  Istasyon sayisi: {len(loads)}")
print()

# TEST 5: Smart Planner
print("TEST 5: SMART PLANNER")
print("-" * 70)

@timer_decorator
def test_smart_planner():
    if len(orders) > 0:
        return planner.optimize_production_sequence(orders[:20])
    return []

optimized, duration5 = test_smart_planner()
print(f"  Optimize edildi: {len(optimized)} siparis")
print()

# TEST 6: Timer Simulation
print("TEST 6: TIMER SIMULASYONU (5x refresh)")
print("-" * 70)

total_timer_cost = 0
for i in range(5):
    start = time.perf_counter()
    _ = db.get_orders_by_status(["Beklemede", "Uretimde"])
    _ = db.get_dashboard_stats()
    end = time.perf_counter()
    cost = (end - start) * 1000
    total_timer_cost += cost
    print(f"    Refresh {i+1}: {cost:.2f} ms")

avg_timer_cost = total_timer_cost / 5
print(f"  Ortalama: {avg_timer_cost:.2f} ms")
print()

# TEST 7: N+1 Problem Simulation
print("TEST 7: N+1 PROBLEM SIMULASYONU")
print("-" * 70)

test_order_count = min(len(orders), 50)
print(f"  Test: {test_order_count} siparis")

@timer_decorator
def test_n_plus_one():
    count = 0
    for order in orders[:test_order_count]:
        route = order.get('route', '')
        if route:
            stations = route.split(',')
            for station in stations:
                progress = db.get_station_progress(order['id'], station.strip())
                count += 1
    return count

query_count, duration7 = test_n_plus_one()
print(f"  Toplam sorgu: {query_count}")
if query_count > 0:
    print(f"  Ortalama: {duration7/query_count:.2f} ms per query")
print()

# SUMMARY
print("=" * 70)
print("PERFORMANS OZET RAPORU")
print("=" * 70)
print()

def score(ms, fast, medium):
    if ms < fast:
        return "OK"
    elif ms < medium:
        return "WARN"
    else:
        return "SLOW"

score1 = score(duration1, 50, 100)
score2 = score(duration2, 100, 200)
score3 = score(duration3, 200, 500)
score4 = score(duration4, 100, 300)
score5 = score(duration5, 500, 2000)
score6 = score(avg_timer_cost, 50, 150)
score7 = score(duration7, 500, 2000)

print(f"  1. Dashboard Stats     : {score1:<10} ({duration1:.2f} ms)")
print(f"  2. Get Orders          : {score2:<10} ({duration2:.2f} ms)")
print(f"  3. Production Matrix   : {score3:<10} ({duration3:.2f} ms)")
print(f"  4. Station Loads       : {score4:<10} ({duration4:.2f} ms)")
print(f"  5. Smart Planner       : {score5:<10} ({duration5:.2f} ms)")
print(f"  6. Timer Refresh       : {score6:<10} ({avg_timer_cost:.2f} ms)")
print(f"  7. N+1 Problem         : {score7:<10} ({duration7:.2f} ms)")
print()

slow_count = sum(1 for s in [score1, score2, score3, score4, score5, score6, score7] if s == "SLOW")
warn_count = sum(1 for s in [score1, score2, score3, score4, score5, score6, score7] if s == "WARN")

print("=" * 70)
print("GENEL SONUC")
print("=" * 70)
if slow_count > 0:
    print(f"  [CRITICAL] {slow_count} test basarisiz")
    print(f"  [WARNING] {warn_count} test iyilestirme gerekiyor")
    print()
    print("  ONERI: Acilen optimizasyon yapilmali!")
elif warn_count > 2:
    print(f"  [WARNING] {warn_count} test iyilestirme gerekiyor")
    print()
    print("  ONERI: Performans iyilestirmeleri yapilmali")
else:
    print("  [OK] Sistem performansi kabul edilebilir seviyede")

print()
print("=" * 70)
