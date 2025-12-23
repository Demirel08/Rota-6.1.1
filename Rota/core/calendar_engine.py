from datetime import datetime, timedelta
try:
    from core.db_manager import db
except ImportError:
    db = None

class CalendarEngine:
    """
    Fabrika Takvim Motoru
    Tatilleri ve hafta sonlarını atlayarak gerçekçi tarih hesaplar.
    """
    
    @staticmethod
    def is_work_day(date_obj):
        """O gün fabrika açık mı?"""
        date_str = date_obj.strftime("%Y-%m-%d")
        
        # 1. Veritabanına bak (Kullanıcı özel ayar yaptı mı?)
        if db:
            is_holiday = db.get_calendar_status(date_str)
            if is_holiday:
                return False # Veritabanında 'Tatil' denmiş
        
        # 2. (Opsiyonel) Varsayılan Hafta Sonu Kuralı
        # Kullanıcı "Her şeyi ben girmek istiyorum" dediği için burayı kapalı tutuyorum.
        # İsterseniz Pazar günlerini (6) otomatik tatil yapabiliriz:
        # if date_obj.weekday() == 6: return False 
        
        return True

    @staticmethod
    def add_work_days(start_date, duration_days):
        """
        Bir tarihe 'X iş günü' ekler.
        Örnek: Cuma + 2 iş günü = Salı (Cmt-Paz atlanır)
        """
        if isinstance(start_date, str):
            current_date = datetime.strptime(start_date, "%Y-%m-%d").date()
        else:
            current_date = start_date
            
        days_left = duration_days
        
        # Süre bitene kadar gün gün ilerle
        while days_left > 0:
            current_date += timedelta(days=1)
            
            if CalendarEngine.is_work_day(current_date):
                days_left -= 1 # Çalışma günü ise sayaçtan düş
            else:
                pass # Tatilse sayacı düşme, takvim ilerlesin
                
        return current_date

    @staticmethod
    def count_work_days(start_date, end_date):
        """İki tarih arasındaki iş günü sayısını bulur"""
        # (Dashboard'da "3 iş günü kaldı" demek için lazım olacak)
        days = 0
        curr = start_date
        while curr < end_date:
            curr += timedelta(days=1)
            if CalendarEngine.is_work_day(curr):
                days += 1
        return days