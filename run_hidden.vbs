' Hide console and run the updater from source (dev).
Set fso = CreateObject("Scripting.FileSystemObject")
Set sh = CreateObject("WScript.Shell")
root = fso.GetParentFolderName(WScript.ScriptFullName)
sh.CurrentDirectory = root
cmd = """" & root & "\.venv\Scripts\pythonw.exe"" -m ytm_discord"
sh.Run cmd, 0, False
