@echo off
setlocal
cd /d "%~dp0"

set "PYTHONDONTWRITEBYTECODE=1"
set "LOTTERY_AUTO_OPEN_BROWSER=1"
set "HOST=127.0.0.1"
set "PORT=5000"

echo Iniciando Gerador de Jogos de Loterias...
echo Mantenha esta janela aberta enquanto usa o sistema.
echo.

where py >nul 2>nul
if %errorlevel%==0 (
    py -3 "%~dp0src\app.py"
    goto :end
)

where python >nul 2>nul
if %errorlevel%==0 (
    python "%~dp0src\app.py"
    goto :end
)

echo Python nao encontrado. Instale o Python ou rode manualmente dentro de src: py app.py

:end
echo.
pause
