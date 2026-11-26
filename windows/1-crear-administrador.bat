@echo off
title Tickets de Soporte - Crear administrador (jefe)
cd /d "%~dp0"
echo.
echo  ==========================================================
echo   Crear (o restablecer) un usuario JEFE / ADMINISTRADOR
echo  ==========================================================
echo.
echo  Si el usuario ya existe, se le pone la nueva contrasena.
echo  Los tecnicos se crean despues, desde el sistema:
echo  menu (su nombre) - Administracion - Usuarios.
echo.
"%~dp0python\python.exe" -m app.cli crear-admin
echo.
pause
