# CreepGrid: Tower Defense

**CreepGrid** ist ein direkt startbares Tower-Defense-Spiel im Stil klassischer Grid-/Creep-TD-Spiele: dunkles Arena-Raster, klar markierte Laufwege, viele bebaubare Zellen und schnelle Wellen. Es kann allein gespielt werden; der Host-Modus bleibt weiterhin LAN-/Hamachi-fähig.

## Sofortstart

Wie beim Strategic-Command-Projekt kann das Spiel als editable Python-Projekt installiert und dann über den Pygame-Launcher gestartet werden:

```powershell
cd "G:\Codex TowerD"
python -m pip install -e ".[gui]"
python run_pygame.py
```

Alternativ gibt es weiterhin den einfachen PowerShell-Starter:

```powershell
cd "G:\Codex TowerD"
.\start.ps1
```

`python run_pygame.py` und `python main.py` öffnen zuerst die CreepGrid-Kontrollzentrale von **Barbarossa & Evil Enterprises™**. Dort wählst du Singleplayer oder Koop-LAN, Spielmodus, Kartenmodus, Karte und Schwierigkeit. Die Modi heißen **Letzte Bastion**, **Megalomanie** und **Akkordarbeit**; ihre technischen IDs bleiben für Spielstände und Netzwerk kompatibel. Für LAN/Hamachi kann der Host einen festen Port wählen; Mitspieler verbinden sich anschließend mit der Host-IP:

```powershell
python main.py --host --port 5000
python main.py --connect 192.168.1.20 --port 5000
```

Alternativ kann ein Mitspieler im Hauptmenü direkt **Multiplayer beitreten** anklicken und die Host-IP oder `IP:Port` eingeben. Ohne Port wird `5000` verwendet. Der Host startet dafür im Menü **Koop-LAN hosten**; beide Rechner müssen dieselbe Spielversion verwenden.

Die gewählte Firewall muss eingehende TCP-Verbindungen für den verwendeten Port erlauben. Alle Spieler verwenden dieselbe Version des Projekts.

## Steuerung

| Eingabe | Funktion |
| --- | --- |
| Linksklick auf freie Grid-Zelle | Aktuellen Turm bauen |
| Linksklick auf Turm | Turm auswählen |
| `1`-`5` | MG-Turm, Artillerie, Laser, Tesla oder Support auswählen |
| `U` | Ausgewählten Turm aufwerten |
| `X` | Ausgewählten Turm verkaufen |
| `Q` | Zielpriorität wechseln: Erste, Stärkste, Nächste, Letzte |
| `J` / `K` | Turmspezialisierung A/B (nach Waffenforschung) |
| `F` | Ausgewählte Forschung kaufen; vorher `T` öffnen und einen Eintrag anklicken |
| `T` | Forschungsbildschirm öffnen/schließen |
| `B` | In Megalomanie 10 % des aktuellen Guthabens investieren |
| `O` | Optionen öffnen |
| `H` | Handbuch öffnen (Hauptmenü) |
| `P` | Pause/Fortsetzen |
| `Y` | Mehrere Türme als atomaren Bauplan vormerken, bestätigen oder verwerfen |
| `6` / `7` / `8` | Singleplayer-Spieltempo 1x / 2x / 3x; LAN bleibt auf 1x |
| Mausklick | „Start erste Welle“ in Megalomanie/Akkordarbeit startet die Partie nach der Vorbereitungszeit |
| Mausklick | „Zum Hauptmenü“ beendet die aktuelle Host-Partie und öffnet die Auswahl erneut |
| `R` | Turmreichweite ein- oder ausblenden |
| `Leertaste` | Nächste Welle starten (Letzte Bastion; Megalomanie/Akkordarbeit automatisch) |
| `M` | Karte wechseln, solange noch keine Welle gestartet wurde; nach Niederlage Neustart |
| `Esc` | Fenster schließen |

Mr. Evil kommentiert wichtige Ereignisse lokal und ereignisgesteuert. Unter `O → Gameplay` lassen sich Häufigkeit (`Aus`, `Selten`, `Normal`, `Häufig`), Animationen und Kommentartextgröße einstellen. Kritische Warnungen wie Durchbrüche und Game Over bleiben unabhängig von der Häufigkeit sichtbar. Die Kommentare werden nicht an LAN-Clients übertragen und verändern weder Regeln noch Wellenzufall.

Im Hauptmenü wechseln `A`/`D` oder die Pfeiltasten die Karte, `Tab` schaltet Singleplayer/Koop-LAN um, `1`-`3` wählen den Schwierigkeitsgrad und `Enter` startet die Partie.

## Spielmechaniken

- **Creep-Arena:** Die erste Karte ist ein offenes Raster mit vielen Bauzellen und drei verzweigten Laufwegen.
- **Acht Karten:** Neben Creep Arena, Versunkenem Pass und Glut-Schmiede gibt es Frostklamm, Finsterwald, Sandsturm-Basar und Schattengruft mit festen Wegen sowie die separate Maze-Karte Zitadellen-Labyrinth.
- **Mehrspielerfähig:** Der Host simuliert die Partie autoritativ; Clients senden nur Eingaben und erhalten Zustands-Schnappschüsse.
- **Fünf Grundtypen:** MG-Turm, Artillerie, Laser, Tesla und Support unterscheiden sich in Reichweite, Feuerrate, Flächen-/Ketteneffekten und Auren. Jeder Turm kann dreimal aufgewertet und nach dem Spezialistenkern alternativ spezialisiert werden.
- **Dynamische Wege:** Türme sind Hindernisse. Die Host-Simulation prüft jede Bauaktion mit gecachtem Grid-BFS, zeigt die Vorschau und lehnt eine vollständige Blockade ab. Laufende Bodengegner werden nach einem Bau-/Verkaufsereignis auf einen neuen Weg gesetzt; Flieger bleiben unabhängig davon.
- **Zwei Kartenfamilien:** „Vordefinierte Wege“ behalten die klassischen festen Laufwege und begrenzten Bauplätze. „Turm-Maze“ nutzt ein freies Raster; dort legen ausschließlich die gesetzten Türme den BFS-Laufweg fest.
- **Kartensprache:** „Vorgegebene Wege“ bedeutet, dass die Karte den Weg vorgibt. „Freies Bauen“ bedeutet, dass die Türme den Weg bilden.
- **Forschung:** Drei Äste (Waffen, Technologie, Wirtschaft) werden über Wellen freigeschaltet und mit Coins gekauft. Forschungspunkte oder eine zweite Währung gibt es nicht.
- **Gegnerrollen:** Standard, schnell, gepanzert, fliegend, Heiler, Schildgenerator, Belagerung und Boss haben jeweils eigene mechanische Effekte. Jede fünfte Big-Combo-Welle ist eine regelbasierte Spezialkombination.
- **Akkordarbeit:** Nach dem Button „Start erste Welle“ beginnt die erste Welle; danach starten die weiteren Wellen automatisch.
- **Megalomanie:** Alle 30 Sekunden wird das dauerhafte Rundeneinkommen als Coin-Tick ausgezahlt, unabhängig vom Wellenabschluss. Der Investitionsregler nimmt einen Prozentsatz des aktuellen Guthabens sofort aus dem Konto und erhöht dauerhaft das Tick-Einkommen.
- **Vorbereitungszeit:** Die erste Welle in Megalomanie und Akkordarbeit wird bewusst per Button gestartet. Danach liegen zwischen den automatischen Wellen acht Sekunden Aufbauzeit.
- **Forschungszweige:** Prismalinse und Fokussierkern sind ein exklusives Laser-Paar; nur eine der beiden Alternativen kann gekauft werden.
- **Niederlage und Neustart:** Nach dem Fall der Burg stehen Zeit und Einkommen still. `M` setzt den aktuellen Lauf vollständig zurück; „Zum Hauptmenü“ beendet die Host-Partie ohne alten Zustand.
- **Hover-Hilfe:** Zwei Sekunden Mauszeiger über einem Turm-Button zeigen Kosten, Reichweite und eine kurze taktische Erklärung.
- **Mr. Evil:** Das Corporate-Commentary-System wählt aus über 100 zentral gepflegten Varianten, vermeidet unmittelbare Wiederholungen, priorisiert kritische Ereignisse und merkt sich relevante Entscheidungen wie All-in-Investitionen, Turmverkäufe und Niederlagen.
- **Gemeinsame Ressourcen:** Coins und Basisleben gehören dem Team. Im Koop werden Startguthaben und laufendes Einkommen gleichmäßig nach aktiver Spielerzahl skaliert: ein Spieler erhält 100 %, zwei Spieler jeweils 50 %. Bau, Upgrade, Forschung, Investition und Verkauf werden vom Host geprüft.
- **Wellen:** Wellen skalieren in Größe, Lebenspunkten und Spezialgegnern. Zwischen Wellen kann umgebaut werden.

## Architektur

```text
main.py                  Programmstart und Argumente
run_pygame.py            Pygame-Launcher wie im Strategic-Command-Projekt
pyproject.toml           Editable Installation mit optionaler GUI-Abhängigkeit
start.ps1                PowerShell-Sofortstart mit virtueller Umgebung
game/
  constants.py            Balancing, Farben, Fenster- und Rasterwerte
  maps.py                 Kartendefinitionen und Bauzellen
  entities.py             Gegner, Türme, Effekte und Wellenplan
  pathfinding.py          Gecachtes Grid-BFS und Re-Routing aktiver Gegner
  research.py             Forschungsbaum und Freischaltstatus
  ui_data.py              Modus-, Karten- und Mr.-Evil-Texte
  evil_commentary.py      Ereignisgesteuerte Mr.-Evil-Dialoge, Gedächtnis und Auswahlregeln
  config.py               Robuste lokale JSON-Konfiguration
  state.py                Autoritative Spielsimulation und Aktionsprüfung
  network.py              Thread-basierter TCP-Host/Client, JSON-Zeilenprotokoll
  app.py                  Pygame-Eingabe, Darstellung und Client-Schleife

## Tests

Die lokalen Verhaltensprüfungen laufen ohne externe Dienste:

```powershell
python tests_smoke.py
python tests_gameplay_expansion.py
python tests_ui_smoke.py
python tests_evil_commentary.py
python -m compileall -q game main.py run_pygame.py
```

`tests_smoke.py` deckt den bestehenden Regel-/TCP-Vertrag ab, `tests_gameplay_expansion.py` prüft die Spielmechaniken und die neue Megalomanie-Wirtschaft, und `tests_ui_smoke.py` rendert Menü, Optionen, Handbuch und Spieloberfläche headless mit SDL dummy. Einstellungen werden standardmäßig in `%USERPROFILE%\.creepgrid_config.json` gespeichert; fehlende oder defekte Dateien werden durch Defaults ersetzt.
```
