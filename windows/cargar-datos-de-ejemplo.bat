@echo off
title Tickets de Soporte - Datos de ejemplo
cd /d "%~dp0"
echo.
echo  Carga datos FICTICIOS para practicar: 14 areas, 5 tecnicos de ejemplo
echo  (tecnico1 ... tecnico5, contrasena practica123) y unos 40 tickets.
echo  Solo funciona si todavia no hay tickets cargados.
echo.
echo  Para empezar despues con los datos reales: detenga el sistema y borre
echo  la carpeta "datos" (se pierden TODOS los datos), luego vuelva a crear
echo  el administrador.
echo.
set /p "OK=Escriba SI para cargar los datos de ejemplo: "
if /i not "%OK%"=="SI" exit /b 0
"%~dp0python\python.exe" -m app.cli demo
echo.
pause
