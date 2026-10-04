$ErrorActionPreference = 'Stop'
$projectRoot = 'G:\Codex TowerD'
$blenderPath = 'G:\Blender\blender.exe'
$scriptPath = Join-Path $projectRoot 'designs\transit_nexus_v3\build_transit_nexus_v3.py'

Set-Location -LiteralPath $projectRoot
if (-not (Test-Path -LiteralPath $blenderPath)) {
    throw "Blender nicht gefunden: $blenderPath"
}
if (-not (Test-Path -LiteralPath $scriptPath)) {
    throw "Blender-Skript nicht gefunden: $scriptPath"
}

& $blenderPath --background --python $scriptPath
if ($LASTEXITCODE -ne 0) {
    throw "Blender-Generierung fehlgeschlagen. Exit-Code: $LASTEXITCODE"
}
