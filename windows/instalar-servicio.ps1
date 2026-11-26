# Tickets de Soporte - instala el inicio automatico en Windows.
# (Se ejecuta desde 3-instalar-como-servicio.bat, como administrador.)
#
# Crea tres tareas programadas de Windows que corren como SYSTEM:
#   1. "Tickets de Soporte": inicia el sistema al encender la PC, aunque nadie
#      inicie sesion, y lo vuelve a levantar cada 5 minutos si se detuvo.
#   2. "Tickets de Soporte - Respaldo": respaldo automatico todas las noches (23:45).
#   3. "Tickets de Soporte - Resumen": resumen diario en la carpeta "reportes".
# Ademas abre el puerto en el Firewall de Windows.
#
# Convive con la Pizarra de Interinatos (C:\Pizarra, puerto 8090): usa otra carpeta,
# otro puerto, otros nombres de tarea y otro horario de respaldo (23:30 la Pizarra).
#
# Este archivo usa solo caracteres ASCII a proposito (PowerShell 5.1).

$ErrorActionPreference = 'Stop'
$base = Split-Path -Parent $PSScriptRoot
$python = Join-Path $base 'python\python.exe'
$pythonw = Join-Path $base 'python\pythonw.exe'
$tarea = 'Tickets de Soporte'
$tareaRespaldo = 'Tickets de Soporte - Respaldo'
$tareaResumen = 'Tickets de Soporte - Resumen'
$reglaFirewall = 'Tickets de Soporte'

function Paso($texto) { Write-Host ''; Write-Host "  >> $texto" -ForegroundColor Cyan }

if (-not (Test-Path $pythonw)) {
    Write-Host "  No se encuentra $pythonw" -ForegroundColor Red
    Write-Host '  Verifique que descomprimio el ZIP completo.'
    exit 1
}

# Puerto y hora del resumen configurados
$puerto = 8091
$horaResumen = '13:30'
$config = Join-Path $base 'configuracion.txt'
if (Test-Path $config) {
    foreach ($linea in Get-Content $config) {
        if ($linea -match '^\s*PUERTO\s*=\s*(\d+)\s*$') { $puerto = [int]$Matches[1] }
        if ($linea -match '^\s*HORA_RESUMEN\s*=\s*(\d{1,2}:\d{2})\s*$') { $horaResumen = $Matches[1] }
    }
}

Write-Host ''
Write-Host '  =========================================================='
Write-Host '   Tickets de Soporte - Instalacion como servicio'
Write-Host '  =========================================================='
Write-Host "   Carpeta: $base"
Write-Host "   Puerto:  $puerto"

# Si habia una instalacion anterior, se detiene y se reemplaza
Paso 'Deteniendo una instalacion anterior (si existe)...'
Stop-ScheduledTask -TaskName $tarea -ErrorAction SilentlyContinue
Start-Sleep -Seconds 2

# El puerto no debe estar ocupado por otro programa (XAMPP, la Pizarra, etc.)
$ocupado = Get-NetTCPConnection -State Listen -LocalPort $puerto -ErrorAction SilentlyContinue
if ($ocupado) {
    $proc = Get-Process -Id ($ocupado | Select-Object -First 1).OwningProcess -ErrorAction SilentlyContinue
    Write-Host ''
    if ($proc -and $proc.ProcessName -like 'python*') {
        Write-Host "  El puerto $puerto lo esta usando Python: probablemente quedo abierta la ventana" -ForegroundColor Red
        Write-Host '  de 2-probar-en-esta-ventana.bat. Cierrela y vuelva a ejecutar este instalador.'
    } else {
        Write-Host "  El puerto $puerto ya lo usa otro programa: $($proc.ProcessName)" -ForegroundColor Red
        Write-Host '  Cambie PUERTO en configuracion.txt (por ejemplo 8092) y vuelva a ejecutar este instalador.'
    }
    exit 1
}

Paso 'Creando la tarea de inicio automatico...'
$accion = New-ScheduledTaskAction -Execute $pythonw -Argument '-m app.servidor' -WorkingDirectory $base
$alIniciar = New-ScheduledTaskTrigger -AtStartup
# Vigilancia: cada 5 minutos intenta iniciarlo; si ya esta corriendo, no hace nada
$vigilancia = New-ScheduledTaskTrigger -Once -At (Get-Date).AddMinutes(1) `
    -RepetitionInterval (New-TimeSpan -Minutes 5) -RepetitionDuration (New-TimeSpan -Days 3650)
$principal = New-ScheduledTaskPrincipal -UserId 'SYSTEM' -LogonType ServiceAccount -RunLevel Highest
$ajustes = New-ScheduledTaskSettingsSet -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries `
    -StartWhenAvailable -MultipleInstances IgnoreNew -ExecutionTimeLimit ([TimeSpan]::Zero) `
    -RestartCount 999 -RestartInterval (New-TimeSpan -Minutes 1)
Register-ScheduledTask -TaskName $tarea -Action $accion -Trigger @($alIniciar, $vigilancia) `
    -Principal $principal -Settings $ajustes -Force `
    -Description 'Sistema de Tickets de la Seccion de Servicios Informaticos (servidor web).' | Out-Null

Paso 'Creando el respaldo automatico (todas las noches a las 23:45)...'
$destino = Join-Path $base 'respaldos'
$accionR = New-ScheduledTaskAction -Execute $python -Argument "-m app.cli respaldo `"$destino`"" -WorkingDirectory $base
$nocturno = New-ScheduledTaskTrigger -Daily -At '23:45'
$ajustesR = New-ScheduledTaskSettingsSet -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries `
    -StartWhenAvailable -ExecutionTimeLimit (New-TimeSpan -Hours 1)
Register-ScheduledTask -TaskName $tareaRespaldo -Action $accionR -Trigger $nocturno `
    -Principal $principal -Settings $ajustesR -Force `
    -Description 'Respaldo nocturno del sistema de Tickets.' | Out-Null

Paso "Creando el resumen diario (de lunes a viernes a las $horaResumen)..."
$accionS = New-ScheduledTaskAction -Execute $python -Argument '-m app.cli resumen' -WorkingDirectory $base
$diario = New-ScheduledTaskTrigger -Weekly -DaysOfWeek Monday, Tuesday, Wednesday, Thursday, Friday -At $horaResumen
Register-ScheduledTask -TaskName $tareaResumen -Action $accionS -Trigger $diario `
    -Principal $principal -Settings $ajustesR -Force `
    -Description 'Resumen diario de tickets (carpeta reportes y, si se configuro, correo).' | Out-Null

Paso "Abriendo el puerto $puerto en el Firewall de Windows..."
Get-NetFirewallRule -DisplayName $reglaFirewall -ErrorAction SilentlyContinue | Remove-NetFirewallRule
New-NetFirewallRule -DisplayName $reglaFirewall -Direction Inbound -Protocol TCP -LocalPort $puerto `
    -Action Allow -Profile Any | Out-Null

Paso 'Iniciando el sistema de Tickets...'
Start-ScheduledTask -TaskName $tarea
$ok = $false
# Se consulta directo a esta PC, SIN pasar por el proxy institucional (si lo hay)
$cliente = New-Object System.Net.WebClient
$cliente.Proxy = $null
for ($i = 0; $i -lt 60; $i++) {
    Start-Sleep -Seconds 1
    try {
        $respuesta = $cliente.DownloadString("http://127.0.0.1:$puerto/salud")
        if ($respuesta -match 'tickets') { $ok = $true; break }
    } catch { }
}

Write-Host ''
if ($ok) {
    Write-Host '  LISTO: el sistema de Tickets esta funcionando.' -ForegroundColor Green
    Write-Host ''
    Write-Host "   En esta PC:          http://localhost:$puerto"
    $ips = Get-NetIPAddress -AddressFamily IPv4 -ErrorAction SilentlyContinue |
        Where-Object { $_.IPAddress -notlike '127.*' -and $_.IPAddress -notlike '169.254.*' } |
        Select-Object -ExpandProperty IPAddress
    foreach ($ip in $ips) { Write-Host "   Desde otras PCs:     http://${ip}:$puerto" }
    Write-Host ''
    Write-Host '  Se iniciara solo cada vez que se encienda la PC.'
} else {
    Write-Host '  El sistema de Tickets no respondio todavia.' -ForegroundColor Yellow
    Write-Host "  Revise el archivo de registro: $base\datos\registros\tickets.log"
    Write-Host '  Si el puerto esta ocupado por otro programa, cambie PUERTO en configuracion.txt'
    Write-Host '  y vuelva a ejecutar este instalador.'
}
