@echo off
REM ========================================
REM REFLEKS 360 ROTA - Build Script
REM ========================================

echo.
echo ==========================================
echo  REFLEKS 360 ROTA - EXE Olusturuluyor...
echo ==========================================
echo.

REM 1. Temizlik
echo [1/4] Onceki build dosyalari temizleniyor...
if exist build rmdir /s /q build
if exist dist rmdir /s /q dist
if exist __pycache__ rmdir /s /q __pycache__
echo       Temizlik tamamlandi.
echo.

REM 2. PyInstaller ile EXE olustur
echo [2/4] PyInstaller calistiriliyor...
echo       Bu islem 2-5 dakika surebilir, lutfen bekleyin...
echo.

pyinstaller REFLEKS360ROTA.spec

if errorlevel 1 (
    echo.
    echo [HATA] PyInstaller basarisiz oldu!
    echo Lutfen asagidaki kontrolleri yapin:
    echo   1. Python ve pip yuklu mu?
    echo   2. Gerekli kutuphaneler yuklu mu? pip install -r requirements.txt
    echo   3. REFLEKS360ROTA.spec dosyasi mevcut mu?
    pause
    exit /b 1
)

echo       EXE olusturma tamamlandi!
echo.

REM 3. Test
echo [3/4] EXE dosyasi test ediliyor...
if exist "dist\REFLEKS360ROTA.exe" (
    echo       [BASARILI] dist\REFLEKS360ROTA.exe olusturuldu!
    echo       Boyut:
    dir "dist\REFLEKS360ROTA.exe" | find "REFLEKS360ROTA.exe"
) else (
    echo       [HATA] EXE dosyasi bulunamadi!
    pause
    exit /b 1
)
echo.

REM 4. Bilgilendirme
echo [4/4] Tamamlandi!
echo.
echo ==========================================
echo  BUILD BASARILI
echo ==========================================
echo.
echo EXE Konumu: dist\REFLEKS360ROTA.exe
echo.
echo SIMDIKI ADIMLAR:
echo   1. dist\REFLEKS360ROTA.exe dosyasini test edin
echo   2. Hatasiz calistigini dogrulayin
echo   3. Inno Setup ile installer olusturun:
echo      - Inno Setup'i acin
echo      - setup_installer.iss dosyasini yukleyin
echo      - "Compile" butonuna tiklayin
echo   4. installer_output klasorundeki Setup.exe hazir!
echo.
echo ==========================================
echo.

REM Kullaniciya secim sun
:MENU
echo Ne yapmak istersiniz?
echo   1. EXE dosyasini test et
echo   2. Inno Setup dosyasini ac
echo   3. Cikis
echo.
set /p choice="Seciminiz (1-3): "

if "%choice%"=="1" goto TEST
if "%choice%"=="2" goto INNO
if "%choice%"=="3" goto END
goto MENU

:TEST
echo.
echo EXE test ediliyor...
start dist\REFLEKS360ROTA.exe
echo.
echo NOT: Herhangi bir hata alirsan konsol modunda test et:
echo      pyinstaller --console REFLEKS360ROTA.spec
echo.
pause
goto MENU

:INNO
echo.
echo Inno Setup aciliyor...
start setup_installer.iss
echo.
echo NOT: Inno Setup'i henuz yuklemediyseniz:
echo      https://jrsoftware.org/isdl.php
echo.
pause
goto MENU

:END
echo.
echo Iyi calismalar!
echo.
pause
