' Launch the Discord watchdog with no visible window (0 = hidden).
Option Explicit
Dim sh, fso, root, ps, script, cmd
Set fso = CreateObject("Scripting.FileSystemObject")
Set sh = CreateObject("WScript.Shell")
root = fso.GetParentFolderName(WScript.ScriptFullName)
ps = sh.ExpandEnvironmentStrings("%SystemRoot%\System32\WindowsPowerShell\v1.0\powershell.exe")
script = root & "\watch_discord.ps1"
cmd = """" & ps & """ -NoProfile -WindowStyle Hidden -ExecutionPolicy Bypass -File """ & script & """"
sh.CurrentDirectory = root
sh.Run cmd, 0, False
