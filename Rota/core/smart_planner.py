import math
from datetime import datetime, timedelta

try:
    from utils.timezone_helper import now_turkey, get_current_date_turkey
except ImportError:
    # Fallback: timezone_helper bulunamazsa normal datetime kullan
    from datetime import datetime as _dt
    now_turkey = lambda: _dt.now()
    get_current_date_turkey = lambda: _dt.now().date()
from collections import defaultdict

try:
    from core.db_manager import db
except ImportError:
    pass

class SmartPlanner:
    """
    AKILLI PLANLAMA MOTORU v18 (TAKVİM ENTEGRASYONLU) 🧠

    Yenilikler:
    - Thickness Factor (Kalınlık Katsayısı): Kapasiteler 4mm referans alınır.
      Kalınlık arttıkça günlük işleme kapasitesi düşürülür.
    - Look-ahead Window: Sadece yakın tarihli işler batch yapılır.
    - Factory Calendar Integration: Tatil günlerinde üretim yapılmaz,
      işler otomatik olarak sonraki çalışma gününe kayar.
    """

    def __init__(self):
        self.FORECAST_DAYS = 30 # 2 aylık projeksiyon
        self.BATCH_BONUS_SCORE = 5
        self.LOOKAHEAD_WINDOW = 30
        self.SIMULATION_WINDOW = 45  # Simülasyona sadece önümüzdeki 45 günlük siparişler dahil edilir 
        
        # --- KALINLIK KATSAYILARI (REFERANS: 4mm = 1.0) ---
        # Örnek: 10mm cam işlemek, 4mm cama göre %40 daha yavaştır (Katsayı 0.60)
        self.THICKNESS_FACTORS = {
            2: 1.0,
            3: 1.0,
            4: 1.00,  # REFERANS NOKTASI
            5: 0.95,
            6: 0.90,  # %10 Performans kaybı
            8: 0.80,  # %20 Performans kaybı
            10: 0.60, # %40 Performans kaybı
            12: 0.50, # Yarı yarıya düşer
            15: 0.40,
            19: 0.30, # Çok yavaş
        }
        # Listede olmayan çok kalın camlar için varsayılan katsayı
        self.DEFAULT_FACTOR = 0.50
        
        try:
            self.capacities = db.get_all_capacities()
            if not self.capacities: raise ValueError
        except:
            self.capacities = {} 
        
        self.station_order = [
            "INTERMAC", "LIVA KESIM", "LAMINE KESIM",
            "CNC RODAJ", "DOUBLEDGER", "ZIMPARA",
            "TESIR A1", "TESIR B1", "TESIR B1-1", "TESIR B1-2",
            "DELİK", "OYGU",
            "TEMPER A1", "TEMPER B1", "TEMPER BOMBE",
            "LAMINE A1", "ISICAM B1",
            "SEVKİYAT"
        ]

    def _parse_date(self, date_str):
        if not date_str: return datetime.max.date()
        try:
            return datetime.strptime(date_str, '%Y-%m-%d').date()
        except:
            return datetime.max.date()

    def _get_capacity_coefficient(self, thickness):
        """Kalınlığa göre kapasite çarpanını döndürür"""
        try:
            t_int = int(float(thickness))
            return self.THICKNESS_FACTORS.get(t_int, self.DEFAULT_FACTOR)
        except:
            return 1.0 # Hata durumunda 4mm gibi davran

    def _is_working_day(self, day_offset):
        """
        Hafta sonu kontrolü (Cumartesi=5, Pazar=6 tatil)
        day_offset: Bugünden itibaren kaç gün sonra (int)
        """
        try:
            target_date = now_turkey().date() + timedelta(days=day_offset)
            # 5=Cumartesi, 6=Pazar
            return target_date.weekday() not in [5, 6]
        except:
            return True

    def optimize_production_sequence(self, orders):
        """
        Gelişmiş Fabrika Sıralama Algoritması
        """
        red_orders = []      # Acil / Gecikmiş
        green_orders = []    # Yakın tarihli Normal
        grey_orders = []     # Uzak tarihli Normal
        
        today = now_turkey().date()
        window_limit = today + timedelta(days=self.LOOKAHEAD_WINDOW)
        
        # 1. AYRIŞTIRMA
        for order in orders:
            due_date = self._parse_date(order.get('delivery_date'))
            days_left = (due_date - today).days
            priority = order.get('priority', 'Normal')
            
            # Kriter 1: KIRMIZI HAT
            if (days_left < 2) or (priority in ['Kritik', 'Çok Acil']):
                red_orders.append(order)
            
            # Kriter 2: YEŞİL HAT
            elif due_date <= window_limit:
                green_orders.append(order)
                
            # Kriter 3: GRİ HAT
            else:
                grey_orders.append(order)
                
        # --- KIRMIZI HAT SIRALAMASI ---
        priority_map = {"Kritik": 0, "Çok Acil": 1, "Acil": 2, "Normal": 3}
        red_orders.sort(key=lambda x: (
            priority_map.get(x.get('priority', 'Normal'), 3),
            x.get('delivery_date', '9999-12-31')
        ))
        
        # --- YEŞİL HAT GRUPLAMASI (BATCHING) ---
        batches = defaultdict(list)
        for order in green_orders:
            key = (order.get('thickness'), order.get('product_type'))
            batches[key].append(order)
            
        scored_batches = []
        for key, batch_list in batches.items():
            avg_days = sum([(self._parse_date(o.get('delivery_date')) - today).days for o in batch_list]) / len(batch_list)
            batch_score = (len(batch_list) * self.BATCH_BONUS_SCORE) - (avg_days * 2)
            
            batch_list.sort(key=lambda x: x.get('delivery_date', '9999-12-31'))
            
            scored_batches.append({
                'score': batch_score,
                'orders': batch_list
            })
            
        scored_batches.sort(key=lambda x: x['score'], reverse=True)
        
        # --- GRİ HAT SIRALAMASI ---
        grey_orders.sort(key=lambda x: x.get('delivery_date', '9999-12-31'))
        
        # 4. LİSTELERİ BİRLEŞTİR
        final_sequence = []
        final_sequence.extend(red_orders)
        for batch in scored_batches:
            final_sequence.extend(batch['orders'])
        final_sequence.extend(grey_orders)
            
        return final_sequence

    def _run_simulation(self, new_order=None):
        # 1. Mevcut İşleri Çek
        active_orders = db.get_orders_by_status(["Beklemede", "Üretimde"])

        # PERFORMANS OPTİMİZASYONU: Sadece önümüzdeki 45 günlük siparişleri simülasyona sok
        today = now_turkey().date()
        simulation_deadline = today + timedelta(days=self.SIMULATION_WINDOW)

        filtered_orders = []
        for order in active_orders:
            due_date = self._parse_date(order.get('delivery_date'))
            # Termin tarihi 45 gün içindeyse veya termin tarihi yoksa/geçersizse simülasyona dahil et
            if due_date <= simulation_deadline or due_date == datetime.max.date():
                filtered_orders.append(order)

        active_orders = filtered_orders

        # PERFORMANS KRİTİK: Tüm progress verilerini tek seferde yükle
        progress_cache = {}  # {order_id: {station: completed_qty}}
        completed_cache = {}  # {order_id: [completed_stations]}

        if active_orders:
            try:
                # Tüm order ID'lerini topla
                order_ids = [o['id'] for o in active_orders if 'id' in o]

                # Tek sorguda tüm production_logs'u çek
                with db.get_connection() as conn:
                    # Progress verileri
                    rows = conn.execute("""
                        SELECT order_id, station_name, SUM(quantity) as total
                        FROM production_logs
                        WHERE order_id IN ({}) AND action = 'Tamamlandi'
                        GROUP BY order_id, station_name
                    """.format(','.join('?' * len(order_ids))), order_ids).fetchall()

                    for row in rows:
                        oid = row[0]
                        station = row[1]
                        qty = row[2] or 0

                        if oid not in progress_cache:
                            progress_cache[oid] = {}
                        progress_cache[oid][station] = qty

                    # Completed stations hesapla
                    for order in active_orders:
                        if 'id' not in order:
                            continue
                        oid = order['id']
                        target_qty = order.get('quantity', 0)
                        completed = []

                        if oid in progress_cache:
                            for station, done_qty in progress_cache[oid].items():
                                if done_qty >= target_qty:
                                    completed.append(station)

                        completed_cache[oid] = completed
            except:
                pass  # Hata durumunda boş cache ile devam et
        
        # 2. Yeni Siparişi Ekle
        if new_order:
            simulated_order = {
                'id': -1,
                'order_code': '>>> HESAPLANAN <<<',
                'customer_name': 'YENİ',
                'width': new_order.get('width', 0),
                'height': new_order.get('height', 0),
                'quantity': new_order.get('quantity', 0),
                'declared_total_m2': new_order.get('total_m2', 0),
                'thickness': new_order.get('thickness', 0),
                'product_type': new_order.get('product', ''),
                'route': new_order.get('route', ''),
                'priority': new_order.get('priority', 'Normal'),
                'delivery_date': new_order.get('date', '9999-12-31'),
                'is_new': True 
            }
            active_orders.append(simulated_order)

        # 3. YENİ OPTİMİZE SIRALAMA
        active_orders = self.optimize_production_sequence(active_orders)

        # 4. SİMÜLASYON DEĞİŞKENLERİ
        forecast_grid = {k: [0.0]*self.FORECAST_DAYS for k in self.capacities.keys()}
        loads_grid = {k: [0.0]*self.FORECAST_DAYS for k in self.capacities.keys()}
        details_grid = {k: [[] for _ in range(self.FORECAST_DAYS)] for k in self.capacities.keys()}
        machine_free_time = {k: 0.0 for k in self.capacities.keys()}
        
        order_finish_times = {} 
        target_finish_day = 0

        # 5. MOTOR ÇALIŞIYOR
        for order in active_orders:
            m2 = order.get('declared_total_m2', 0)
            if not m2 or m2 <= 0:
                w = order.get('width', 0)
                h = order.get('height', 0)
                q = order.get('quantity', 0)
                if w and h and q: m2 = (w * h * q) / 10000.0
            
            if m2 <= 0: continue
            
            total_qty = order.get('quantity', 1)
            route_str = order.get('route', '')
            route_steps = route_str.split(',')
            thickness = order.get('thickness', 4)
            
            # --- KRİTİK NOKTA: KALINLIK KATSAYISINI AL ---
            capacity_factor = self._get_capacity_coefficient(thickness)
            
            completed_stops = []
            if not order.get('is_new'):
                # Cache'den oku (DB'ye gitme)
                completed_stops = completed_cache.get(order.get('id'), [])
            
            current_order_ready_time = 0.0 
            
            for station in route_steps:
                station = station.strip()
                if station not in self.capacities: continue
                if station in completed_stops: continue 

                # Teorik Günlük Kapasite (4mm için)
                base_daily_cap = self.capacities[station]
                if base_daily_cap <= 0: base_daily_cap = 1
                
                # --- GERÇEK KAPASİTE HESABI ---
                # Örn: 1000 m2 (4mm) * 0.6 (10mm katsayısı) = 600 m2 (Gerçek Kapasite)
                effective_daily_cap = base_daily_cap * capacity_factor
                
                done_qty = 0
                if not order.get('is_new'):
                    # Cache'den oku (DB'ye gitme)
                    oid = order.get('id')
                    if oid in progress_cache and station in progress_cache[oid]:
                        done_qty = progress_cache[oid][station]
                
                remaining_ratio = 1.0 - (done_qty / total_qty)
                if remaining_ratio <= 0: continue

                remaining_m2 = m2 * remaining_ratio
                
                # Süre Hesabı: m2 / Gerçek Kapasite
                duration_days = remaining_m2 / effective_daily_cap

                start_day = max(current_order_ready_time, machine_free_time[station])

                # Hafta sonlarını atla
                remaining_work = duration_days
                current_day = start_day
                max_iterations = self.FORECAST_DAYS * 2  # Sonsuz döngü önleme

                iteration = 0
                while remaining_work > 0 and iteration < max_iterations:
                    iteration += 1
                    day_idx = int(current_day)

                    if day_idx >= self.FORECAST_DAYS:
                        break

                    # Bu gün çalışma günü mü? (Hafta sonu değil mi?)
                    if self._is_working_day(day_idx):
                        # Çalışma günü - iş yapılabilir
                        # Bir günde ne kadar iş yapabiliriz?
                        day_end = day_idx + 1
                        available_time_in_day = day_end - current_day
                        work_amount = min(available_time_in_day, remaining_work)

                        # Doluluk Yüzdesi (Zaman bazlı)
                        forecast_grid[station][day_idx] += (work_amount * 100)

                        # Yük Miktarı (m2 bazlı)
                        loads_grid[station][day_idx] += (work_amount * effective_daily_cap)

                        info = {
                            "code": order['order_code'],
                            "customer": order.get('customer_name', 'Tahmini'),
                            "m2": remaining_m2,
                            "batch": f"{thickness}mm",
                            "notes": order.get('notes', '')
                        }
                        exists = any(x['code'] == info['code'] for x in details_grid[station][day_idx])
                        if not exists:
                            details_grid[station][day_idx].append(info)

                        remaining_work -= work_amount
                        current_day += work_amount
                    else:
                        # Hafta sonu - bir gün atla
                        current_day = day_idx + 1

                end_day = current_day

                machine_free_time[station] = end_day
                current_order_ready_time = end_day
            
            order_finish_times[order.get('order_code')] = current_order_ready_time
            if order.get('is_new'):
                target_finish_day = current_order_ready_time

        return forecast_grid, details_grid, loads_grid, target_finish_day, order_finish_times

    def calculate_forecast(self):
        try: self.capacities = db.get_all_capacities()
        except: pass
        grid, details, loads, _, _ = self._run_simulation(new_order=None)
        return grid, details, loads

    def calculate_impact(self, new_order_data):
        try: self.capacities = db.get_all_capacities()
        except: pass
        _, _, _, _, base_finish_times = self._run_simulation(new_order=None)
        _, _, _, target_day, new_finish_times = self._run_simulation(new_order=new_order_data)
        
        delayed_orders = []
        for code, base_time in base_finish_times.items():
            if code in new_finish_times:
                new_time = new_finish_times[code]
                if (new_time - base_time) > 0.1:
                    delayed_orders.append({
                        "code": code,
                        "delay": math.ceil(new_time - base_time),
                        "old_day": math.ceil(base_time),
                        "new_day": math.ceil(new_time)
                    })

        today = now_turkey()
        delivery_date = today + timedelta(days=math.ceil(target_day))
        return delivery_date, math.ceil(target_day), delayed_orders

    def fix_route_order(self, user_route_str):
        if not user_route_str: return ""
        selected = [s.strip() for s in user_route_str.split(',')]
        sorted_route = []
        for station in self.station_order:
            if station in selected:
                sorted_route.append(station)
        return ",".join(sorted_route)

    def get_weekly_plan(self):
        """
        Gelecek 7 gün için haftalık üretim planı oluşturur.
        Returns: {date_str: [order_list]}
        """
        try:
            # Aktif siparişleri çek
            active_orders = db.get_orders_by_status(["Beklemede", "Uretimde"], respect_manual_order=True)

            # Simülasyonu çalıştır
            forecast_grid, details_grid, loads_grid, _, order_finish_times = self._run_simulation()

            # Haftalık plan oluştur (bugünden itibaren 7 gün)
            weekly_plan = {}
            today = now_turkey().date()

            # Sipariş kodlarına göre tam bilgiyi sakla
            order_map = {o.get('order_code'): o for o in active_orders}

            for day_offset in range(7):
                target_date = today + timedelta(days=day_offset)
                date_str = target_date.strftime('%Y-%m-%d')

                # Bu gün için işleri topla
                daily_jobs = []
                seen_codes = set()

                # Her istasyondaki işleri kontrol et
                for station in self.station_order:
                    if station in details_grid and day_offset < len(details_grid[station]):
                        jobs_at_station = details_grid[station][day_offset]

                        for job in jobs_at_station:
                            order_code = job.get('code', '-')

                            # Aynı siparişi tekrar ekleme
                            if order_code not in seen_codes:
                                seen_codes.add(order_code)

                                # Sipariş detaylarını veritabanından çek
                                order_detail = order_map.get(order_code, {})

                                daily_jobs.append({
                                    'code': order_code,
                                    'customer': job.get('customer', order_detail.get('customer_name', '-')),
                                    'product': order_detail.get('product_type', job.get('batch', '-')),
                                    'm2': order_detail.get('declared_total_m2', job.get('m2', 0)),
                                    'route': order_detail.get('route', ''),
                                    'notes': order_detail.get('notes', job.get('notes', ''))
                                })

                weekly_plan[date_str] = daily_jobs

            return weekly_plan

        except Exception as e:
            print(f"Haftalık plan hatası: {e}")
            import traceback
            traceback.print_exc()
            return {}

planner = SmartPlanner()