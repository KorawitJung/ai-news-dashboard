@echo off
REM Starts AI Daily and opens it in your browser.
cd /d "%~dp0"
if not exist ".venv\Scripts\python.exe" (
  echo First run: creating virtual environment...
  py -m venv .venv || python -m venv .venv
  ".venv\Scripts\python.exe" -m pip install -r requirements.txt
)
start "" http://127.0.0.1:5050
".venv\Scripts\python.exe" app.py
