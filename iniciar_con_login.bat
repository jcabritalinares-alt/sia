@echo off
title Gestor de Inicio - Inventario Nuevo

echo [1/2] Iniciando el servidor de produccion SIA (Waitress Multihilo) en otra ventana...
start "Servidor SIA (Waitress)" cmd /k "cd /d "%~dp0" && call venv\Scripts\activate && python servidor.py"

echo [2/2] Iniciando tunel publico NPX LocalTunnel (siaweb-venezuela)...
start "Tunel NPX LocalTunnel" cmd /k "cd /d "%~dp0" && call iniciar_tunel.bat"

timeout /t 2 /nobreak >nul
start http://localhost:8000/login/

echo.
echo Servidor y Tunel NPX iniciados.
pause