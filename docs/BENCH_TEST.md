# Prüfstand-Test

Die Softwareänderungen wurden auf Nutzerwunsch vor der Hardwaremessung von Schritt 1 vorbereitet. Die Reihenfolge gilt
weiterhin für die elektrische und funktionale Inbetriebnahme; der erste Anschluss an den Thermia-Bus bleibt bis zum
Abschluss der offenen Sicherheitsprüfung gesperrt.

## Schritt 1: Bus-Zustand beim Einschalten (ohne Wärmepumpe, weiterhin OFFEN)

Ziel: Klären, ob der Transceiver vor der Firmwareinitialisierung sendet (siehe `docs/SAFETY.md`, Abschnitt 1).

1. Board ohne Verbindung zur Wärmepumpe betreiben. A/B nur an ein Oszilloskop oder einen zweiten USB-RS485-Adapter (Empfangsmodus) legen.
2. Board einschalten, Messung über 10 s aufzeichnen. Danach einen Reset auslösen und wiederholen.
3. Ergebnis: Dauern Signale auf A/B an, bevor die Firmware läuft?
   - **Ja:** Stopp. Gegenmaßnahmen aus `docs/SAFETY.md` klären, bevor weiter.
   - **Nein:** Weiter.
4. Ergebnis und Messaufbau in `docs/SAFETY.md` eintragen.

## Schritt 2: Passives Mitlesen

Firmware für diesen Schritt mit beiden Emulationen deaktiviert konfigurieren:

```yaml
thermia_bus:
  dcm:
    "0x0f_emulation": false
  room_temperature:
    enable: false
```

1. Board erst nach bestandenem Schritt 1 an den Bus anschließen (A an Pin 1, B an Pin 3). Pins 7/8 frei lassen.
2. 30 Minuten mitlesen. Prüfen:
   - `Gültige Telegramme` steigt, `Verworfene Bytes` steigt nur wenig.
   - Vorlauftemperatur, Außentemperatur und Verdichterfrequenz sind plausibel und stimmen mit dem Display überein.
   - `oldest_register_age_seconds` steigt plausibel und wird bei erneuter Registerabfrage zurückgesetzt, sofern alle aktuell gespeicherten Registerwerte wieder gelesen wurden.
3. Abbruch, wenn der Regler Fehler anzeigt oder die Werte nicht zum Display passen.

## Schritt 3: Raumsensor-Emulation ohne Sendefreigabe am Bus (Dry-Run, noch nicht verfügbar)

Ein Dry-Run-Modus ist in dieser Firmwareversion noch nicht implementiert. Die normale Raumthermostat-Konfiguration
aktiviert auch den realen TX-Pfad. Dieser Schritt kann deshalb derzeit nicht ausgeführt werden. Die Emulation nicht
als vermeintlichen Dry-Run an einen laufenden Thermia-Bus anschließen. Die Implementierung eines expliziten
`dry_run`-Schalters ist in `docs/TODO.md` vorgesehen.

## Schritt 4: Timing messen

1. Erst nach implementiertem und bestandenem Dry-Run sowie bestandenem Schritt 1 `room_temperature.room_temperature_sensor`
   auf einen gültigen HA-Temperatursensor setzen. `enable` kann entfallen; die Sensorreferenz aktiviert die Emulation
   automatisch. Alternativ `enable: true` setzen.
2. Mit dem Oszilloskop: Abstand zwischen dem Ende der Abfrage des Reglers (FC17 an 0x0A) und dem Beginn der Antwort messen.
   Soll: ca. 8,8 ms (5 ms Stille plus 3,8 ms).
3. Wiederholen über 50 Abfragen. Prüfen, ob der Regler die Antwort akzeptiert: Der Sollwert auf dem Display springt
   nicht zurück, und die Raumtemperatur wird angezeigt.
4. Sensorwert entziehen oder ungültig machen und prüfen, dass keine Raumantwort mehr erfolgt. Watchdog-Ablauf testen.

## Schritt 5: 0x0F ACK

1. `dcm.0x0f_emulation: true` konfigurieren und Firmware neu kompilieren/flashen.
2. Regler schreibt Einstellungsblöcke. Prüfen, dass die Quittung (FC10, 8 Byte) kommt und der Regler keine Wiederholungen mehr sendet.
3. Die 0x0708-Leerlaufantwort prüfen, sofern der Regler die entsprechende FC03-Abfrage sendet.
4. Prüfen, dass die Emulation bei erkanntem zweitem Teilnehmer `BLOCKED_BY_EXTERNAL_RESPONDER` meldet.

## Schritt 6: Umwälzpumpe

1. Pumpe nur an Relais anschließen, wenn die Elektrik von einer Elektrofachkraft geprüft ist.
2. Nach jedem Neustart des ESP32: Pumpe AUS. Dann über HA einschalten, prüfen, dann ausschalten.
3. Den Schalter bei Verbindungsverlust zu HA testen: Pumpe bleibt im letzten Zustand.

## Vor dem ersten Hardwaretest

Die offenen Timing- und Firmwareaufgaben sind in `docs/TODO.md` gesammelt. Insbesondere muss die ESPHome-Kompilierung
mit 2026.10.1 erfolgreich sein; die reine Host-Test-Suite ersetzt keinen Firmware-Build.
