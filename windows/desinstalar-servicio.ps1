# Tickets de Soporte - quita el inicio automatico (NO borra los datos).
# No toca las tareas de la Pizarra de Interinatos.
# Este archivo usa solo caracteres ASCII a proposito (PowerShell 5.1).

$tarea = 'Tickets de Soporte'
$tareaRespaldo = 'Tickets de Soporte - Respaldo'
$tareaResumen = 'Tickets de Soporte - Resumen'

Stop-ScheduledTask -TaskName $tarea -ErrorAction SilentlyContinue
Unregister-ScheduledTask -TaskName $tarea -Confirm:$false -ErrorAction SilentlyContinue
Unregister-ScheduledTask -TaskName $tareaRespaldo -Confirm:$false -ErrorAction SilentlyContinue
Unregister-ScheduledTask -TaskName $tareaResumen -Confirm:$false -ErrorAction SilentlyContinue
Get-NetFirewallRule -DisplayName 'Tickets de Soporte' -ErrorAction SilentlyContinue | Remove-NetFirewallRule

Write-Host ''
Write-Host '  Listo: se quito el inicio automatico, el respaldo nocturno, el resumen diario' -ForegroundColor Green
Write-Host '  y la regla del firewall. Los datos (carpeta "datos") y los respaldos NO se borraron.'
