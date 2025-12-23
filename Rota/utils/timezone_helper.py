"""
EFES ROTA X - Timezone Helper
Türkiye saati (UTC+3) için yardımcı fonksiyonlar
"""

from datetime import datetime, timedelta, timezone


# Türkiye zaman dilimi (UTC+3)
TURKEY_TZ = timezone(timedelta(hours=3))


def now_turkey():
    """
    Türkiye saatini döndürür (UTC+3)

    Returns:
        datetime: Türkiye saatine göre şu anki zaman
    """
    return datetime.now(TURKEY_TZ)


def get_current_date_turkey():
    """
    Türkiye saatine göre bugünün tarihini döndürür (sadece tarih)

    Returns:
        date: Bugünün tarihi (Türkiye saati)
    """
    return now_turkey().date()


def get_current_time_turkey():
    """
    Türkiye saatine göre şu anki saati döndürür (HH:MM:SS formatında)

    Returns:
        str: Şu anki saat
    """
    return now_turkey().strftime("%H:%M:%S")


def format_datetime_turkey(dt=None):
    """
    Datetime objesini Türkiye saatine çevirerek formatlar

    Args:
        dt: datetime objesi (None ise şu anki zaman)

    Returns:
        str: Formatlanmış tarih-saat (örn: "15.01.2025 14:30")
    """
    if dt is None:
        dt = now_turkey()
    elif dt.tzinfo is None:
        # Naive datetime ise Türkiye saati olarak varsay
        dt = dt.replace(tzinfo=TURKEY_TZ)
    else:
        # Başka timezone'dan geliyorsa Türkiye saatine çevir
        dt = dt.astimezone(TURKEY_TZ)

    return dt.strftime("%d.%m.%Y %H:%M")


def format_date_turkey(dt=None):
    """
    Date objesini Türkiye formatında döndürür

    Args:
        dt: datetime veya date objesi (None ise bugün)

    Returns:
        str: Formatlanmış tarih (örn: "15.01.2025")
    """
    if dt is None:
        dt = now_turkey()

    return dt.strftime("%d.%m.%Y")


def format_time_turkey(dt=None):
    """
    Time'ı Türkiye formatında döndürür

    Args:
        dt: datetime objesi (None ise şu anki zaman)

    Returns:
        str: Formatlanmış saat (örn: "14:30")
    """
    if dt is None:
        dt = now_turkey()

    return dt.strftime("%H:%M")
