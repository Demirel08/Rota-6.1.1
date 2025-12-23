; REFLEKS 360 ROTA - Inno Setup Script
; Inno Setup 6.x ile derlenmiştir
; https://jrsoftware.org/isinfo.php

#define MyAppName "REFLEKS 360 ROTA"
#define MyAppVersion "1.0.0"
#define MyAppPublisher "REFLEKS CAM"
#define MyAppExeName "REFLEKS360ROTA.exe"
#define MyAppURL "https://www.reflekscam.com"

[Setup]
; ÖNEMLI: Admin yetkisi gerektirmesin!
PrivilegesRequired=lowest
PrivilegesRequiredOverridesAllowed=dialog

AppId={{A8B3C2D1-4E5F-6A7B-8C9D-0E1F2A3B4C5D}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppPublisher={#MyAppPublisher}
AppPublisherURL={#MyAppURL}
AppSupportURL={#MyAppURL}
AppUpdatesURL={#MyAppURL}
DefaultDirName={autopf}\{#MyAppName}
DefaultGroupName={#MyAppName}
AllowNoIcons=yes
OutputDir=installer_output
OutputBaseFilename=REFLEKS360ROTA_Setup_v{#MyAppVersion}
Compression=lzma2/max
SolidCompression=yes
WizardStyle=modern
; Icon dosyası
SetupIconFile=icon.ico
UninstallDisplayIcon={app}\icon.ico

; Windows 10 ve üstü
MinVersion=10.0

[Languages]
Name: "turkish"; MessagesFile: "compiler:Languages\Turkish.isl"

[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"
Name: "quicklaunchicon"; Description: "Hızlı Başlat simgesi oluştur"; GroupDescription: "{cm:AdditionalIcons}"; Flags: unchecked

[Files]
; Ana EXE dosyası
Source: "dist\{#MyAppExeName}"; DestDir: "{app}"; Flags: ignoreversion
; Icon dosyası
Source: "icon.ico"; DestDir: "{app}"; Flags: ignoreversion

; OPSIYONEL: Ek dosyalar (readme vb.)
; Source: "README.md"; DestDir: "{app}"; Flags: ignoreversion

[Icons]
Name: "{group}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"
Name: "{group}\{cm:UninstallProgram,{#MyAppName}}"; Filename: "{uninstallexe}"
Name: "{autodesktop}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; Tasks: desktopicon
Name: "{userappdata}\Microsoft\Internet Explorer\Quick Launch\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; Tasks: quicklaunchicon

[Run]
; Kurulumdan sonra programı çalıştır (opsiyonel)
Filename: "{app}\{#MyAppExeName}"; Description: "{cm:LaunchProgram,{#StringChange(MyAppName, '&', '&&')}}"; Flags: nowait postinstall skipifsilent

[UninstallDelete]
; Geçici dosyaları temizle
Type: filesandordirs; Name: "{app}\__pycache__"

[Code]
{ ========== ÖNEMLI: Kullanıcı Verileri Yönetimi ========== }

var
  DataDirPage: TInputOptionWizardPage;
  KeepUserData: Boolean;

procedure InitializeWizard;
begin
  { Kaldırma sırasında veri saklama seçeneği }
  DataDirPage := CreateInputOptionPage(wpWelcome,
    'Kullanıcı Verileri', 'Veritabanı ve ayarlarınız nasıl yönetilsin?',
    'Program, verilerinizi şu konumda saklar:' + #13#10 +
    ExpandConstant('{localappdata}\REFLEKS360ROTA\') + #13#10#13#10 +
    'İlk kurulumda otomatik olarak veritabanı oluşturulacaktır.',
    False, False);

  DataDirPage.Add('Mevcut verileri koru (önerilir)');
  DataDirPage.Add('Tüm verileri sil ve sıfırdan başla');
  DataDirPage.Values[0] := True; { Varsayılan: Verileri koru }
end;

procedure CurStepChanged(CurStep: TSetupStep);
begin
  if CurStep = ssPostInstall then
  begin
    { Kurulum tamamlandı }
    MsgBox('Kurulum başarılı!' + #13#10#13#10 +
           'Verileriniz şurada saklanıyor:' + #13#10 +
           ExpandConstant('{localappdata}\REFLEKS360ROTA\') + #13#10#13#10 +
           '• Veritabanı: efes_factory.db' + #13#10 +
           '• Log dosyaları: logs klasörü' + #13#10#13#10 +
           'İlk girişte varsayılan kullanıcı:' + #13#10 +
           'Kullanıcı: admin | Şifre: admin',
           mbInformation, MB_OK);
  end;
end;

procedure CurUninstallStepChanged(CurUninstallStep: TUninstallStep);
var
  DataPath: String;
  Response: Integer;
begin
  if CurUninstallStep = usUninstall then
  begin
    DataPath := ExpandConstant('{localappdata}\REFLEKS360ROTA');

    if DirExists(DataPath) then
    begin
      Response := MsgBox(
        'Kullanıcı verileriniz şurada bulunuyor:' + #13#10 +
        DataPath + #13#10#13#10 +
        'Bu klasörde veritabanı, log dosyaları ve ayarlarınız var.' + #13#10#13#10 +
        'Tüm verileri SİLMEK istiyor musunuz?' + #13#10#13#10 +
        'EVET = Tüm veriler silinecek (geri alınamaz!)' + #13#10 +
        'HAYIR = Veriler korunacak (tekrar yüklediğinizde kullanabilirsiniz)',
        mbConfirmation, MB_YESNO or MB_DEFBUTTON2);

      if Response = IDYES then
      begin
        { Kullanıcı verileri silmek istedi }
        DelTree(DataPath, True, True, True);
        MsgBox('Tüm kullanıcı verileri silindi.', mbInformation, MB_OK);
      end
      else
      begin
        { Verileri koru }
        MsgBox('Verileriniz korundu. Programı tekrar yüklerseniz mevcut veriler kullanılacak.',
               mbInformation, MB_OK);
      end;
    end;
  end;
end;
