@echo off
chcp 65001 >nul
title Elphara Fit - connexion Dolphin
cd /d "%~dp0"
where python >nul 2>nul
if %errorlevel%==0 (
  python elphara_live.py %*
) else (
  py -3 elphara_live.py %*
)
echo.
echo Le programme s'est arrete. Appuie sur une touche pour fermer.
pause >nul
