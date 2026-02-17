; SRE_Cockpit_Installer_NoAdmin.iss  (Inno Setup)
; Per-user install (no admin), adds Desktop + Start Menu + Right-click "Send to" entry.
; Build prereqs:
;   1) Compile cockpit to an EXE with PyInstaller (onefile or onefolder)
;   2) Install Inno Setup, then compile this .iss

[Setup]
AppName=SRE Application Cockpit
AppVersion=1.0.0
DefaultDirName={localappdata}\Programs\SRE_Cockpit
DefaultGroupName=SRE Cockpit
OutputBaseFilename=SRE_Cockpit_Installer_NoAdmin
Compression=lzma
SolidCompression=yes
PrivilegesRequired=lowest

[Files]
; === Adjust these paths to match your build output ===
; If you use one-folder:
Source: "dist\SRE_Application_Cockpit\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

; If you use one-file instead, swap the above line for this:
; Source: "dist\SRE_Application_Cockpit.exe"; DestDir: "{app}"; Flags: ignoreversion

; Ship required runtime files (keep minimal)
Source: "cockpit-requirements.txt"; DestDir: "{app}"; Flags: ignoreversion
Source: "launcher_state.json"; DestDir: "{app}"; Flags: ignoreversion

; Ship icon if used
Source: "sap_sre_icon.ico"; DestDir: "{app}"; Flags: ignoreversion

; Ship ONLY git-repos (internal packaging rule)
Source: "applications\git-repos"; DestDir: "{app}\applications"; Flags: ignoreversion

; If you have an assets folder (banner, images, etc.), include it:
; Source: "assets\*"; DestDir: "{app}\assets"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
; Desktop shortcut (per-user)
Name: "{userdesktop}\SRE Application Cockpit"; Filename: "{app}\SRE_Application_Cockpit.exe"; WorkingDir: "{app}"

; Start Menu shortcut (per-user)
Name: "{userprograms}\SRE Cockpit\SRE Application Cockpit"; Filename: "{app}\SRE_Application_Cockpit.exe"; WorkingDir: "{app}"

; Right-click → Send to → SRE Application Cockpit (per-user)
Name: "{userappdata}\Microsoft\Windows\SendTo\SRE Application Cockpit"; Filename: "{app}\SRE_Application_Cockpit.exe"; Parameters: "--import ""%1"""; WorkingDir: "{app}"

; Optional second entry that prompts for a custom tile name:
; Name: "{userappdata}\Microsoft\Windows\SendTo\SRE Application Cockpit (Prompt Name)"; Filename: "{app}\SRE_Application_Cockpit.exe"; Parameters: "--import ""%1"" --prompt"; WorkingDir: "{app}"

[Run]
Filename: "{app}\SRE_Application_Cockpit.exe"; Description: "Launch SRE Application Cockpit"; Flags: nowait postinstall skipifsilent
