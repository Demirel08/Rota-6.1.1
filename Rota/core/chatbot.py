"""
EFES ROTA X - Akıllı Asistan Motoru (Rule-Based Chatbot)
Yapay zeka kullanmadan, anahtar kelime ve veri analizi ile akıllı cevaplar üretir.

v3.0 Güncellemeler:
- Müşteri ismi ile sipariş arama
- Sipariş durumu ile filtreleme
- Konuşma geçmişi (context) desteği
- Çoklu sonuç listesi
- Akıllı öneri sistemi
"""

import re
from datetime import datetime, timedelta

try:
    from core.db_manager import db
except ImportError:
    try:
        from db_manager import db
    except ImportError:
        db = None

try:
    from utils.timezone_helper import now_turkey
except ImportError:
    # Fallback: timezone_helper bulunamazsa normal datetime kullan
    now_turkey = lambda: datetime.now()


class RotaBot:
    def __init__(self):
        self.bot_name = "Rota Asistan"
        self.last_order_code = None  # Son sorgulanan sipariş
        self.last_customer = None     # Son sorgulanan müşteri
        self.conversation_history = [] # Konuşma geçmişi
        
    def get_greeting(self):
        """Açılış mesajı ve hızlı butonlar"""
        hour = now_turkey().hour
        if hour < 12:
            greeting = "Günaydın"
        elif hour < 18:
            greeting = "İyi günler"
        else:
            greeting = "İyi akşamlar"

        return {
            "text": f"{greeting}! Ben **Rota Asistan** 🤖\n\n**Akıllı Bilgi Asistanınız**\n\n**🔍 SORGULAMA YAPABİLİRSİNİZ:**\n\n**Sipariş Takip:**\n• Sipariş kodu: \"ABC-001\"\n• Müşteri: \"Ahmet\", \"Cam Evi\"\n• Durum: \"Gecikenler\", \"Bekleyenler\"\n\n**Üretim Bilgisi:**\n• \"TEMPER işleri\" → Makine kuyruğu\n• \"Makine durumu\" → İstasyon yükleri\n• \"Fire raporu\" → Hata analizi\n\n**Raporlar:**\n• \"Günlük özet\" → Bugünün durumu\n• \"Stok durumu\" → Depo bilgisi\n• \"İstatistikler\" → Genel durum\n\n💡 **Doğal dil kullanın, sorularınızı yazın!**",
            "buttons": [
                "📦 Sipariş Ara",
                "👤 Müşteri",
                "🏭 Makineler",
                "⚠️ Gecikenler",
                "📊 Özet"
            ]
        }

    def process_message(self, user_message):
        """Kullanıcı mesajını analiz eder ve cevap üretir"""
        if not user_message:
            return self.get_greeting()

        # Orijinal mesajı sakla (büyük/küçük harf korunacak)
        original_msg = user_message.strip()

        # Konuşma geçmişine ekle
        self.conversation_history.append({
            'role': 'user',
            'message': original_msg,
            'timestamp': now_turkey()
        })

        # Türkçe karakterleri koruyarak lowercase yap
        msg = self._turkish_lower(original_msg)

        # 1. YARDIM
        if self._contains_any(msg, ['yardım', 'yardim', 'help', 'ne yapabilirsin', 'neler sorabilir']):
            return self._handle_help()

        # 2. MÜŞTERİ İSMİ İLE ARAMA (YENİ!)
        customer_result = self._try_find_by_customer(original_msg)
        if customer_result:
            return customer_result

        # 3. DURUM BAZLI ARAMA (YENİ!)
        status_result = self._try_find_by_status(msg)
        if status_result:
            return status_result

        # 3.5. MAKİNE BAZLI SİPARİŞ ARAMA (YENİ!)
        machine_orders = self._try_find_by_machine(msg)
        if machine_orders:
            return machine_orders

        # 4. SİPARİŞ SORGULAMA - Önce veritabanında ara
        order_result = self._try_find_order(original_msg)
        if order_result:
            return order_result

        # 5. MAKİNE / İSTASYON DURUMU
        if self._contains_any(msg, ['makine', 'istasyon', 'doluluk', 'yogunluk', 'yoğunluk', 'kapasite', 'dolu', 'bos', 'boş']):
            return self._handle_machine_query()

        # 6. STOK SORGUSU
        if self._contains_any(msg, ['stok', 'depo', 'kritik stok', 'malzeme', 'hammadde']):
            return self._handle_stock_query()

        # 7. FİRE / HATA RAPORU
        if self._contains_any(msg, ['fire', 'kırık', 'kirik', 'hata', 'hasar', 'rework']):
            return self._handle_fire_query()

        # 8. GECİKEN İŞLER
        if self._contains_any(msg, ['gecik', 'gecikmis', 'gecikmiş', 'yetiş', 'yetis', 'acil']):
            return self._handle_overdue_query()

        # 9. BUGÜN / GÜNLÜK ÖZET
        if self._contains_any(msg, ['bugün', 'bugun', 'günlük', 'gunluk', 'özet', 'ozet', 'today']):
            return self._handle_today_summary()

        # 10. İSTATİSTİK
        if self._contains_any(msg, ['istatistik', 'toplam', 'kaç', 'kac', 'sayı', 'sayi', 'genel durum']):
            return self._handle_stats_query()

        # 11. PROJE
        if self._contains_any(msg, ['proje', 'project']):
            return self._handle_project_query()

        # 12. SİPARİŞ ANAHTAR KELİMESİ (kod bulunamadıysa)
        if self._contains_any(msg, ['sipariş', 'siparis', 'order', 'nerede', 'durum']):
            return self._handle_order_search_prompt()

        # ANLAŞILAMADI - Akıllı öneriler sun
        return self._handle_unknown_with_suggestions(msg)

    # =========================================================================
    # YARDIMCI METODLAR
    # =========================================================================

    def _turkish_lower(self, text):
        """Türkçe karakterleri koruyarak lowercase yapar"""
        replacements = {
            'I': 'ı', 'İ': 'i',
            'Ğ': 'ğ', 'Ü': 'ü',
            'Ş': 'ş', 'Ö': 'ö',
            'Ç': 'ç'
        }
        for old, new in replacements.items():
            text = text.replace(old, new)
        return text.lower()
    
    def _contains_any(self, text, keywords):
        """Metinde herhangi bir anahtar kelime var mı kontrol eder"""
        return any(kw in text for kw in keywords)
    
    def _try_find_order(self, msg):
        """Mesajdaki her kelimeyi veritabanında sipariş kodu olarak arar"""
        if not db:
            return None

        # "ne durumda", "nerede", "hangi aşamada" gibi sorular için context-aware arama
        lower_msg = self._turkish_lower(msg)
        asking_about_last = False
        if self._contains_any(lower_msg, ['ne durumda', 'nerede', 'hangi aşamada', 'hangi asamada', 'durumu ne']):
            # Son sorgulanan siparişi kontrol et
            if self.last_order_code:
                asking_about_last = True
                try:
                    order = db.get_order_by_code(self.last_order_code)
                    if order:
                        return self._format_order_response(order)
                except:
                    pass

        # Mesajı kelimelere ayır
        # Noktalama işaretlerini temizle ama tire/alt çizgi koru
        clean_msg = re.sub(r'[^\w\s\-_]', ' ', msg)
        words = clean_msg.split()

        # Her kelimeyi dene
        for word in words:
            if len(word) < 2:  # Çok kısa kelimeleri atla
                continue

            # Büyük harfe çevir ve veritabanında ara
            code = word.upper()
            try:
                order = db.get_order_by_code(code)
                if order:
                    self.last_order_code = code
                    return self._format_order_response(order)
            except:
                pass

            # Orijinal haliyle de dene
            try:
                order = db.get_order_by_code(word)
                if order:
                    self.last_order_code = word
                    return self._format_order_response(order)
            except:
                pass

        # Eğer context-aware sorgu ise ama sipariş bulunamadıysa
        if asking_about_last and self.last_order_code:
            return {
                "text": f"🔍 Son sorgulanan sipariş: **{self.last_order_code}**\n\nAncak veritabanında bulunamadı. Sipariş kodu değişmiş olabilir.",
                "buttons": ["📦 Başka Sipariş", "📊 Özet"]
            }

        return None
    
    def _format_order_response(self, order):
        """Sipariş bilgilerini formatlar"""
        # Güvenli alan erişimi
        code = order.get('code') or order.get('order_code', 'N/A')
        status = order.get('status', 'Bilinmiyor')
        customer = order.get('customer') or order.get('customer_name', 'Müşteri')
        date = order.get('date') or order.get('delivery_date', '')
        product = order.get('product') or order.get('product_type', '')
        thickness = order.get('thickness', '')
        quantity = order.get('quantity', 0)
        total_m2 = order.get('total_m2') or order.get('declared_total_m2', 0) or 0
        route = order.get('route', '')
        order_id = order.get('id')
        
        # Zaman analizi
        time_msg = ""
        if date:
            days_left = self._days_until(date)
            if days_left is not None:
                if days_left < 0:
                    time_msg = f"🚨 {abs(days_left)} gün GECİKMİŞ!"
                elif days_left == 0:
                    time_msg = "⚠️ Teslim tarihi BUGÜN"
                elif days_left <= 3:
                    time_msg = f"⏰ Teslime {days_left} gün kaldı"
                else:
                    time_msg = f"📅 Teslime {days_left} gün var"
            else:
                time_msg = f"📅 Termin: {self._format_date(date)}"

        # Durum ikonu
        status_icons = {
            "Beklemede": "⏳",
            "Üretimde": "🔄",
            "Tamamlandı": "✅",
            "Sevk Edildi": "🚚"
        }
        status_icon = status_icons.get(status, "📋")
        
        # İstasyon ilerlemesi
        progress_msg = ""
        if route and order_id:
            stations = [s.strip() for s in route.split(',') if s.strip()]
            try:
                completed = db.get_completed_stations_list(order_id)
                if completed is None:
                    completed = []
                done_count = len(completed)
                total_count = len(stations)
                if total_count > 0:
                    progress_msg = f"\n\n🏭 İlerleme: {done_count}/{total_count} istasyon"
                    if completed:
                        progress_msg += f"\n✓ {', '.join(completed)}"
                    # Sıradaki istasyon
                    remaining = [s for s in stations if s not in completed]
                    if remaining:
                        progress_msg += f"\n➡️ Sırada: {remaining[0]}"
            except Exception as e:
                pass

        # Ürün bilgisi
        product_info = ""
        if thickness and product:
            product_info = f"{thickness}mm {product}"
        elif product:
            product_info = product
        elif thickness:
            product_info = f"{thickness}mm cam"

        response_text = f"""📄 **{code}**

👤 Müşteri: {customer}
📦 Ürün: {product_info}
🔢 Miktar: {quantity} adet ({total_m2:.1f} m²)

{status_icon} Durum: **{status}**
{time_msg}{progress_msg}"""

        buttons = []
        if status == "Beklemede":
            buttons = ["🔄 Üretimdekiler", "⚠️ Gecikenler"]
        elif status == "Üretimde":
            buttons = ["⚠️ Gecikenler", "📊 Günlük Özet"]
        elif status == "Tamamlandı":
            buttons = ["🚚 Sevkiyat Bekleyenler"]
            
        return {"text": response_text, "buttons": buttons if buttons else None}
    
    def _format_date(self, date_str, output_format='%d.%m.%Y'):
        """Tarihi formatlar"""
        try:
            if isinstance(date_str, str):
                # Farklı formatları dene
                for fmt in ['%Y-%m-%d', '%d.%m.%Y', '%d/%m/%Y']:
                    try:
                        d = datetime.strptime(date_str, fmt)
                        return d.strftime(output_format)
                    except:
                        continue
        except:
            pass
        return date_str or "Belirsiz"
    
    def _days_until(self, date_str):
        """Tarihe kaç gün kaldığını hesaplar"""
        try:
            if isinstance(date_str, str):
                for fmt in ['%Y-%m-%d', '%d.%m.%Y', '%d/%m/%Y']:
                    try:
                        d_date = datetime.strptime(date_str, fmt).date()
                        break
                    except:
                        continue
                else:
                    return None
            else:
                d_date = date_str
            today = now_turkey().date()
            return (d_date - today).days
        except:
            return None

    # =========================================================================
    # CEVAP ÜRETİCİLER
    # =========================================================================

    def _handle_help(self):
        """Yardım mesajı"""
        return {
            "text": """🤖 **Rota Asistan - BİLGİ ASİSTANI**

**🎯 Doğal Dil ile Sorgulama - Her Türlü Soruyu Anlıyorum!**

**📦 SİPARİŞ SORGULAMA:**
✓ Sipariş kodu: "ABC-001", "a siparişi"
✓ Müşteri: "Ahmet", "Cam Evi"
✓ Durum: "Gecikenler", "Bekleyenler", "Üretimdekiler"

**🏭 ÜRETİM BİLGİLERİ:**
✓ Makine kuyruğu: "TEMPER işleri", "CNC kuyruğu"
✓ İstasyon durumu: "Makine doluluk", "LAMINE yükü"
✓ Fire bilgisi: "Fire raporu", "Hata sayısı"

**💬 DOĞAL SORULAR:**
✓ "Ahmet ne durumda?" → Müşteri siparişleri
✓ "TEMPER bekleyenler?" → Kuyruk listesi
✓ "Ne durumda?" → Son sorgu bilgisi
✓ "Bugün ne yapıldı?" → Günlük özet

**📊 RAPORLAR ve ANALİZ:**
• Günlük özet • İstatistikler
• Geciken siparişler • Kritik stoklar
• Makine yükleri • Fire analizi

**🔍 ARAMA İPUÇLARI:**
• Tam cümle yazabilirsiniz
• Büyük/küçük harf fark etmez
• Müşteri adının bir kısmı yeter

💡 **Sorunuzu yazın, size yardımcı olayım!**""",
            "buttons": ["📦 Sipariş Ara", "👤 Müşteri", "🏭 Makineler", "📊 Özet"]
        }

    def _handle_order_search_prompt(self):
        """Sipariş kodu isteme"""
        return {
            "text": "🔍 **Esnek Arama - Her Şekilde Bulur!**\n\n**Sadece yazın:**\n• Sipariş kodu: ABC-001\n• İsim: Ahmet, Cam Evi, Yapı...\n• Durum: Üretimdekiler\n\n**Doğal cümle:**\n• \"Ahmet ne durumda?\"\n• \"Cam Evi siparişleri\"\n• \"Bekleyen işler\"",
            "buttons": ["⏳ Bekleyenler", "🔄 Üretimdekiler", "⚠️ Gecikenler"]
        }

    def _handle_machine_query(self):
        """Makine doluluklarını yorumlar"""
        if not db:
            return {"text": "⚠️ Veritabanı bağlantısı yok."}
        
        try:
            loads = db.get_station_loads()
            
            if not loads:
                return {"text": "ℹ️ İstasyon verisi bulunamadı."}
            
            # Kategorize et
            critical = [m for m in loads if m.get('percent', 0) > 90]
            busy = [m for m in loads if 70 < m.get('percent', 0) <= 90]
            free = [m for m in loads if m.get('percent', 0) <= 30]
            
            msg = "🏭 **İstasyon Durumu**\n\n"
            
            if critical:
                msg += "🚨 **Kritik:**\n"
                for m in critical:
                    msg += f"• {m['name']}: %{m['percent']}\n"
                msg += "\n"
                
            if busy:
                msg += "⚠️ **Yoğun:**\n"
                for m in busy:
                    msg += f"• {m['name']}: %{m['percent']}\n"
                msg += "\n"
                    
            if not critical and not busy:
                msg += "✅ Kritik yoğunluk yok.\n\n"
                
            if free:
                msg += "🟢 **Müsait:**\n"
                for m in free[:3]:
                    msg += f"• {m['name']}: %{m['percent']}\n"
                    
            if critical:
                msg += f"\n💡 {critical[0]['name']} darboğaz oluşturuyor."
                
            return {"text": msg, "buttons": ["📊 Günlük Özet", "⚠️ Gecikenler"]}
            
        except Exception as e:
            return {"text": f"⚠️ Hata: {str(e)}"}

    def _handle_stock_query(self):
        """Kritik stokları söyler"""
        if not db:
            return {"text": "⚠️ Veritabanı bağlantısı yok."}
        
        try:
            low_stocks = db.get_low_stocks()
            
            if not low_stocks:
                return {
                    "text": "✅ **Stok Durumu İyi**\n\nKritik seviyede ürün yok.",
                    "buttons": ["📊 Günlük Özet"]
                }
            
            msg = f"⚠️ **{len(low_stocks)} Kritik Stok**\n\n"
            
            for s in low_stocks[:5]:
                product = s.get('product_name', 'Ürün')
                qty = s.get('quantity_m2', 0)
                limit = s.get('min_limit', 0)
                msg += f"• **{product}**\n  {qty:.0f} m² (Min: {limit:.0f})\n\n"
                
            if len(low_stocks) > 5:
                msg += f"... ve {len(low_stocks)-5} ürün daha"
                
            return {"text": msg, "buttons": ["📊 Günlük Özet"]}
            
        except Exception as e:
            return {"text": f"⚠️ Hata: {str(e)}"}

    def _handle_fire_query(self):
        """Fire durumunu raporlar"""
        if not db:
            return {"text": "⚠️ Veritabanı bağlantısı yok."}
        
        try:
            stats = db.get_dashboard_stats()
            fire_count = stats.get('fire', 0)
            
            fire_data = db.get_fire_analysis_data()
            
            msg = f"🔥 **Fire Raporu**\n\nToplam: {fire_count} adet\n\n"
            
            if fire_data:
                msg += "**İstasyon Bazlı:**\n"
                for f in fire_data[:4]:
                    station = f.get('station_name', 'Bilinmeyen')
                    count = f.get('fire_adedi', 0)
                    msg += f"• {station}: {count} adet\n"
            else:
                msg += "Detaylı kayıt yok."
                
            return {"text": msg, "buttons": ["📊 Günlük Özet", "🏭 Makineler"]}
            
        except Exception as e:
            return {"text": f"⚠️ Hata: {str(e)}"}

    def _handle_overdue_query(self):
        """Geciken siparişleri listeler"""
        if not db:
            return {"text": "⚠️ Veritabanı bağlantısı yok."}
        
        try:
            all_orders = db.get_all_orders()
            today = now_turkey().date()
            overdue = []
            
            for o in all_orders:
                status = o.get('status', '')
                if status in ['Sevk Edildi', 'Tamamlandı']:
                    continue
                    
                delivery = o.get('delivery_date')
                if delivery:
                    days = self._days_until(delivery)
                    if days is not None and days < 0:
                        overdue.append({
                            'code': o.get('order_code', 'N/A'),
                            'customer': o.get('customer_name', ''),
                            'days': abs(days),
                            'status': status
                        })
            
            if not overdue:
                return {
                    "text": "🎉 **Harika!**\n\nGeciken sipariş yok.",
                    "buttons": ["📊 Günlük Özet", "🏭 Makineler"]
                }
            
            # Gecikme süresine göre sırala
            overdue.sort(key=lambda x: x['days'], reverse=True)
            
            msg = f"🚨 **{len(overdue)} Geciken Sipariş**\n\n"
            
            for o in overdue[:5]:
                icon = "🔴" if o['days'] > 7 else "🟠" if o['days'] > 3 else "🟡"
                msg += f"{icon} **{o['code']}**\n"
                msg += f"   {o['customer']} | {o['days']} gün\n\n"
                
            if len(overdue) > 5:
                msg += f"... ve {len(overdue)-5} sipariş daha"
                
            return {"text": msg, "buttons": ["📊 Günlük Özet", "🏭 Makineler"]}
            
        except Exception as e:
            return {"text": f"⚠️ Hata: {str(e)}"}

    def _handle_today_summary(self):
        """Bugünün özeti"""
        if not db:
            return {"text": "⚠️ Veritabanı bağlantısı yok."}
        
        try:
            stats = db.get_dashboard_stats()
            all_orders = db.get_all_orders()
            today = now_turkey().date()
            
            # Bugün teslim edilecekler
            today_count = 0
            for o in all_orders:
                if o.get('status') in ['Sevk Edildi', 'Tamamlandı']:
                    continue
                delivery = o.get('delivery_date')
                if delivery:
                    days = self._days_until(delivery)
                    if days == 0:
                        today_count += 1
            
            # Bugün tamamlanan
            try:
                today_completed = db.get_today_completed_count()
            except:
                today_completed = 0
            
            msg = f"📊 **Günlük Özet**\n{today.strftime('%d.%m.%Y')}\n\n"
            msg += f"🔄 Aktif: {stats.get('active', 0)}\n"
            msg += f"⚡ Acil/Kritik: {stats.get('urgent', 0)}\n"
            msg += f"✅ Bugün Tamamlanan: {today_completed}\n"
            msg += f"📅 Bugün Teslim: {today_count}\n"
            msg += f"🔥 Fire: {stats.get('fire', 0)}\n"
            
            return {"text": msg, "buttons": ["🏭 Makineler", "⚠️ Gecikenler", "🔥 Fire"]}
            
        except Exception as e:
            return {"text": f"⚠️ Hata: {str(e)}"}

    def _handle_stats_query(self):
        """Genel istatistikler"""
        if not db:
            return {"text": "⚠️ Veritabanı bağlantısı yok."}
        
        try:
            stats = db.get_dashboard_stats()
            all_orders = db.get_all_orders()
            
            # Durum dağılımı
            status_counts = {}
            for o in all_orders:
                st = o.get('status', 'Bilinmiyor')
                status_counts[st] = status_counts.get(st, 0) + 1
            
            msg = "📈 **İstatistikler**\n\n"
            
            icons = {'Beklemede': '⏳', 'Üretimde': '🔄', 'Tamamlandı': '✅', 'Sevk Edildi': '🚚'}
            for status, count in sorted(status_counts.items(), key=lambda x: x[1], reverse=True):
                icon = icons.get(status, '📋')
                msg += f"{icon} {status}: {count}\n"
            
            msg += f"\n**Toplam:** {len(all_orders)} sipariş"
            
            return {"text": msg, "buttons": ["📊 Günlük Özet", "🏭 Makineler"]}
            
        except Exception as e:
            return {"text": f"⚠️ Hata: {str(e)}"}

    def _handle_project_query(self):
        """Proje sorguları"""
        if not db:
            return {"text": "⚠️ Veritabanı bağlantısı yok."}

        try:
            projects = db.get_all_projects()
            active = [p for p in projects if p.get('status') in ['Aktif', 'Devam Ediyor']]

            if not active:
                return {"text": "📁 Aktif proje yok.", "buttons": ["📊 Günlük Özet"]}

            msg = f"📁 **{len(active)} Aktif Proje**\n\n"

            for p in active[:4]:
                name = p.get('project_name', 'Proje')
                customer = p.get('customer_name', '')
                msg += f"• **{name}**"
                if customer:
                    msg += f" ({customer})"
                msg += "\n"

            return {"text": msg, "buttons": ["📊 Günlük Özet"]}

        except Exception as e:
            return {"text": f"⚠️ Hata: {str(e)}"}

    # =========================================================================
    # YENİ ÖZELLİKLER v3.0
    # =========================================================================

    def _try_find_by_customer(self, msg):
        """Müşteri ismine göre siparişleri arar - ESNEK ARAMA"""
        if not db:
            return None

        # Müşteri sorgusu mu kontrol et
        lower_msg = self._turkish_lower(msg)

        # "Müşteri Ara" veya "İsim Ara" butonu tıklandıysa
        if lower_msg in ['müşteri ara', 'musteri ara', 'müşteri', 'musteri', 'isim ara', 'isim', 'İsim ara']:
            return {
                "text": "👤 **İsim Ara - Süper Esnek!**\n\n**Sadece yazın:**\n• İsmin bir kısmı bile yeter\n• \"Ahm\" → Ahmet, Ahmed...\n• \"Cam\" → Cam Evi, Camlı İnşaat...\n• \"Yapı\" → Yapı A.Ş., Yapıcı Ltd...\n\n**Kelime sırası önemli değil!**\nDirekt isim yazın, gerisini ben hallederim! 🎯",
                "buttons": ["📦 Tüm Siparişler", "🏭 Makineler", "📊 Özet"]
            }

        # ESNEK ARAMA: Sadece müşteri hint kelimeleri varsa devam et
        # Ama yoksa da yine de arama yap (daha sonra)
        has_customer_hint = self._contains_any(lower_msg, ['müşteri', 'musteri', 'firma', 'sirket', 'şirket'])

        # Veritabanındaki tüm siparişleri al
        try:
            all_orders = db.get_all_orders()

            # Mesajdaki kelimeleri çıkar ve gereksiz kelimeleri filtrele
            stop_words = ['müşteri', 'musteri', 'firma', 'sirket', 'şirket', 'için', 'icin',
                          'olan', 'ait', 'ne', 'nerede', 'hangi', 'sipariş', 'siparis',
                          'siparişleri', 'siparisleri', 'var', 'mi', 'mı']

            words = re.sub(r'[^\w\s]', ' ', msg).split()
            search_words = [w for w in words if len(w) >= 3 and self._turkish_lower(w) not in stop_words]

            if not search_words:
                return None

            # Her kelimeyi müşteri isimlerinde ara (ESNEK - kısmi eşleşme)
            matches = []
            match_scores = {}  # Eşleşme puanı tut

            for order in all_orders:
                customer = order.get('customer_name', '')
                if not customer:
                    continue

                customer_lower = self._turkish_lower(customer)
                score = 0

                for word in search_words:
                    word_lower = self._turkish_lower(word)

                    # Tam kelime eşleşmesi (en yüksek puan)
                    if word_lower in customer_lower.split():
                        score += 10
                    # Kısmi eşleşme (içinde geçiyor)
                    elif word_lower in customer_lower:
                        score += 5
                    # Başlangıç eşleşmesi
                    elif customer_lower.startswith(word_lower):
                        score += 7

                if score > 0:
                    if order not in matches:
                        matches.append(order)
                        match_scores[order.get('order_code', '')] = score

            # Eşleşmeleri puana göre sırala
            if matches:
                matches.sort(key=lambda x: match_scores.get(x.get('order_code', ''), 0), reverse=True)
                self.last_customer = matches[0].get('customer_name')

                # Eğer müşteri hint kelimesi vardı ve eşleşme bulduysa, kesin dön
                if has_customer_hint:
                    return self._format_multiple_orders(matches, f"Müşteri: {self.last_customer}")

                # Hint kelimesi yoksa ama güçlü eşleşme varsa (skor >= 7), yine de dön
                if match_scores.get(matches[0].get('order_code', ''), 0) >= 7:
                    return self._format_multiple_orders(matches, f"📋 Aranan: {search_words[0].upper()}")

        except Exception as e:
            pass

        return None

    def _try_find_by_status(self, msg):
        """Sipariş durumuna göre arama"""
        if not db:
            return None

        status_map = {
            'bekle': 'Beklemede',
            'üretim': 'Üretimde',
            'tamamlan': 'Tamamlandı',
            'sevk': 'Sevk Edildi'
        }

        for key, status in status_map.items():
            if key in msg:
                try:
                    orders = db.get_orders_by_status(status)
                    if orders:
                        return self._format_multiple_orders(orders[:10], f"Durum: {status}")
                except:
                    pass

        return None

    def _try_find_by_machine(self, msg):
        """Makine/İstasyon bazlı sipariş arama - ESNEK"""
        if not db:
            return None

        lower_msg = self._turkish_lower(msg)

        # Makine hint kelimeleri (bu kelimeler VARSA makine araması yapacağız)
        machine_hints = ['üzerinde', 'uzerinde', 'kuyruğu', 'kuyrugu', 'işleri', 'isleri']

        # Makine hint kelimesi var mı?
        has_machine_hint = self._contains_any(lower_msg, machine_hints)

        # Eğer hint yoksa, çık (önemli: "bekleyen", "makine", "istasyon" yeterli DEĞİL)
        if not has_machine_hint:
            return None

        # Tüm istasyon isimlerini al
        try:
            capacities = db.get_all_capacities()
            station_names = list(capacities.keys())

            # Mesajdaki kelimeleri temizle (hint kelimeleri çıkar)
            stop_words = ['üzerinde', 'uzerinde', 'bekleyen', 'bekleyenler',
                          'sırada', 'sirada', 'sıradakiler', 'siradakiler',
                          'kuyruğu', 'kuyrugu', 'işleri', 'isleri',
                          'ne', 'var', 'hangi', 'için', 'icin', 'olan', 'olanlar']

            words = re.sub(r'[^\w\s]', ' ', msg).split()
            search_words = [w for w in words if len(w) >= 2 and self._turkish_lower(w) not in stop_words]

            if not search_words:
                # Sadece "makine" veya "istasyon" denmişse veya "Makine İşleri" butonuna basıldıysa
                # En yoğun 4 makineyi öner
                loads = db.get_station_loads()
                # Yoğunluğa göre sırala
                sorted_loads = sorted(loads, key=lambda x: x.get('percent', 0), reverse=True)
                top_stations = [load['name'] for load in sorted_loads[:4]]

                return {
                    "text": "🏭 **Hangi makine/istasyon?**\n\n**Örnekler:**\n• \"TEMPER bekleyenler\"\n• \"LAMINE işleri\"\n• \"CNC kuyruğu\"\n• \"DOUBLEDGER üzerindekiler\"\n\n**En yoğun makineler:**",
                    "buttons": top_stations if top_stations else ["TEMPER A1", "LAMINE A1", "DOUBLEDGER", "CNC RODAJ"]
                }

            # Her kelimeyi istasyon isimlerinde ara (ESNEK)
            matched_station = None
            best_score = 0

            for station in station_names:
                station_lower = self._turkish_lower(station)
                score = 0

                for word in search_words:
                    word_lower = self._turkish_lower(word)

                    # Tam eşleşme
                    if word_lower == station_lower:
                        score += 20
                    # İçinde geçiyor
                    elif word_lower in station_lower:
                        score += 15
                    # Başlangıç
                    elif station_lower.startswith(word_lower):
                        score += 18
                    # İstasyon kelimelerinde geçiyor (TEMPER A1 -> "temper" veya "a1")
                    elif word_lower in station_lower.split():
                        score += 17

                if score > best_score:
                    best_score = score
                    matched_station = station

            # Eşleşme varsa
            if matched_station and best_score >= 15:
                # Bu istasyonda bekleyen siparişleri bul
                all_orders = db.get_all_orders()
                waiting_orders = []

                for order in all_orders:
                    # Tamamlanmış veya sevk edilmiş olanları atla
                    if order.get('status') in ['Tamamlandı', 'Sevk Edildi']:
                        continue

                    route = order.get('route', '')
                    order_id = order.get('id')

                    # Rotada bu istasyon var mı?
                    if matched_station in route:
                        # Bu istasyon tamamlandı mı?
                        try:
                            completed_stations = db.get_completed_stations_list(order_id)
                            if completed_stations is None:
                                completed_stations = []

                            # Eğer bu istasyon henüz tamamlanmamışsa
                            if matched_station not in completed_stations:
                                waiting_orders.append(order)
                        except:
                            waiting_orders.append(order)

                if waiting_orders:
                    # İstasyon yoğunluğunu da ekle
                    loads = db.get_station_loads()
                    station_load = next((l for l in loads if l['name'] == matched_station), None)
                    load_info = ""
                    if station_load:
                        percent = station_load.get('percent', 0)
                        load_info = f"\n📊 Yoğunluk: %{percent}"

                    title = f"🏭 {matched_station}{load_info}\n{len(waiting_orders)} sipariş bekliyor"
                    return self._format_multiple_orders(waiting_orders[:10], title)
                else:
                    return {
                        "text": f"✅ **{matched_station}**\n\nBu istasyonda bekleyen sipariş yok!",
                        "buttons": ["🏭 Tüm Makineler", "📊 Özet"]
                    }

        except Exception as e:
            return None

        return None

    def _format_multiple_orders(self, orders, title="Siparişler"):
        """Çoklu sipariş sonuçlarını formatlar"""
        if not orders:
            return {"text": "🔍 Sonuç bulunamadı.", "buttons": ["📦 Sipariş Sorgula", "📊 Özet"]}

        count = len(orders)
        orders_to_show = orders[:5]  # İlk 5'i göster

        msg = f"📋 **{title}**\n{count} sipariş bulundu\n\n"

        for order in orders_to_show:
            code = order.get('order_code', 'N/A')
            customer = order.get('customer_name', 'Müşteri')
            status = order.get('status', 'Bilinmiyor')

            # Durum ikonu
            status_icons = {
                "Beklemede": "⏳",
                "Üretimde": "🔄",
                "Tamamlandı": "✅",
                "Sevk Edildi": "🚚"
            }
            icon = status_icons.get(status, "📋")

            msg += f"{icon} **{code}**\n"
            msg += f"   👤 {customer} | {status}\n\n"

        if count > 5:
            msg += f"... ve {count - 5} sipariş daha\n"

        # Butonlar - ilk 3 sipariş kodu
        buttons = [orders_to_show[i].get('order_code') for i in range(min(3, len(orders_to_show)))]

        return {"text": msg, "buttons": buttons}

    def _handle_unknown_with_suggestions(self, msg):
        """Anlaşılamayan mesajlar için akıllı öneriler"""
        # Konuşma geçmişine bak
        recent_topics = self._get_recent_topics()

        suggestions = []

        # Geçmiş konulara göre öneriler
        if 'sipariş' in recent_topics:
            suggestions.append("📦 Başka Sipariş Sorgula")
        if 'makine' in recent_topics or 'istasyon' in recent_topics:
            suggestions.append("🏭 Makine Durumu")

        # Varsayılan öneriler
        if not suggestions:
            suggestions = ["📦 Sipariş Sorgula", "🏭 Makineler", "📊 Özet", "❓ Yardım"]

        # Son sorgulanan müşteri varsa öneri ekle
        if self.last_customer:
            msg_text = f"Bunu tam anlayamadım.\n\n💡 Son sorguladığınız: **{self.last_customer}**\n\nŞunları deneyebilirsiniz:"
        else:
            msg_text = "Bunu tam anlayamadım.\n\nŞunları deneyebilirsiniz:\n• Sipariş kodu yazın\n• Müşteri ismi yazın\n• \"Geciken siparişler\"\n• \"Makine durumu\""

        return {
            "text": msg_text,
            "buttons": suggestions[:4]
        }

    def _get_recent_topics(self):
        """Son 5 mesajdaki konuları analiz eder"""
        topics = []
        recent = self.conversation_history[-5:] if len(self.conversation_history) >= 5 else self.conversation_history

        for msg in recent:
            if msg.get('role') == 'user':
                text = self._turkish_lower(msg.get('message', ''))
                if 'sipariş' in text or 'siparis' in text or 'order' in text:
                    topics.append('sipariş')
                if 'makine' in text or 'istasyon' in text:
                    topics.append('makine')
                if 'müşteri' in text or 'musteri' in text:
                    topics.append('müşteri')

        return list(set(topics))


# Global nesne
bot = RotaBot()