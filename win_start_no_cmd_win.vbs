Set WshShell = CreateObject("WScript.Shell")
Set FSO = CreateObject("Scripting.FileSystemObject")
scriptDir = FSO.GetParentFolderName(WScript.ScriptFullName)
If Not FSO.FileExists(scriptDir & "\.venv\Scripts\python.exe") Then
    MsgBox ChrW(&H7F3A) & ChrW(&H5C11) & " .venv" & ChrW(&HFF0C) & ChrW(&H8BF7) & ChrW(&H8FD0) & ChrW(&H884C) & " setup_env.bat", vbCritical, "MiniJMP startup error"
    WScript.Quit 1
End If
exitCode = WshShell.Run("""" & scriptDir & "\win_start.bat""", 0, True)
If exitCode <> 0 Then
    MsgBox ChrW(&H542F) & ChrW(&H52A8) & ChrW(&H5931) & ChrW(&H8D25) & ChrW(&HFF0C) & ChrW(&H9000) & ChrW(&H51FA) & ChrW(&H7801) & " " & exitCode & ChrW(&H3002) & ChrW(&H8BF7) & ChrW(&H8FD0) & ChrW(&H884C) & " win_start.bat " & ChrW(&H67E5) & ChrW(&H770B) & ChrW(&H5177) & ChrW(&H4F53) & ChrW(&H9519) & ChrW(&H8BEF) & ChrW(&H3002), vbCritical, "MiniJMP startup error"
End If
Set WshShell = Nothing
WScript.Quit exitCode
