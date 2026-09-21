@echo off
title Habilitar Acceso por Red LAN - Puerto 8000 (SIA Web)
color 0A
cd /d "%~dp0"

echo ======================================================================
echo    CONFIGURANDO REGLA DEL FIREWALL PARA PERMITIR ACCESO POR IP/LAN
echo ======================================================================
echo.

net session >nul 2>&1
if %errorLevel% neq 0 (
    echo [AVISO] Se requieren privilegios de Administrador.
    echo Por favor haga clic derecho sobre este archivo y seleccione:
    echo "Ejecutar como administrador"
    echo.
    pause
    exit /b 1
)

echo [*] Abriendo puerto TCP 8000 en el Firewall de Windows...
netsh advfirewall firewall delete rule name="SIA Web Port 8000" >nul 2>&1
netsh advfirewall firewall add rule name="SIA Web Port 8000" dir=in action=allow protocol=TCP localport=8000 profile=any

echo.
echo [*] Regla agregada exitosamente al Firewall de Windows.
echo Ahora los dispositivos en su misma red local (celulares, tablets, otras PCs)
echo podran conectarse sin bloqueos al servidor SIA en el puerto 8000.
echo.
pause
