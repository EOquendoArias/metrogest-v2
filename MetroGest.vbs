Set WshShell = CreateObject("WScript.Shell")
carpeta = Left(WScript.ScriptFullName, InStrRev(WScript.ScriptFullName, "\"))
WshShell.Run """" & carpeta & "iniciar.bat""", 0, False
