# Transit Nexus · Kartenbauplan V1

Dieser Ordner ist ein unabhängiger Designentwurf. Er wird von der aktuell spielbaren CreepGrid-Version nicht geladen und verändert keine bestehenden Karten, Creeps, UI- oder Gameplay-Dateien.

## Dateien

- `transit_nexus.json` – maschinenlesbarer 30×18-Bauplan mit Routen, Höhenebenen, Bauflächen, Sperrzonen und Bridge-Regeln.
- `transit_nexus_preview.png` – programmatisch aus der JSON-Datei gerenderte 1200×720-Vorschau mit 40×40-Pixel-Zellen.
- `generate_transit_nexus.py` – reproduzierbarer Generator für JSON und PNG.
- `validate_transit_nexus.py` – ausführbare Validierung ohne Spielintegration.

## Wegführung

`route_alpha` bleibt auf der Bodenebene und führt vom gemeinsamen Spawn zunächst nach Norden, über eine lange Südtrasse und anschließend über die westliche Rückführung zur Basis. `route_beta` nutzt zunächst die südliche Paralleltrasse, steigt im Zentrum auf eine Überführung über Alpha, verläuft auf der erhöhten Ebene nach Norden und senkt sich erst vor der Basis wieder ab.

Die fünf zentralen Überführungszellen haben dieselbe XY-Projektion wie Alpha, aber unterschiedliche Höhenebenen. Die JSON-Regel `optical_crossing_only_no_route_switch` macht ausdrücklich klar, dass dort kein Routenwechsel erlaubt ist. Für Blender soll die Navigation getrennte Ebenen beziehungsweise getrennte Nav-Mesh-Flächen erhalten.

## PowerShell-Ausführung

```powershell
Set-Location 'G:\Codex TowerD'
python designs\transit_nexus_v1\generate_transit_nexus.py
python designs\transit_nexus_v1\validate_transit_nexus.py
```

Der Generator liest die gerade erzeugte JSON-Datei vor dem Rendern erneut ein. Die Validierung vergleicht zusätzlich die PNG-Abmessungen und einen Render-Manifest mit den tatsächlich aus der JSON berechneten Zellmengen.
