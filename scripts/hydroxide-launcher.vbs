' Hydroxide hidden launcher for ProtonMail bridge (protonesk dependency).
' Runs hydroxide serve fully hidden (window style 0) with an auto-restart loop.
' Launched at logon by the "Hydroxide" Scheduled Task via wscript.exe.
' wscript itself is windowless; hydroxide inherits the hidden context -> no console flash.

Dim sh, hydroxide, goBin
Set sh = CreateObject("WScript.Shell")

' Resolve hydroxide.exe: PATH first, then %USERPROFILE%\go\bin
hydroxide = ""
goBin = sh.ExpandEnvironmentStrings("%USERPROFILE%\go\bin\hydroxide.exe")

Dim fso
Set fso = CreateObject("Scripting.FileSystemObject")
If fso.FileExists(goBin) Then
    hydroxide = goBin
Else
    hydroxide = "hydroxide.exe" ' rely on PATH
End If

Do
    ' window style 0 = hidden, bWaitOnReturn = True -> block until it exits, then restart
    sh.Run """" & hydroxide & """ serve", 0, True
    WScript.Sleep 5000
Loop
