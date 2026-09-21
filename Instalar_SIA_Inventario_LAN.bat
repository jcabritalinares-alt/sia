@echo off
title Instalador SIA Inventario - Escritorio Nativo y Red LAN
color 0A
cd /d "%~dp0"

echo ======================================================================
echo   INSTALADOR DE APLICACION NATIVA DE WINDOWS - SIA INVENTARIO
echo ======================================================================
echo.
echo Instalando la aplicacion nativa en su equipo...
echo.

powershell -ExecutionPolicy Bypass -NoProfile -Command "$source = '%~dp0'; $target = Join-Path $env:LOCALAPPDATA 'SIA-Inventario'; if (-not (Test-Path $target)) { New-Item -ItemType Directory -Path $target -Force | Out-Null }; Copy-Item (Join-Path $source '*') $target -Recurse -Force; $wsh = New-Object -ComObject WScript.Shell; $desktop = [System.Environment]::GetFolderPath('Desktop'); $shortcutApp = $wsh.CreateShortcut((Join-Path $desktop 'SIA Inventario - Escritorio.lnk')); $shortcutApp.TargetPath = Join-Path $target 'SIA_Inventario.exe'; $shortcutApp.WorkingDirectory = $target; $shortcutApp.Description = 'Sistema de Inventario Nativo de Windows'; $shortcutApp.Save(); $shortcutNet = $wsh.CreateShortcut((Join-Path $desktop 'Configurar Red LAN SIA.lnk')); $shortcutNet.TargetPath = Join-Path $target 'venv\Scripts\python.exe'; $shortcutNet.Arguments = 'configurador_red.py'; $shortcutNet.WorkingDirectory = $target; $shortcutNet.Description = 'Configuracion de IP y Modo Servidor/Cliente LAN'; $shortcutNet.Save(); Write-Host 'ACCESOS DIRECTOS CREADOS EN EL ESCRITORIO DE WINDOWS' -ForegroundColor Green"

echo.
echo ======================================================================
echo   ¡INSTALACION COMPLETADA CON EXITO!
echo.
echo   Se han creado 2 accesos directos en su Escritorio:
echo     1. "SIA Inventario - Escritorio" (Aplicación Nativa .EXE)
echo     2. "Configurar Red LAN SIA" (Panel de IP / Red)
echo ======================================================================
echo.
echo Presione cualquier tecla para cerrar este asistente...
pause >nul
