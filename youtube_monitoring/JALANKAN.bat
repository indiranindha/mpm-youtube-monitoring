@echo off
chcp 65001 >nul
cd /d "%~dp0"
echo MPM YouTube Monitoring - mencari video dan membuat dashboard ...
echo.
where py >nul 2>nul
if %errorlevel%==0 (
  py -3 yt_crawl.py %*
) else (
  python yt_crawl.py %*
)
echo.
pause
