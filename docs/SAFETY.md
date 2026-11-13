# Sicherheit

Dieses Dokument ist Pflichtlektüre vor dem Anschluss an die Wärmepumpe. Es enthält bekannte Risiken und offene Prüfpunkte.

## 1. Bus-Zustand beim Einschalten (Messung weiterhin OFFEN)

Laut Schaltplan (`ESP32-S3-Relay-1CH-schematic.pdf`, Ausschnitt U6 SP3485EN) hängen DE und RE̅ des Transceivers am gemeinsamen
Freigabe-Netz `RS485_EN'`. Dieses Netz hat einen Pull-up nach 3V3 (R21, 4,7 kΩ).

- `DE` high = Sender aktiv. `RE̅` high = Empfänger aus.
- Der Nutzer geht davon aus, dass das Netz vor der Firmwareinitialisierung durch den Pull-up logisch `1` ist. Das ist
  mit dem Schaltplan konsistent, bedeutet beim verwendeten Transceiver aber zugleich **Sender aktiv / Empfänger aus**.
- Die Software setzt GPIO21 in `thermia_bus::setup()` auf low. Das passiert erst, nachdem die Firmware läuft. Die Phase
  davor (ROM-Bootloader, Reset) ist nicht durch diese Komponente kontrolliert.

Der Nutzer hat ausdrücklich freigegeben, die Softwareänderungen vor der Hardwaremessung vorzunehmen. Damit ist Schritt 1
aber **nicht bestanden**. Das Board darf nicht allein aufgrund dieser Annahme an die Wärmepumpe angeschlossen werden.

**Offene Messung vor dem ersten Busanschluss:** Board ohne Wärmepumpe einschalten und A/B während Boot und Reset mit
Oszilloskop oder zweitem RS485-Adapter beobachten. Vorgehen siehe `docs/BENCH_TEST.md`, Schritt 1.

Mögliche Gegenmaßnahmen, falls die Messung ein Problem zeigt. Jede davon ist eine Hardware-Änderung und braucht die
Freigabe des Nutzers:
1. R21 entfernen, damit das Netz beim Start nicht auf high gezogen wird. Dann braucht es einen definierten Pull-down.
2. Pull-down auf das Freigabe-Netz setzen, damit der Transceiver beim Start im Empfangsmodus bleibt.

## 2. Umwälzpumpe (230 V AC)

- Pumpe: 230 V AC, max. 3 A. Das Relais schaltet bis 10 A bei 250 V AC.
- Das Relais liegt auf GPIO47. Beim Start ist es **AUS** (`restore_mode: ALWAYS_OFF` und früher `on_boot`).
- Eingeschaltet wird die Pumpe nur durch Home Assistant. Ein Neustart des ESP32 schaltet sie immer aus.
- Bei Ausfall von HA bleibt die Pumpe im letzten Zustand (so vereinbart).
- Netzseitige Verdrahtung nur durch eine Elektrofachkraft: Sicherung, Schutzleiter, Berührungsschutz.
  Das Board ist kein Netzgerät. Die Isolation des Relais ist für den Betrieb ausgelegt, aber das Gehäuse muss passen.

## 3. Versorgung

- Das Board wird über den DC-5-V-Schraubklemmen-Eingang oder USB-C versorgt.
- **Pins 7 und 8 des Thermia-RJ45 (+12 V) nicht anschließen.** Dafür gibt es keinen Anschluss am Board.
- A an RJ45 Pin 1 oder 2, B an Pin 3 oder 4, GND an Pin 5 oder 6 (laut Repo-README).

## 4. Abschlusswiderstand

- Das Board hat ein 120-Ω-Abschlussmodul (R23, Jumper H1), Standard offen.
- Ob der Bus schon abgeschlossen ist, ist nicht geklärt. Der Jumper bleibt offen, bis das geprüft ist.

## 5. Emulationen und Temperaturquelle

Die Emulationen werden nicht mehr über wiederherstellbare Template-Schalter bedient, sondern direkt in `thermia_bus:` konfiguriert:

- **DCM / 0x0F ACK:** `dcm.0x0f_emulation: true` aktiviert ACK- und die dokumentierte 0x0708-Leerlaufantwort. Ohne Option bzw. mit `false` bleibt diese Emulation aus.
- **Raumthermostat / 0x0A:** `room_temperature.room_temperature_sensor` referenziert eine ESPHome-Sensor-ID, normalerweise einen `platform: homeassistant`-Sensor. Wenn `enable` fehlt, wird bei vorhandener und gültiger Sensorreferenz automatisch aktiviert. `enable: false` deaktiviert die Emulation trotz Sensor; `enable: true` ohne Sensor ist ein Konfigurationsfehler.
- Die Konfiguration setzt voraus, dass der emulierte Raumthermostat der einzige Thermostat auf Slave `0x0A` ist. Eine erkannte externe Raumantwort bleibt eine zusätzliche Schutzsperre.
- Bei Start ist die Emulation logisch aktiviert, wenn die YAML-Regel dies ergibt. Sie sendet aber erst, sobald ein gültiger aktueller HA-Wert vorliegt. Ohne frischen Wert bleibt der Status `WAITING`; nach Watchdog-Ablauf `TIMEOUT`.
- Watchdog Standard 30 min, Bereich 0–120 min. Der wiederhergestellte Wert wird nach Initialisierung der ESPHome-Number explizit an den C++-Kern übergeben.

**Registeralter:** `register_stale_after: 0` deaktiviert die automatische Invalidierung. Bei einem positiven Sekundenwert werden einzelne Registerwerte nach Ablauf dieses Alters als ungültig publiziert (Sensoren werden `NAN`, Binärsensoren unavailable, Textsensoren `UNKNOWN`). `oldest_register_age_seconds` zeigt das Alter des ältesten gespeicherten Registerwerts. `register_data_stale` wird nur bei aktiviertem Timeout gültig und meldet, sobald mindestens ein gespeicherter Registerwert veraltet ist. Die Altersdiagnose ist bewusst nicht change-only und aktualisiert sich regelmäßig.

## 6. Timing

- Die Antwortzeiten stammen aus dem Repo: 0x0A nach 5 ms Stille plus 3,8 ms, 0x0F-Quittung und 0x0708-Antwort nach 5 ms plus 5 ms.
- Der ESP32 verarbeitet Frames in der Hauptschleife. Schreiben blockiert, bis das Telegramm gesendet ist (wie im Repo).
- Ob das auf dem Board eingehalten wird, muss am Bus gemessen werden (`docs/BENCH_TEST.md`, Schritt 4; Details in `docs/TODO.md`).
