@echo off
cd /d "%~dp0"
if exist dashboard.html (start "" dashboard.html) else (echo Belum ada dashboard. Jalankan JALANKAN.bat dulu. & pause)
