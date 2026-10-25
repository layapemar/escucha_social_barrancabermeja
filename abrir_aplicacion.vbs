Set shell = CreateObject("WScript.Shell")
Set fs = CreateObject("Scripting.FileSystemObject")
carpeta = fs.GetParentFolderName(WScript.ScriptFullName)
python = carpeta & "\.venv312\Scripts\python.exe"
aplicacion = carpeta & "\app.py"
If Not fs.FileExists(python) Then
  MsgBox "No se encuentra el entorno .venv312. Consulta el README del proyecto.", 16, "Escucha Social"
  WScript.Quit
End If
shell.CurrentDirectory = carpeta
comando = Chr(34) & python & Chr(34) & " -m streamlit run " & Chr(34) & aplicacion & Chr(34) & " --server.address 127.0.0.1 --server.port 8501 --server.headless true --browser.gatherUsageStats false"
shell.Run comando, 0, False
WScript.Sleep 5000
shell.Run "http://127.0.0.1:8501", 1, False
