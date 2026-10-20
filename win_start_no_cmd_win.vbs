Set WshShell = CreateObject("WScript.Shell")
Set FSO = CreateObject("Scripting.FileSystemObject")
scriptDir = FSO.GetParentFolderName(WScript.ScriptFullName)
exitCode = WshShell.Run("""" & scriptDir & "\win_start.bat""", 0, True)
If exitCode = 9009 Then
    MsgBox "Python was not found. Activate the Minijmp Python environment and run win_start.bat.", vbCritical, "Minijmp startup error"
End If
Set WshShell = Nothing
WScript.Quit exitCode
