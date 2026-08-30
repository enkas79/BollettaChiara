; Script NSIS per l'installer Windows di BollettaChiara.
; VERSION viene passata dal workflow CI con /DVERSION=x.y.z (makensis);
; il fallback qui sotto serve solo per compilazioni manuali senza quel flag.
!ifndef VERSION
  !define VERSION "0.0.0"
!endif

!define APP_NAME "BollettaChiara"

Name "${APP_NAME} ${VERSION}"
OutFile "${APP_NAME}-Setup-${VERSION}.exe"
InstallDir "$PROGRAMFILES64\${APP_NAME}"
RequestExecutionLevel admin

Page directory
Page instfiles

UninstPage uninstConfirm
UninstPage instfiles

Section "Install"
  SetOutPath "$INSTDIR"
  ; dist\BollettaChiara\ è l'output onedir generato da PyInstaller nel job CI
  File /r "..\..\dist\${APP_NAME}\*.*"

  CreateDirectory "$SMPROGRAMS\${APP_NAME}"
  CreateShortcut "$SMPROGRAMS\${APP_NAME}\${APP_NAME}.lnk" "$INSTDIR\${APP_NAME}.exe"
  CreateShortcut "$DESKTOP\${APP_NAME}.lnk" "$INSTDIR\${APP_NAME}.exe"

  WriteUninstaller "$INSTDIR\Uninstall.exe"
SectionEnd

Section "Uninstall"
  RMDir /r "$INSTDIR"
  Delete "$SMPROGRAMS\${APP_NAME}\${APP_NAME}.lnk"
  Delete "$DESKTOP\${APP_NAME}.lnk"
  RMDir "$SMPROGRAMS\${APP_NAME}"
SectionEnd
