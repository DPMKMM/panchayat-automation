' =====================================================================
' e-Panchayat Silent Background Launcher (Zero Windows on Screen)
' Prevents accidental closure by office staff clicking 'X'
' =====================================================================

Set WshShell = CreateObject("WScript.Shell")
Set fso = CreateObject("Scripting.FileSystemObject")

strPath = fso.GetParentFolderName(WScript.ScriptFullName)
strBat = Chr(34) & strPath & "\Run_Office_Server_Silent.bat" & Chr(34)

' Run completely hidden (window style 0, bWaitOnReturn False)
WshShell.Run strBat, 0, False
