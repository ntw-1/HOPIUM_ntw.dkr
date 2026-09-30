@echo off
echo ===================================================
echo HOPIUM - SIH26170 Setup and Execution Script
echo ===================================================

echo.
echo Installing dependencies...
pip install -r requirements.txt
if %errorlevel% neq 0 (
    echo Failed to install dependencies.
    pause
    exit /b %errorlevel%
)

echo.
echo Generating datasets...
python scripts\generate_datasets.py
python scripts\generate_v2.py

echo.
echo Running Model Lab to train and register models...
python scripts\run_model_lab.py

echo.
echo Starting the HOPIUM Web App...
echo A browser window should open automatically.
python scripts\run_screening_ui.py

pause
