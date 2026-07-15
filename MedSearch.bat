@echo off
REM ============================================================================
REM  MedSearch - Windows double-click launcher (source / git-clone distribution)
REM
REM  Windows counterpart of MedSearch.command. On first run it sets up a local
REM  virtual environment and installs the dependencies; after that it just
REM  launches the app. Running from a git clone keeps the in-app "Update" button
REM  working (it runs "git pull").
REM
REM  Usage: double-click this file, or run  MedSearch.bat  from a terminal.
REM ============================================================================
setlocal
cd /d "%~dp0"

echo ----------------------------------------------
echo   MedSearch
echo ----------------------------------------------

REM -- Need Python 3 -----------------------------------------------------------
where python >nul 2>&1
if errorlevel 1 (
  echo   [X] Python was not found on PATH.
  echo       Install Python 3 from https://python.org and tick
  echo       "Add Python to PATH", then double-click MedSearch.bat again.
  echo.
  pause
  exit /b 1
)

REM -- First-run setup: virtual environment ------------------------------------
if not exist ".venv\Scripts\activate.bat" (
  echo   First run: setting up the environment ^(this happens once^)...
  python -m venv .venv
  if errorlevel 1 (
    echo   [X] Could not create the virtual environment. Is Python 3 installed?
    pause
    exit /b 1
  )
)
call ".venv\Scripts\activate.bat"

REM -- Install/refresh dependencies (flask + pywebview) ------------------------
set "NEED_INSTALL=0"
python -c "import flask" 2>nul || set "NEED_INSTALL=1"
python -c "import webview" 2>nul || set "NEED_INSTALL=1"
if "%NEED_INSTALL%"=="1" (
  echo   Installing dependencies...
  python -m pip install --quiet --upgrade pip
  if exist requirements.txt (
    python -m pip install --quiet -r requirements.txt
  ) else (
    python -m pip install --quiet flask pywebview
  )
)

REM -- Launch ------------------------------------------------------------------
echo   Starting MedSearch...
echo   ^(Close the app window to quit.^)
echo.
python app.py
