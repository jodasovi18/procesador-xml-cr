<#
build.ps1 — construye sxml_agent.exe (PyInstaller, one-file).

Uso:
    .\build.ps1                                  # usa "python" del PATH
    .\build.ps1 -Python "C:\ruta\python.exe"     # intérprete explícito

En este repo de desarrollo, pasar el venv:
    .\build.ps1 -Python "C:\Users\Usuario\Desktop\Sistemas\sistema-xml-web\backend\.venv\Scripts\python.exe"

Resultado: agent\dist\sxml_agent.exe
#>
param(
    [string]$Python = "python"
)
$ErrorActionPreference = "Stop"
Set-Location -Path $PSScriptRoot   # carpeta agent/

Write-Host "Verificando PyInstaller con: $Python"
& $Python -c "import PyInstaller" 2>$null
if ($LASTEXITCODE -ne 0) {
    Write-Host "PyInstaller no encontrado; instalando (con --trusted-host por la red)..."
    & $Python -m pip install pyinstaller --trusted-host pypi.org --trusted-host files.pythonhosted.org
    if ($LASTEXITCODE -ne 0) {
        throw "No se pudo instalar PyInstaller (¿la red bloquea PyPI? ver README, sección Troubleshooting)."
    }
}

Write-Host "Construyendo sxml_agent.exe..."
& $Python -m PyInstaller --onefile --name sxml_agent --clean run_agent.py
if ($LASTEXITCODE -ne 0) { throw "Falló el build de PyInstaller." }

$exe = Join-Path $PSScriptRoot "dist\sxml_agent.exe"
Write-Host ""
Write-Host "Listo: $exe"
Write-Host "Siguiente: copiar agent.toml junto al .exe (o pasar --config <ruta> al instalar la tarea)."
