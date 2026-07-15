' ============================================================================
'  MedSearch - create a Desktop shortcut (Windows)
'
'  Double-click this file ONCE. It drops a "MedSearch" icon on your Desktop
'  that launches MedSearch.bat from this folder, using the MedSearch icon.
'  Run it again any time the folder moves to refresh the shortcut.
' ============================================================================
Option Explicit

Dim fso, shell, scriptDir, desktop, lnkPath, target, icon, lnk
Set fso   = CreateObject("Scripting.FileSystemObject")
Set shell = CreateObject("WScript.Shell")

scriptDir = fso.GetParentFolderName(WScript.ScriptFullName)
target    = fso.BuildPath(scriptDir, "MedSearch.bat")
icon      = fso.BuildPath(scriptDir, "icon.ico")

If Not fso.FileExists(target) Then
  MsgBox "Could not find MedSearch.bat next to this script." & vbCrLf & _
         "Keep this file inside the MedSearch folder and try again.", _
         48, "MedSearch"
  WScript.Quit 1
End If

desktop = shell.SpecialFolders("Desktop")
lnkPath = fso.BuildPath(desktop, "MedSearch.lnk")

Set lnk = shell.CreateShortcut(lnkPath)
lnk.TargetPath       = target
lnk.WorkingDirectory = scriptDir
lnk.Description      = "MedSearch - search the medical literature"
lnk.WindowStyle      = 1
If fso.FileExists(icon) Then lnk.IconLocation = icon
lnk.Save

MsgBox "Done. A 'MedSearch' icon is now on your Desktop." & vbCrLf & _
       "Double-click it to start the app.", 64, "MedSearch"
