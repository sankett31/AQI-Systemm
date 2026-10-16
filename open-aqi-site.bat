@echo off
setlocal
cd /d "%~dp0"
if exist "%LocalAppData%\Programs\Python\Python313\python.exe" (
  "%LocalAppData%\Programs\Python\Python313\python.exe" server.py
) else (
  python server.py
)
endlocal
