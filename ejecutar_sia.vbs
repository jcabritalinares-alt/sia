Set WshShell = CreateObject("WScript.Shell")
Set FSO = CreateObject("Scripting.FileSystemObject")
ScriptDir = FSO.GetParentFolderName(WScript.ScriptFullName)
WshShell.CurrentDirectory = ScriptDir
If FSO.FileExists(ScriptDir & "\venv\Scripts\pythonw.exe") Then
    WshShell.Run Chr(34) & ScriptDir & "\venv\Scripts\pythonw.exe" & Chr(34) & " servidor.py", 0, False
Else
    WshShell.Run "python servidor.py", 0, False
End If