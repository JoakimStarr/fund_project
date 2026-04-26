@echo off
setlocal
cd /d %~dp0

where python >nul 2>nul
if errorlevel 1 (
  echo Python is not available. Please install Python 3.10+ and retry.
  pause
  exit /b 1
)

if not exist .venv (
  echo Creating virtual environment...
  python -m venv .venv
  if errorlevel 1 goto fail
)

call .venv\Scripts\activate
python -m pip install --upgrade pip
if errorlevel 1 goto fail
pip install -r requirements.txt
if errorlevel 1 goto fail

start http://127.0.0.1:8000
python -m uvicorn backend.app.main:app --host 127.0.0.1 --port 8000
if errorlevel 1 goto fail
goto end

:fail
echo.
echo Startup failed. See the error above.
pause
exit /b 1

:end
pause
