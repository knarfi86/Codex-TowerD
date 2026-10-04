# Transit Nexus V3 · Insolvenzspirale

Dieser Ordner enthält die gemeinsame Datenbasis für die spielbare CreepGrid-Karte und den lokalen Blender-Workflow.

## Ablauf

```powershell
Set-Location 'G:\Codex TowerD'
python designs\transit_nexus_v3\generate_transit_nexus_v3.py
python designs\transit_nexus_v3\validate_transit_nexus_v3.py
.\designs\transit_nexus_v3\run_transit_nexus_v3.ps1
```

Das Blender-Skript liest ausschließlich `transit_nexus_v3.json`. Es erzeugt daraus editierbare Boden-, Routen-, Begrenzungs-, Maschinen-, Plattform-, Licht- und Kameraobjekte. Die Gameplay-Kamera ist orthografisch und rendert 1800×1080 Pixel; die Showcase-Kamera ist leicht schräg. `transit_nexus_v3_layout.png` dient als zusätzliche Draufsicht zur Qualitätskontrolle.

## Kartengeometrie

Die Lane besitzt genau einen Spawn am oberen Rand `(15,1)` und führt über 120 eindeutige Rasterzellen zur zentralen Basis `(14,9)`. Der Weg nutzt elf markierte 90-Grad-Richtungswechsel und mehrere engere innere Windungen. Zwischen den Abschnitten liegen freie Bauflächen oder gesperrte technische Puffer; seitlich benachbarte Nicht-Folgefelder werden vom Validator abgelehnt.

Die Hintergrundgrafiken sind rein visuell. CreepGrid liest die Route aus derselben JSON-Datei und verwendet Fixed-Path-Regeln. Türme dürfen die Lane nicht umleiten oder blockieren.
