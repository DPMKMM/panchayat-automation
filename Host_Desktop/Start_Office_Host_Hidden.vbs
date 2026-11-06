Set WshShell = CreateObject("WScript.Shell")
Set fso = CreateObject("Scripting.FileSystemObject")

targetDir = "D:\DPM-ept"
scriptPath = targetDir & "\run_silent.bat"

If Not fso.FolderExists(targetDir) Then
    MsgBox "Directory " & targetDir & " does not exist yet!" & vbCrLf & vbCrLf & _
           "Please run 'Setup_Office_Desktop_D_Drive.bat' once first to set up D:\DPM-ept.", 16, "ePanchayat Portal"
    WScript.Quit 1
End If

If Not fso.FileExists(scriptPath) Then
    MsgBox "File " & scriptPath & " was not found inside D:\DPM-ept!", 16, "ePanchayat Portal"
    WScript.Quit 1
End If

' Run completely hidden with window style 0 (no command prompt window shown)
WshShell.CurrentDirectory = targetDir
WshShell.Run "cmd.exe /c """ & scriptPath & """", 0, False

' Helpful confirmation popup that closes automatically or on OK
MsgBox "Telangana ePanchayat Portal is now running in the BACKGROUND!" & vbCrLf & vbCrLf & _
       "• Domain      : https://www.panchayatautomation.in" & vbCrLf & _
       "• Work Directory: D:\DPM-ept" & vbCrLf & _
       "• Auto-Sync   : Active (pulls laptop updates every 60s)" & vbCrLf & _
       "• Protection  : 100% Hidden. Closing other CMD windows will NOT affect it!", 64, "ePanchayat Background Host"
