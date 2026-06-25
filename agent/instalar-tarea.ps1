<#
instalar-tarea.ps1 — registra/desregistra la Tarea Programada del agente.

La tarea corre el .exe en modo "un disparo" cada N minutos: el Programador de tareas
es el bucle (robusto, sobrevive reboots; no se usa --watch).

Instalar:
    .\instalar-tarea.ps1 -ExePath "C:\sxml\sxml_agent.exe" -ConfigPath "C:\sxml\agent.toml" -IntervaloMin 30
Desinstalar:
    .\instalar-tarea.ps1 -Accion uninstall

Nota: la tarea corre con el usuario actual y solo cuando está con sesión iniciada
(LogonType Interactive), para no guardar contraseñas. La PC del contador debe estar
con sesión iniciada durante el horario de trabajo.
#>
param(
    [ValidateSet("install", "uninstall")] [string]$Accion = "install",
    [string]$ExePath,
    [string]$ConfigPath,
    [int]$IntervaloMin = 30,
    [string]$NombreTarea = "SistemaXML-Agente"
)
$ErrorActionPreference = "Stop"

if ($Accion -eq "uninstall") {
    Unregister-ScheduledTask -TaskName $NombreTarea -Confirm:$false
    Write-Host "Tarea '$NombreTarea' desinstalada."
    return
}

if (-not $ExePath -or -not (Test-Path $ExePath)) { throw "ExePath no existe: $ExePath" }
if (-not $ConfigPath -or -not (Test-Path $ConfigPath)) { throw "ConfigPath no existe: $ConfigPath" }

$accion = New-ScheduledTaskAction -Execute $ExePath -Argument "--config `"$ConfigPath`""
$trigger = New-ScheduledTaskTrigger -Once -At (Get-Date) `
    -RepetitionInterval (New-TimeSpan -Minutes $IntervaloMin)
$settings = New-ScheduledTaskSettingsSet -StartWhenAvailable -MultipleInstances IgnoreNew
$principal = New-ScheduledTaskPrincipal -UserId $env:USERNAME -LogonType Interactive

Register-ScheduledTask -TaskName $NombreTarea -Action $accion -Trigger $trigger `
    -Settings $settings -Principal $principal -Force `
    -Description "Sube los XML nuevos al backend Sistema XML cada $IntervaloMin min." | Out-Null

Write-Host "Tarea '$NombreTarea' instalada: corre '$ExePath --config $ConfigPath' cada $IntervaloMin min."
Get-ScheduledTask -TaskName $NombreTarea | Format-Table TaskName, State
