@echo off
chcp 65001 >nul
cd /d "%~dp0"
python -m print_server.main
pause
