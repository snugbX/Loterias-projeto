@echo off
setlocal

cd /d "%~dp0"
set PYTHONDONTWRITEBYTECODE=1

echo Atualizando resultados e preparando envio ao GitHub...
echo.

where py >nul 2>nul
if %errorlevel%==0 (
    py -3 src\update_lottery_data.py --publish
) else (
    python src\update_lottery_data.py --publish
)

echo.
pause
