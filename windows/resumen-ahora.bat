@echo off
title Tickets de Soporte - Resumen del dia
cd /d "%~dp0"
echo.
echo  Generando el resumen del dia en la carpeta "reportes"...
echo  (si se configuro el correo en configuracion.txt, tambien se envia)
echo.
"%~dp0python\python.exe" -m app.cli resumen
echo.
pause
