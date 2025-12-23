"""
ETKİ ANALİZİ MOTORU

Sipariş öncelik değişikliklerinin diğer siparişlere etkisini analiz eder.
What-If senaryoları üretir ve karar destek sağlar.

Özellikler:
- Simülasyon tabanlı etki analizi
- Tahmini teslim tarihi karşılaştırması
- Gecikme/Erken teslim hesaplama
- Kritik sipariş tespiti
"""

from datetime import datetime, timedelta
from typing import List, Dict, Optional
from copy import deepcopy

try:
    from utils.timezone_helper import now_turkey, get_current_date_turkey
except ImportError:
    from datetime import datetime as _dt
    now_turkey = lambda: _dt.now()
    get_current_date_turkey = lambda: _dt.now().date()


class ImpactAnalyzer:
    """Sipariş değişikliklerinin etkisini analiz eden motor"""

    def __init__(self, planner=None, cr_calculator=None):
        """
        Args:
            planner: SmartPlanner instance (core/smart_planner.py)
            cr_calculator: CriticalRatioCalculator instance
        """
        self.planner = planner
        self.cr_calculator = cr_calculator

    def analyze_reorder_impact(
        self,
        all_orders: List[Dict],
        selected_order_id: int,
        new_position: int
    ) -> Dict:
        """
        Bir siparişin sırasını değiştirmenin etkisini analiz et

        Args:
            all_orders: Tüm siparişler listesi (mevcut sıralama)
            selected_order_id: Değiştirilecek siparişin ID'si
            new_position: Yeni pozisyon (0-based index)

        Returns:
            {
                'affected_orders': [
                    {
                        'order': {...},
                        'old_completion_date': datetime,
                        'new_completion_date': datetime,
                        'diff_days': int,  # pozitif = gecikme, negatif = erken
                        'severity': 'critical'|'warning'|'improved'|'neutral',
                        'exceeds_deadline': bool
                    },
                    ...
                ],
                'summary': {
                    'total_affected': int,
                    'delayed_count': int,
                    'improved_count': int,
                    'deadline_exceeded_count': int
                }
            }
        """

        if not self.planner:
            return {'error': 'Planner not available'}

        # 1. Seçili siparişi bul
        selected_order = None
        selected_index = None
        for i, order in enumerate(all_orders):
            if order.get('id') == selected_order_id:
                selected_order = order
                selected_index = i
                break

        if selected_order is None:
            return {'error': 'Sipariş bulunamadı'}

        # 2. Mevcut durumu analiz et (Before)
        current_snapshot = self._calculate_completion_dates(all_orders)

        # 3. Yeni sıralamayı oluştur
        new_orders = all_orders.copy()
        new_orders.pop(selected_index)
        new_orders.insert(new_position, selected_order)

        # 4. Yeni durumu analiz et (After)
        new_snapshot = self._calculate_completion_dates(new_orders)

        # 5. Farkları hesapla
        affected_orders = []

        for order_id, current_date in current_snapshot.items():
            new_date = new_snapshot.get(order_id)

            if new_date is None or current_date is None:
                continue

            # Fark var mı?
            if current_date != new_date:
                order_data = self._find_order_by_id(all_orders, order_id)
                if not order_data:
                    continue

                diff_days = (new_date - current_date).days
                delivery_date = self._parse_date(order_data.get('delivery_date'))
                exceeds_deadline = new_date.date() > delivery_date if delivery_date else False

                # Önem derecesi belirle
                if exceeds_deadline:
                    severity = 'critical'  # Termin tarihi aşıldı
                elif diff_days > 3:
                    severity = 'critical'  # 3+ gün gecikme
                elif diff_days > 0:
                    severity = 'warning'   # Küçük gecikme
                elif diff_days < -3:
                    severity = 'improved'  # Önemli iyileşme
                elif diff_days < 0:
                    severity = 'improved'  # Küçük iyileşme
                else:
                    severity = 'neutral'

                affected_orders.append({
                    'order': order_data,
                    'old_completion_date': current_date,
                    'new_completion_date': new_date,
                    'diff_days': diff_days,
                    'severity': severity,
                    'exceeds_deadline': exceeds_deadline
                })

        # 6. Özet istatistikler
        delayed_count = sum(1 for x in affected_orders if x['diff_days'] > 0)
        improved_count = sum(1 for x in affected_orders if x['diff_days'] < 0)
        deadline_exceeded_count = sum(1 for x in affected_orders if x['exceeds_deadline'])

        # 7. Önem derecesine göre sırala (kritik önce)
        severity_order = {'critical': 0, 'warning': 1, 'improved': 2, 'neutral': 3}
        affected_orders.sort(key=lambda x: (severity_order[x['severity']], -abs(x['diff_days'])))

        return {
            'affected_orders': affected_orders,
            'summary': {
                'total_affected': len(affected_orders),
                'delayed_count': delayed_count,
                'improved_count': improved_count,
                'deadline_exceeded_count': deadline_exceeded_count
            }
        }

    def _calculate_completion_dates(self, orders: List[Dict]) -> Dict[int, datetime]:
        """
        Tüm siparişler için tahmini tamamlanma tarihlerini hesapla
        ÖNEMLI: Sipariş sırasını dikkate alarak kümülatif hesaplama yapar

        Returns:
            {order_id: completion_date, ...}
        """
        completion_dates = {}

        # Basit birikimli hesaplama: Her sipariş bir öncekinden sonra tamamlanır
        # Varsayım: Her sipariş ortalama 2 gün sürer
        current_date = now_turkey()

        for index, order in enumerate(orders):
            order_id = order.get('id')
            if not order_id:
                continue

            # İşlem süresi tahmini (m2'ye göre)
            m2 = order.get('declared_total_m2', 10)
            # Basit formül: Her 50 m2 için 1 gün
            processing_days = max(1, int(m2 / 50))

            # Kümülatif tarih: Bir önceki siparişten sonra başlar
            if index == 0:
                # İlk sipariş bugünden başlar
                start_date = current_date
            else:
                # Diğer siparişler bir önceki siparişin bitiminden sonra başlar
                prev_order_id = orders[index - 1].get('id')
                if prev_order_id in completion_dates:
                    start_date = completion_dates[prev_order_id]
                else:
                    start_date = current_date + timedelta(days=index * 2)

            # Bu siparişin tamamlanma tarihi
            completion_dates[order_id] = start_date + timedelta(days=processing_days)

        return completion_dates

    def _find_order_by_id(self, orders: List[Dict], order_id: int) -> Optional[Dict]:
        """ID'ye göre sipariş bul"""
        for order in orders:
            if order.get('id') == order_id:
                return order
        return None

    def _parse_date(self, date_str: str) -> Optional[datetime.date]:
        """String tarih parse et"""
        if not date_str:
            return None
        try:
            return datetime.strptime(date_str, '%Y-%m-%d').date()
        except:
            return None

    def analyze_priority_change(
        self,
        all_orders: List[Dict],
        order_id: int,
        new_priority: str
    ) -> Dict:
        """
        Öncelik değişikliginin etkisini analiz et

        Args:
            all_orders: Tüm siparişler
            order_id: Değiştirilecek siparişin ID'si
            new_priority: Yeni öncelik ('Normal', 'Acil', 'Çok Acil', 'Kritik')

        Returns:
            Analyze_reorder_impact ile aynı format
        """
        # Öncelik değişikliği sıralama değişikliği demektir
        # Yeni önceliğe göre yeniden sırala

        # 1. Siparişi bul ve önceliğini değiştir
        orders_copy = deepcopy(all_orders)
        for order in orders_copy:
            if order.get('id') == order_id:
                order['priority'] = new_priority
                break

        # 2. Yeni önceliğe göre sırala
        priority_map = {"Kritik": 1, "Çok Acil": 2, "Acil": 3, "Normal": 4}
        orders_copy.sort(
            key=lambda x: (
                priority_map.get(x.get('priority', 'Normal'), 4),
                x.get('delivery_date', '9999-12-31')
            )
        )

        # 3. Yeni sıralamadaki pozisyonu bul
        new_position = None
        for i, order in enumerate(orders_copy):
            if order.get('id') == order_id:
                new_position = i
                break

        # 4. Reorder impact analizini kullan
        if new_position is not None:
            return self.analyze_reorder_impact(all_orders, order_id, new_position)

        return {'error': 'Yeni pozisyon belirlenemedi'}
