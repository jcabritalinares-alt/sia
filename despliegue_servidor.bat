@echo off
title SIA WEB - Despliegue Completo de Servidor (Localhost + Tunel NPX)
color 0A
cd /d "%~dp0"

echo ==============================================================================
echo       SISTEMA INSTITUCIONAL DE ATENCION E INVENTARIO (SIA)
echo        DESPLIEGUE COMPLETO: SERVIDOR LOCALHOST + TUNEL NPX
echo ==============================================================================
echo.

:: 1. Verificar Entorno Virtual Python
if not exist "%~dp0venv\Scripts\python.exe" (
    echo [ERROR] No se encontro el entorno virtual en: "%~dp0venv"
    echo Asegurese de que la carpeta venv exista en este directorio.
    pause
    exit /b 1
)

:: 2. Iniciar el Servidor de Producción Waitress Multihilo (escuchando en 0.0.0.0:8000)
echo [1/3] Iniciando Servidor SIA Multihilo (Waitress WSGI en 0.0.0.0:8000)...
start "Servidor SIA (Waitress Multihilo - Puerto 8000)" cmd /k ""%~dp0venv\Scripts\python.exe" "%~dp0servidor.py""

ping 127.0.0.1 -n 3 >nul

:: 3. Iniciar el Túnel Público NPX LocalTunnel
echo [2/3] Iniciando Tunel Publico NPX LocalTunnel (siaweb-venezuela)...
start "Tunel NPX LocalTunnel (siaweb-venezuela)" "%~dp0iniciar_tunel.bat"

ping 127.0.0.1 -n 3 >nul

:: 4. Abrir Navegador en Localhost
echo [3/3] Abriendo panel del sistema en el navegador local...
start http://localhost:8000/login/

echo.
echo ==============================================================================
echo   ¡DESPLIEGUE COMPLETO DE SERVIDOR EJECUTANDOSE CON EXITO!
echo.
echo   * Acceso Localhost:  http://localhost:8000/login/
echo   * Acceso en Internet: https://siaweb-venezuela.loca.lt
echo ==============================================================================
echo.
echo Puede mantener esta ventana minimizada o cerrarla cuando lo desee.
echo Los servicios del servidor y del tunel continuan activos en sus ventanas.
echo.
pause
