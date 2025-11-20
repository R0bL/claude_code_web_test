@echo off

rem Activate virtual environment for Windows
rem Usage: source.bat

if exist .venv\Scripts\activate.bat (
    call .venv\Scripts\activate.bat
) else (
    echo Virtual environment not found. Creating one...
    python -m venv .venv
    call .venv\Scripts\activate.bat
    pip install -r requirements.txt
)

echo Environment activated. Python version:
python --version
