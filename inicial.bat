@echo off
title Sistema SIA - Lanzador Oficial
color 0B
cd /d "%~dp0"

:: 1. Parámetros directos por línea de comandos (ej: inicial.bat 1, inicial.bat console)
if "%1"=="1" goto OPCION1
if "%1"=="2" goto OPCION2
if "%1"=="3" goto OPCION3
if "%1"=="4" goto OPCION4
if "%1"=="5" goto OPCION5
if "%1"=="console" goto MENU
if "%1"=="-c" goto MENU

:: 2. Verificar existencia del entorno virtual
if not exist "%~dp0venv\Scripts\activate.bat" (
    echo [ERROR] No se encontro el entorno virtual en: "%~dp0venv"
    echo Asegurese de que la carpeta venv exista en este directorio.
    pause
    exit /b 1
)

:: 3. Lanzar la Interfaz Grafica de Escritorio (Panel Moderno con Botones y Logos)
if exist "%~dp0venv\Scripts\pythonw.exe" (
    start "" "%~dp0venv\Scripts\pythonw.exe" "%~dp0lanzador_gui.py"
    exit /b 0
)

if exist "%~dp0venv\Scripts\python.exe" (
    start "" "%~dp0venv\Scripts\python.exe" "%~dp0lanzador_gui.py"
    exit /b 0
)

:: 4. Modo de Respaldo por Consola si la interfaz grafica no se pudiera cargar
echo ==============================================================================
echo        SISTEMA INSTITUCIONAL DE ATENCION E INVENTARIO (SIA)
echo               Servidor de Produccion (Waitress WSGI Multihilo)
echo ==============================================================================
echo.

echo [*] Activando entorno virtual Python (venv)...
call "%~dp0venv\Scripts\activate.bat"

:MENU
echo.
echo ==============================================================================
echo Seleccione el modo de inicio deseado:
echo.
echo   [1] Despliegue Completo de Servidor (Localhost + Tunel NPX + Navegador)
echo   [2] Iniciar Servidor Local y Abrir Navegador (http://localhost:8000/login/)
echo   [3] Iniciar Solo Tunel Publico NPX (LocalTunnel siaweb-venezuela)
echo   [4] Iniciar Solo Servidor en esta Consola (Modo Diagnostico)
echo   [5] Generar Copia de Seguridad (Respaldo DB PostgreSQL)
echo   [6] Salir
echo ==============================================================================
echo.
choice /C 123456 /M "Seleccione una opcion [1-6]"

if errorlevel 6 goto FIN
if errorlevel 5 goto OPCION5
if errorlevel 4 goto OPCION4
if errorlevel 3 goto OPCION3
if errorlevel 2 goto OPCION2
if errorlevel 1 goto OPCION1

:OPCION1
echo.
echo ==============================================================================
echo [1/3] Iniciando Servidor SIA Multihilo (Waitress en 0.0.0.0:8000)...
start "Servidor SIA (Waitress Multihilo)" cmd /k ""%~dp0venv\Scripts\python.exe" "%~dp0servidor.py""
ping 127.0.0.1 -n 3 >nul
echo [2/3] Iniciando Tunel Publico NPX LocalTunnel (siaweb-venezuela)...
start "Tunel NPX LocalTunnel" "%~dp0iniciar_tunel.bat"
ping 127.0.0.1 -n 3 >nul
echo [3/3] Abriendo navegador local...
start http://localhost:8000/login/
echo.
echo [*] Despliegue completo ejecutandose:
echo     - Localhost: http://localhost:8000/login/
echo     - Publico:   https://siaweb-venezuela.loca.lt
echo.
echo Regresando al menu en 3 segundos...
ping 127.0.0.1 -n 4 >nul
goto MENU

:OPCION2
echo.
echo ==============================================================================
echo [*] Iniciando Servidor SIA (Waitress Multihilo) y abriendo navegador local...
echo [*] Acceso local: http://localhost:8000/login/
start "Servidor SIA Local" cmd /k ""%~dp0venv\Scripts\python.exe" "%~dp0servidor.py""
ping 127.0.0.1 -n 3 >nul
start http://localhost:8000/login/
echo.
echo [*] Servidor iniciado. Regresando al menu...
ping 127.0.0.1 -n 3 >nul
goto MENU

:OPCION3
echo.
echo ==============================================================================
echo [*] Iniciando Solo Tunel Publico NPX LocalTunnel (siaweb-venezuela)...
start "Tunel NPX LocalTunnel" "%~dp0iniciar_tunel.bat"
echo.
echo [*] Tunel iniciado. Regresando al menu...
ping 127.0.0.1 -n 3 >nul
goto MENU

:OPCION4
echo.
echo ==============================================================================
echo [*] Iniciando Servidor SIA directamente en esta consola (Presione Ctrl+C para salir)...
python servidor.py
goto MENU

:OPCION5
echo.
echo ==============================================================================
echo [*] Generando Copia de Seguridad de la Base de Datos PostgreSQL...
if not exist "backups" mkdir "backups"
python manage.py dumpdata --natural-foreign --natural-primary -e contenttypes -e auth.Permission --indent 2 -o "backups\respaldo_sia.json"
echo [*] Respaldo generado con exito en la carpeta 'backups\respaldo_sia.json'.
echo.
pause
goto MENU

:FIN
exit /b 0