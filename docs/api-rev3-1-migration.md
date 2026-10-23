# Marstek Open API Rev 3.1: Analyse und Migrationsplan

Grundlage: `input/MarstekDeviceOpenApi-rev3-1.pdf` (22 Seiten) verglichen mit `input/MarstekDeviceOpenApi-rev-2-0.pdf`.
Methode: Text beider PDFs extrahiert und normalisiert, Diff gelesen, die relevanten Seiten (10–11, 19–22) zusätzlich als Bild geprüft.
Stand des Codes: Controls sind optional, Client mit gemeinsamer Warteschlange (siehe README).

## 1. Ergebnis in Kürze

- **Das Protokoll ist kompatibel.** Alle Methodennamen, das Request/Response-Format, die Fehlercodes, `ES.SetMode`, `ES.GetMode` und die Discovery sind unverändert. Es gibt keinen Breaking Change im Transport.
- **Eine Sensor-Einheit hat sich geändert** (`total_pv_energy`). Für ein Venus E ist das vermutlich ohne Wirkung, weil es laut Kap. 4.1 keine PV-Komponente hat. Das muss am Gerät geprüft werden.
- **DOD, LED und Bluetooth-Lock gehören jetzt zur Komponente „SYS“** und sind bei Venus C/E und A/D erst ab **Firmware ≥ 150** verfügbar. Das Gerät im README läuft mit **Firmware 148**. Ob die Controls dort überhaupt funktionieren, ist offen und der wichtigste Punkt dieser Analyse.
- **Zwei neue gefährliche Befehle** (`Set.Ver`, `Reset.Factory`). Empfehlung: nicht in Home Assistant einbauen.
- **Neues Gerät Venus E mini** mit eigenen Grenzen und einem zusätzlichen Parameter bei Manual.

## 2. Alle Unterschiede Rev 2.0 → Rev 3.1

| # | Stelle | Rev 2.0 | Rev 3.1 | Auswirkung auf die Integration |
|---|---|---|---|---|
| D1 | `ES.GetStatus` → `total_pv_energy` | `[Wh]` | `[0.01*KWh]` (1 Zähler = 10 Wh) | `sensor.py`: Sensor „Total Solar Energy“ ist bei neuer Firmware um Faktor 10 zu klein. Übrige Energiefelder bleiben `[Wh]`. |
| D2 | `EM.GetStatus` → `input_energy`, `output_energy` | `[Wh] (*0.1)` | `[0.1 Wh]` | Nur klarere Formulierung. Der Faktor 0.1 in `sensor.py` bleibt richtig. |
| D3 | `ES.GetMode` → `input_energy`, `output_energy` | `[Wh] (*0.1)` | unverändert, uneindeutig | Wie D2 behandeln, nicht ändern. |
| D4 | Komponente „SYS“ (Kap. 3.8) | DOD, Ble_block, Led_Ctrl als eigene Kapitel 3.8–3.10 | Unterkapitel 3.8.1–3.8.3 unter SYS; bei C/E und A/D „FW>=150 available“ | Siehe Abschnitt 4 (Firmware-Gate). Methodennamen bleiben `DOD.SET`, `Ble.Adv`, `Led.Ctrl`. |
| D5 | `Set.Ver` (Kap. 3.8.4) | nicht vorhanden | `version` = 800, 1200, 1500, 2200 oder 2500 (W/VA, je nach Modell) | Ändert die Leistungsklasse des Geräts. Nicht als Entität anbieten. |
| D6 | `Reset.Factory` (Kap. 3.8.5) | nicht vorhanden | `type` 1 = Werkseinstellung, Daten löschen; 2 = Werkseinstellung, Daten behalten | Löscht Konfiguration. Nicht als Entität anbieten. |
| D7 | `manual_cfg.time_num` | „Venus C/E supports 0-9“ | A/C/D/E: 0–9, **E mini: 0–5** | Nur relevant, falls `set_manual_mode` genutzt wird (Validierung im Client). |
| D8 | `manual_cfg.manual_set` | nicht vorhanden | **nur Venus E mini:** 0 aus, 1 Laden, 2 Entladen, 3 Auto | Optionaler Parameter für `set_manual_mode`. |
| D9 | Kap. 3.5 PV | allgemein | „only for Venus A/D“ | `PV.GetStatus` wird nicht genutzt. Keine Änderung nötig. |
| D10 | Kap. 4.3 Venus E mini | nicht vorhanden | neues Gerät, SYS (DOD, Ble_block, Led_Ctrl) ohne Firmware-Einschränkung | Modell-Erkennung, siehe Schritt 3. |
| D11 | `ES.GetStatus` Request-Parameter `id` | `number or null` | `number` | Wir senden immer `{"id": 0}`. Keine Änderung. |
| D12 | Change-Log am Ende | vorhanden | entfernt | Kein Versionsdatum im Dokument. Die PDF-Metadaten nennen Typora als Ersteller und den 17.09.2026 als Erstelldatum. |

Unverändert und damit unkritisch: `Marstek.GetDevice`, `Wifi.GetStatus`, `BLE.GetStatus`, `Bat.GetStatus`, `ES.GetMode`, `ES.SetMode` (auto/ai/manual/passive/ups), `EM.GetStatus`, Fehlercodes.

Auffällig im Dokument selbst, aber ohne Folgen für uns: Beispiele schreiben `"set_result": ture` (Tippfehler, kein gültiges JSON) und „fai“ statt „fail“. Der Client prüft nur auf einen wahren `set_result` und ist davon nicht betroffen.

## 3. Offene Fragen (am Gerät zu klären)

Die Spezifikation beantwortet diese Punkte nicht. Alle lassen sich mit `src/probe.py` klären. Das Skript sendet nur Lese-Abfragen, mit optionaler Ausnahme `--check-dod`.

| Frage | Warum offen | Wie klären | Betrifft |
|---|---|---|---|
| **Q1** Liefert dein Gerät `total_pv_energy` schon in 0.01 kWh? | Das Dokument nennt keine Firmware-Version für die Änderung. | `probe.py` zeigt den Rohwert. Beim Venus E ist er vermutlich immer 0; dann ist die Frage für dich gegenstandslos. | Schritt 2 |
| **Q2** Welche Firmware meldet das Gerät? | `Marstek.GetDevice` liefert `ver`, wir lesen es bisher nirgends. Das Beispiel in der Spezifikation zeigt `ver: 111`. Ob `ver` der Firmware-Nummer aus Kap. 4 entspricht, ist eine Annahme. | `probe.py` zeigt `device` und `ver`. Der Aufruf kann bei Unicast mit „Parse error“ scheitern (siehe `config_flow.py`). | Schritt 3 |
| **Q3** Meldet `ES.GetMode` im UPS-Modus `UPS` oder `Ups`? | Die Spezifikation schreibt in der Tabelle „Ups“, in den Beispielen „UPS“. Die Select-Entität vergleicht exakt mit `UPS`. Das war schon in Rev 2.0 so. | In der App einmal UPS setzen, `probe.py` laufen lassen. | Schritt 4 |
| **Q4** Antwortet `PV.GetStatus` am Venus E? | Laut Spezifikation nur A/D. Erwartet wird `-32601`. | `probe.py` | nur Dokumentation |
| **Q5** Existieren `DOD.SET`, `Led.Ctrl`, `Ble.Adv` auf Firmware 148? | Rev 3.1 sagt „ab Firmware ≥ 150“. Rev 2.0 nannte keine Einschränkung. | `probe.py <ip> --check-dod <aktueller Wert>`. Das **schreibt** den Wert, den du in der App eingestellt hast, ändert den Zustand also nicht. `-32601` bedeutet „nicht verfügbar“. | Schritt 4 |
| **Q6** Bleiben CT-Werte in `EM.GetStatus` auch in Manual/Passive/UPS gültig? | `ES.GetMode` kennzeichnet CT-Felder nur für Auto und AI als gültig. Für `EM.GetStatus` steht das nicht dabei. | `probe.py` je einmal pro Modus (Modus in der App setzen). | Schritt 2, optional |

Hypothese, nicht belegt: Falls Q5 auf Firmware 148 `-32601` ergibt, wären DOD- und LED-Befehle dort wirkungslos. Dann sind sie nicht die Ursache von Störungen, sondern liefen bisher ins Leere und lieferten falsche Erfolgsmeldungen (diese Lücke ist mit dem letzten Umbau geschlossen: `set_result: false` und Fehlerantworten werden jetzt gemeldet).

## 4. Schrittweiser Umsetzungsplan

Jeder Schritt ist eigenständig lieferbar und testbar. Schritt 1 ist ein Gate für 2–4.

### Schritt 0: Repo aufräumen (kein Verhalten ändert sich)
- `README.md:151` und `CLAUDE.md:7` verweisen noch auf `input/MarstekDeviceOpenApi (1).pdf`. Die Datei heißt jetzt `MarstekDeviceOpenApi-rev-2-0.pdf`; die Rev 3.1 liegt daneben. Verweise auf Rev 3.1 umstellen.
- Git zeigt die alte PDF als gelöscht und beide neuen als unversioniert. Beide neuen Dateien committen.
- `docs/` (dieses Dokument) und `src/probe.py` mit einchecken. `.gitignore` enthält bereits `output/probe-*.json`.
- Test: keiner nötig.

### Schritt 1: Gerät abfragen (Gate)
- `python3 src/probe.py <ip> [port]` ausführen. Optional zusätzlich `--check-dod <aktueller Wert aus der App>`.
- Die Ausgabe nennt unter „Findings“ die Antworten zu Q1–Q6. Ergebnis hier in Abschnitt 3 als Spalte „Ergebnis“ nachtragen.
- Die Datei unter `output/` enthält maskierte Kennungen (MAC, IP, SSID). Sie ist git-ignoriert und lässt sich bei Bedarf weitergeben.
- Dauer: etwa 10 s. Das Skript wartet je 1 s zwischen den Abfragen, damit es das Gerät nicht stört.

### Schritt 2: Sensor-Korrektheit (abhängig von Q1)
- Ziel: `total_pv_energy` zeigt keinen um Faktor 10 falschen Wert.
- Empfehlung: Einheit Wh beibehalten und den Faktor 10 nur anwenden, wenn Q1/Q2 das für die Firmware bestätigen. Das vermeidet eine Einheitenänderung bestehender Statistiken.
- Alternative bei Venus C/E ohne PV: Sensor standardmäßig deaktivieren (`entity_registry_enabled_default=False`), wie es bei den CT-Phasen schon der Fall ist.
- Dateien: `sensor.py` (`MarstekSensorEntityDescription.factor` existiert bereits), ggf. `const.py`.
- Test: Sensor-Test mit Rohwert 1234 → erwartet 12340 Wh (bzw. unverändert, je nach Q1). Ist das Ergebnis aus Q1 „0 und Venus E“, reicht das Deaktivieren, der Faktor entfällt.
- Risiko gering. Fehler wären nur ein falscher Zahlenwert im Energie-Dashboard.

### Schritt 3: Modell- und Firmware-Erkennung (abhängig von Q2)
- Ziel: Wissen, welches Modell und welche Firmware das Gerät hat, ohne dass ein Fehlschlag den Start verhindert.
- `config_flow.py` liest `device` und `ble_mac` bereits aus `Marstek.GetDevice`. Zusätzlich `ver` im Config-Entry speichern.
- `coordinator.py`: `DeviceInfo` um `sw_version` ergänzen.
- Fehlt `ver` (Unicast-Parse-Error), bleibt der Wert leer und es gilt „unbekannt“. Der Start darf daran nie scheitern (aktuelles Verhalten bleibt).
- Hilfsfunktion `supports_sys(entry) -> bool | None`: `True`/`False` bei bekannter Firmware, `None` bei unbekannter.
- Bestehende Config-Entries haben kein `ver`. Entweder beim Setup einmalig nachholen (ein zusätzlicher Request, gleiche Warteschlange) oder bis zur Neukonfiguration als unbekannt behandeln.
- Test: Config-Flow mit und ohne `ver`; Entry ohne `ver` startet weiterhin.

### Schritt 4: Controls robust machen (abhängig von Q3 und Q5)
- DOD, LED und BLE hängen an SYS. Wenn das Gerät `-32601` meldet, soll die UI das verständlich sagen („vom Gerät/der Firmware nicht unterstützt“) statt „command failed“.
- `entity.py` (`MarstekControlEntity._async_send`): `MarstekError` mit `code == -32601` in eine eigene Meldung übersetzen.
- Optionen: Beschreibung der Schalter um „benötigt Firmware ≥ 150“ ergänzen (`translations/en.json`). Ist `supports_sys()` aus Schritt 3 `False`, den Hinweis im Options-Dialog hervorheben. Kein hartes Sperren, solange `ver` nur eine Annahme ist.
- `select.py`: Modus-Vergleich unabhängig von Groß-/Kleinschreibung (`Ups` vs. `UPS`), falls Q3 das bestätigt. Sonst zeigt die Entität im UPS-Modus „unbekannt“.
- Test: Fake-Client wirft `MarstekError(code=-32601)` → `HomeAssistantError` mit der neuen Meldung; Modus `Ups` wird als `UPS` erkannt.

### Schritt 5: Client erweitern, ohne neue Entitäten
- `set_manual_mode`: optionaler Parameter `manual_set` (nur E mini) und Prüfung von `time_num` (0–9, bei E mini 0–5). Der Client lehnt ungültige Werte vor dem Senden ab (wie bei `set_mode` für Manual/Passive).
- `Set.Ver` und `Reset.Factory`: **bewusst nicht** in `custom_components/` aufnehmen. Beide verändern das Gerät dauerhaft (Leistungsklasse bzw. Konfiguration) und gehören nicht in eine Oberfläche, die versehentlich bedient werden kann. Falls gewünscht: nur in einem eigenen Skript unter `src/` mit ausdrücklicher Bestätigung.
- `Ble.Adv` bleibt wie bisher ohne Entität.
- Test: Client-Tests gegen den simulierten UDP-Server (wie beim letzten Umbau).

### Schritt 6: Tests ins Repo, Doku, Version
- Die bisherigen Tests liegen nur im Job-Verzeichnis. Nach `tests/` übernehmen (Client-Test und HA-Integrationstest, inklusive `pytest.ini` mit `asyncio_mode = auto`).
- `README.md`: Abschnitt „Known Limitations“ um Firmware ≥ 150 für DOD/LED und die `total_pv_energy`-Einheit ergänzen.
- `manifest.json`: Version anheben (derzeit 1.0.0).

### Backlog (kein Teil dieser Migration)
- Services für Manual und Passive (README verspricht `marstek_venus.set_manual_mode`, „not yet implemented“).
- Vermerk zum Known Issue „Polling führt zu Crashes“: Rev 3.1 enthält dazu keine Hinweise. Dafür wird das Home-Assistant-Log mit der genauen Fehlermeldung gebraucht.

## 5. Risiken auf einen Blick

| Risiko | Wahrscheinlichkeit | Wirkung | Gegenmaßnahme |
|---|---|---|---|
| `total_pv_energy` falsch skaliert | mittel bei Geräten mit PV, bei Venus E vermutlich irrelevant | falscher Zahlenwert | Schritt 2 mit Q1 |
| Controls wirkungslos auf Firmware 148 | offen (Q5) | falsche Erwartung des Nutzers | klare Fehlermeldung, Hinweis in den Optionen (Schritt 4) |
| `ver` ≠ Firmware-Nummer | offen (Q2) | falsche Sperre/Freigabe | nur Hinweis, kein hartes Sperren |
| `Ups`/`UPS` | offen (Q3) | Modus zeigt „unbekannt“ | Schritt 4 |
| Versehentliches `Reset.Factory`/`Set.Ver` | nur falls eingebaut | Datenverlust, falsche Leistungsklasse | nicht einbauen (Schritt 5) |
