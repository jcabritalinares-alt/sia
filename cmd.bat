@echo off
title Django Inventory Server (Red LAN 0.0.0.0:8000)
cd /d "%~dp0"
call venv\Scripts\activate
python manage.py runserver 0.0.0.0:8000
pause