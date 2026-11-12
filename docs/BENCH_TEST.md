# Prüfstand-Test

Reihenfolge einhalten. Jeder Schritt hat ein Abbruchkriterium. Ohne Bestehen des vorherigen Schritts nicht weitermachen.

## Schritt 1: Bus-Zustand beim Einschalten (ohne Wärmepumpe)

Ziel: Klären, ob der Transceiver beim Start sendet (siehe docs/SAFETY.md, Abschnitt 1).

1. Board ohne Verbindung zur Wärmepumpe betreiben. A/B nur an ein Oszilloskop oder einen zweiten USB-RS485-Adapter (Empfangsmodus) legen.
2. Board einschalten, Messung über 10 s aufzeichnen. Danach einen Reset auslösen und wiederholen.
3. Ergebnis: Dauern Signale auf A/B an, bevor die Firmware läuft?
   - **Ja:** Stopp. Gegenmaßnahmen aus SAFETY.md klären, bevor weiter.
   - **Nein:** Weiter.

## Schritt 2: Passives Mitlesen

1. Firmware ohne Emulation flashen (alle Emulationsschalter AUS, 0x0F ACK kann AN bleiben, sendet nur bei Schreibvorgängen des Reglers).
2. Board an den Bus anschließen (A an Pin 1, B an Pin 3). Pins 7/8 frei lassen.
3. 30 Minuten mitlesen. Prüfen:
   - `Gültige Telegramme` steigt, `Verworfene Bytes` steigt nur wenig.
   - Vorlauftemperatur, Außentemperatur und Verdichterfrequenz sind plausibel und stimmen mit dem Display überein.
4. Abbruch, wenn der Regler Fehler anzeigt oder die Werte nicht zum Display passen.

## Schritt 3: Raumsensor-Emulation ohne Sendefreigabe am Bus (Dry-Run)

Die Protokoll-Logik läuft, aber `write_array` bleibt aus. Prüfen, ob die Entscheidungen stimmen. Hierfür im Code einen
Testschalter setzen (muss noch gebaut werden, siehe PLAN, Phase 4).

## Schritt 4: Timing messen

1. Raumsensor-Emulation ein, Raumtemperatur über HA setzen.
2. Mit dem Oszilloskop: Abstand zwischen dem Ende der Abfrage des Reglers (FC17 an 0x0A) und dem Beginn der Antwort messen.
   Soll: ca. 8,8 ms (5 ms Stille plus 3,8 ms).
3. Wiederholen über 50 Abfragen. Prüfen, ob der Regler die Antwort akzeptiert: Der Sollwert auf dem Display springt
   nicht zurück, und die Raumtemperatur wird angezeigt.

## Schritt 5: 0x0F ACK

1. Schalter `0x0F ACK-Emulation` AN.
2. Regler schreibt Einstellungsblöcke. Prüfen, dass die Quittung (FC10, 8 Byte) kommt und der Regler keine Wiederholungen mehr sendet.
3. Prüfen, dass der Schalter AUS geht, sobald ein zweiter Teilnehmer antwortet (`BLOCKED_BY_EXTERNAL_RESPONDER`).

## Schritt 6: Umwälzpumpe

1. Pumpe nur an Relais anschließen, wenn die Elektrik von einer Elektrofachkraft geprüft ist.
2. Nach jedem Neustart des ESP32: Pumpe AUS. Dann über HA einschalten, prüfen, dann ausschalten.
3. Den Schalter bei Verbindungsverlust zu HA testen: Pumpe bleibt im letzten Zustand.
