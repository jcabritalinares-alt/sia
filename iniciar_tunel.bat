@echo off
title SIA WEB - Tunel Publico (NPX LocalTunnel)
color 0B
cd /d "%~dp0"

:: 1. Asegurar rutas de Node.js y NPX en el PATH de Windows
set "PATH=C:\Program Files\nodejs;%APPDATA%\npm;%LOCALAPPDATA%\Programs\nodejs;%PATH%"

echo ==============================================================================
echo       SISTEMA INSTITUCIONAL DE ATENCION E INVENTARIO (SIA)
echo               TUNEL PUBLICO EN INTERNET (NPX LOCALTUNNEL)
echo ==============================================================================
echo.
echo   * Dominio Asignado: https://siaweb-venezuela.loca.lt
echo   * Puerto Local:     http://127.0.0.1:8000
echo.
echo   [!] Para detener el tunel, presione Ctrl + C o cierre esta ventana.
echo ==============================================================================
echo.

:: 2. Registrar el túnel en el archivo .active_tunnel del sistema
echo https://siaweb-venezuela.loca.lt> "%~dp0.active_tunnel"

:: 3. Verificar disponibilidad de NPX
where.exe npx.cmd >nul 2>&1
if %errorlevel% equ 0 (
    set NPX_CMD=npx.cmd
) else (
    where.exe npx >nul 2>&1
    if %errorlevel% equ 0 (
        set NPX_CMD=npx
    ) else if exist "C:\Program Files\nodejs\npx.cmd" (
        set NPX_CMD="C:\Program Files\nodejs\npx.cmd"
    ) else (
        echo [ERROR] No se encontro Node.js / NPX instalado en el sistema.
        echo Por favor asegurese de tener instalado Node.js desde: https://nodejs.org/
        echo.
        pause
        exit /b 1
    )
)

echo [*] Conectando tunel publico con: %NPX_CMD% localtunnel...
echo.

call %NPX_CMD% -y localtunnel --port 8000 --subdomain siaweb-venezuela

if %errorlevel% neq 0 (
    echo.
    echo [REINTENTO] El tunel se desconecto o fallo. Reintentando conexion...
    ping 127.0.0.1 -n 3 >nul
    call %NPX_CMD% -y localtunnel --port 8000 --subdomain siaweb-venezuela
)

echo.
echo [AVISO] El proceso del tunel se ha detenido.
pause
