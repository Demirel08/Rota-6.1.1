# REFLEKS 360 ROTA - Build ve Setup Kılavuzu

## 📋 Gereksinimler

1. **Python 3.10+** kurulu olmalı
2. **PyInstaller** kurulu olmalı: `pip install pyinstaller`
3. **Inno Setup 6.x** kurulu olmalı: [İndir](https://jrsoftware.org/isdl.php)
4. Tüm Python bağımlılıkları kurulu olmalı: `pip install -r requirements.txt`

## 🚀 Hızlı Başlangıç

### Adım 1: EXE Oluşturma

En basit yöntem `build.bat` dosyasını çalıştırmak:

```bash
build.bat
```

Bu script:
- ✅ Önceki build dosyalarını temizler
- ✅ PyInstaller ile EXE oluşturur
- ✅ Test etmenizi sağlar
- ✅ Inno Setup'a yönlendirir

### Adım 2: Setup (Installer) Oluşturma

1. **Inno Setup'ı açın**
2. `setup_installer.iss` dosyasını yükleyin
3. **Build > Compile** (veya F9)
4. `installer_output\` klasöründe Setup.exe hazır!

## 📁 Önemli Dosyalar

| Dosya | Açıklama |
|-------|----------|
| `REFLEKS360ROTA.spec` | PyInstaller yapılandırma dosyası |
| `setup_installer.iss` | Inno Setup script dosyası |
| `build.bat` | Otomatik build scripti (Windows) |
| `icon.ico` | Program ikonu (opsiyonel) |

## ⚠️ ÇOK ÖNEMLİ NOTLAR

### 1. Veritabanı Konumu
Program veritabanını şuraya yazar:
```
C:\Users\[Kullanıcı]\AppData\Local\REFLEKS360ROTA\
├── efes_factory.db      ← Veritabanı
├── logs\                ← Log dosyaları
└── exports\             ← PDF/Excel export'lar
```

**NEDEN?**
- ✅ Program Files'a yazma izni gerektirmez
- ✅ Her kullanıcının kendi verisi olur
- ✅ Güncelleme yapınca veriler kaybolmaz
- ✅ Windows standartlarına uygun

### 2. Admin Yetkisi GEREKMİYOR
`setup_installer.iss` dosyasında:
```pascal
PrivilegesRequired=lowest
```
Bu sayede normal kullanıcı bile kurabilir.

### 3. İlk Çalıştırma
Program ilk çalıştırıldığında:
- ✅ Otomatik veritabanı oluşturulur
- ✅ Default kullanıcılar eklenir (`admin/admin`)
- ✅ Log klasörü oluşturulur

### 4. Güncelleme Senaryosu
Kullanıcı programı güncellediğinde:
- ✅ EXE dosyası değişir (Program Files)
- ✅ Veritabanı AYNEN KALIR (AppData)
- ✅ Ayarlar AYNEN KALIR
- ✅ Log'lar AYNEN KALIR

### 5. Kaldırma (Uninstall)
Kullanıcı programı kaldırınca:
- ⚠️ Seçim soruluyor: "Verileri sil mi?"
- ✅ HAYIR → Veriler korunur, tekrar kurulunca kullanılır
- ❌ EVET → Tüm veriler silinir

## 🔧 Sorun Giderme

### Sorun 1: "Module not found" Hatası
**Çözüm:** Hidden imports ekleyin
```bash
# REFLEKS360ROTA.spec dosyasına ekleyin:
hiddenimports=[
    'PySide6.QtCore',
    'reportlab.pdfbase.ttfonts',
    # ... diğerleri
]
```

### Sorun 2: Font Bulunamadı
**Çözüm:** Windows Fonts klasörü kontrol edilir, yoksa fallback kullanılır.
```python
# Kod zaten bunu yapıyor (pdf_engine.py)
if os.path.exists(font_path):
    pdfmetrics.registerFont(TTFont('Arial', font_path))
else:
    pdfmetrics.registerFont(TTFont('Arial', 'Helvetica'))
```

### Sorun 3: EXE Çok Büyük (>100MB)
**Normal!** PySide6 ve reportlab ağır kütüphaneler.
**Çözüm (opsiyonel):**
- UPX ile sıkıştırma: `upx=True` (spec dosyasında zaten var)
- Gereksiz modülleri exclude edin

### Sorun 4: Virüs Uyarısı (False Positive)
PyInstaller ile yapılan EXE'ler bazen antivirüs alarmı verir.
**Çözüm:**
1. EXE'yi VirusTotal'da test edin
2. Code signing sertifikası alın (profesyonel)
3. Windows SmartScreen'e bildirin

## 📊 Test Checklist

Setup yapmadan önce test edin:

- [ ] EXE normal modda çalışıyor mu?
- [ ] Veritabanı AppData'ya oluşuyor mu?
- [ ] Login ekranı açılıyor mu?
- [ ] PDF export çalışıyor mu?
- [ ] Türkçe karakterler düzgün görünüyor mu?
- [ ] Farklı bir Windows kullanıcısında test ettiniz mi?

## 🎯 Önerilen İş Akışı

```mermaid
1. Kodunuzu test edin (main.py)
   ↓
2. build.bat çalıştırın
   ↓
3. dist\REFLEKS360ROTA.exe test edin
   ↓
4. Sorun varsa düzeltin, tekrar build
   ↓
5. Sorun yoksa Inno Setup ile installer oluşturun
   ↓
6. Setup dosyasını test edin (temiz bir PC'de)
   ↓
7. Dağıtıma hazır! 🎉
```

## 🔐 Güvenlik Notları

1. **Şifreleri değiştirin:** Default `admin/admin` şifresini kullanıcılar değiştirmeli
2. **Yedekleme hatırlatın:** Kullanıcılara AppData klasörünü yedeklemelerini söyleyin
3. **Güncellemeler:** Versiyon numarasını her build'de artırın

## 📞 Destek

Sorun yaşarsanız:
1. `logs\error.log` dosyasını kontrol edin (AppData\Local\REFLEKS360ROTA\logs\)
2. Console modunda çalıştırın: `pyinstaller --console REFLEKS360ROTA.spec`
3. Hata mesajını kopyalayıp destek ekibine gönderin

---

**Hazırlayan:** Claude AI
**Tarih:** 2025-12-18
**Versiyon:** 1.0.0
