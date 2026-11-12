# Sicherheit

Dieses Dokument ist Pflichtlektüre vor dem Anschluss an die Wärmepumpe. Es enthält sowohl bekannte Risiken als auch offene Prüfpunkte.

## 1. Bus-Zustand beim Einschalten (OFFEN, vor dem ersten Anschluss prüfen)

Laut Schaltplan (`ESP32-S3-Relay-1CH-schematic.pdf`, Ausschnitt U6 SP3485EN) hängen DE und RE̅ des Transceivers am gemeinsamen
Freigabe-Netz `RS485_EN'`. Dieses Netz hat einen Pull-up nach 3V3 (R21, 4,7 kΩ).

- `DE` high = Sender aktiv. `RE̅` high = Empfänger aus.
- Ohne Ansteuerung durch den ESP32 liegt das Netz über R21 auf high. Der Transceiver würde dann **senden**, bis der
  ESP32 GPIO21 aktiv auf low setzt.
- In der Software setzt `thermia_bus::setup()` GPIO21 auf low. Das passiert erst, nachdem die Firmware läuft. Die Phase
  davor (ROM-Bootloader, Reset) ist nicht kontrolliert.

**Prüfung vor dem Anschluss an den Bus (siehe docs/BENCH_TEST.md, Schritt 1):** Messen, ob die Busleitungen A/B
während des Einschaltens und Neustarts des ESP32 bei leerem Flash (oder mit einer Test-Firmware, die nur GPIO21 auf low setzt) bestimmt werden. Ergebnis hier eintragen.

Mögliche Gegenmaßnahmen, falls die Messung ein Problem zeigt. Jede davon ist eine Hardware-Änderung und braucht deine
Freigabe:
1. R21 entfernen, damit das Netz beim Start nicht auf high gezogen wird. Dann braucht es einen definierten Pull-down.
2. Pull-down auf das Freigabe-Netz setzen, damit der Transceiver beim Start im Empfangsmodus bleibt.

## 2. Umwälzpumpe (230 V AC)

- Pumpe: 230 V AC, max. 3 A. Das Relais schaltet bis 10 A bei 250 V AC.
- Das Relais liegt auf GPIO47. Beim Start ist es **AUS** (`restore_mode: ALWAYS_OFF` und `on_boot`).
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

## 5. Emulationen

- **Raumsensor-Emulation (0x0A):** Standard AUS nach jedem Neustart. Wird nur eingeschaltet, wenn ein gültiger Raumtemperaturwert vorliegt.
- **Watchdog:** Standard 30 min. Nach einem Neustart sendet der ESP **keine** Raumtemperatur, bis HA einen neuen Wert schickt. Das ist eine bewusste Abweichung vom Repo, die docs/DECISIONS.md begründet.
- **0x0F ACK:** Standard AN, wie im Repo. Sie sendet, sobald der Regler auf 0x0F schreibt.
- Beide Emulationen blockieren sich, wenn ein zweiter Teilnehmer auf dem Bus antwortet.

## 6. Timing

- Die Antwortzeiten stammen aus dem Repo: 0x0A nach 5 ms Stille plus 3,8 ms, 0x0F-Quittung und 0x0708-Antwort nach 5 ms plus 5 ms.
- Der ESP32 verarbeitet Frames in der Hauptschleife. Schreiben blockiert, bis das Telegramm gesendet ist (wie im Repo).
- Ob das auf dem Board eingehalten wird, muss am Bus gemessen werden (docs/BENCH_TEST.md, Schritt 4).
