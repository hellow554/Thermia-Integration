# TODO / offene Prüfungen

## Vor dem ersten Anschluss an die Wärmepumpe

- [ ] **GPIO21 / RS485_EN Boot-Messung:** Board ohne Thermia-Bus einschalten und Reset wiederholen; mit Oszilloskop oder zweitem RS485-Adapter prüfen, ob A/B vor der Firmwareinitialisierung aktiv getrieben werden. Pull-up auf logische 1 wird angenommen; beim SP3485 bedeutet DE high Sender aktiv. Die Softwarefreigabe für Änderungen ersetzt diese Messung nicht.
- [ ] Ergebnis und Messaufbau in `docs/SAFETY.md` dokumentieren.
- [ ] Bei aktivem Sender während Boot Hardware-Gegenmaßnahme (Pull-down / R21) mit Nutzer abstimmen. Keine automatische Hardwareänderung.

## Firmware / ESPHome

- [ ] Expliziten `dry_run`-Modus ergänzen: Protokollentscheidungen und Scheduler ausführen, aber DE nicht aktivieren und keine Bytes auf UART senden.
- [ ] ESPHome 2026.10.2 installieren und `esphome compile config/thermia-relay.yaml` erfolgreich durchlaufen lassen.
- [ ] Prüfen, dass `room_temperature.enable` ohne Sensor automatisch deaktiviert ist, mit Sensor automatisch aktiviert wird, `false` überschreibt und `true` ohne Sensor einen Validierungsfehler liefert.
- [ ] Prüfen, dass der HA-Sensorwert beim Start und bei Updates in den Raumemulator übernommen wird; `WAITING` bis zum ersten gültigen Wert.
- [ ] Watchdog mit einem über längere Zeit unveränderten HA-Sensorwert testen: HA-State-Callbacks kommen bei Zustandsänderungen; prüfen, ob die Quellintegration ausreichend häufig aktualisiert und ob bei Bedarf ein anderer Watchdog-Wert (einschließlich `0` = deaktiviert) sinnvoll ist.
- [ ] Prüfen, dass der nach Neustart wiederhergestellte Watchdog-Wert nach spätem Boot-Hook im C++-Kern ankommt.
- [ ] Prüfen, dass Change-only-Publishing keine wiederholten identischen API-Updates erzeugt und NAN/UNKNOWN-Übergänge genau einmal publiziert.
- [ ] Bei `register_stale_after > 0` prüfen, dass Einzelwerte nach Ablauf invalidiert und `register_data_stale` gesetzt wird; bei `0` muss der Binärsensor unavailable sein.
- [ ] Prüfen, dass `tx_dropped` bei einem Scheduler-Konflikt steigt und in Home Assistant sichtbar wird.

## Bus-Timing / Kommunikation

- [ ] UART-Empfangsverzögerung (`rx_full_threshold`, `rx_timeout`) messen: Zeit zwischen letztem RX-Bit und dem Aufruf der Parser-/Schedulerlogik bestimmen.
- [ ] 0x0A-Antwort: Zeit zwischen Ende der Reglerabfrage und erstem TX-Bit über mindestens 50 Polls messen; Sollwert aus `docs/SAFETY.md` / Repo-Quelle gegenprüfen.
- [ ] 0x0F FC10-ACK und FC03-0x0708-Antwort auf Timing und Antwortbytes prüfen.
- [ ] Scheduler-Kollisionen reproduzieren; Diagnose `tx_dropped` beobachten und Ursachen protokollieren.
- [ ] Registeralter mit realen Pollzyklen vergleichen. `register_stale_after` vorerst bei `0` lassen, bis die erwarteten Aktualisierungsintervalle bekannt sind; danach passenden Wert festlegen. `oldest_register_age_seconds` und `register_data_stale` gemeinsam beobachten.
- [ ] Peer-Erkennung / Own-Echo-Verhalten mit eigenem und zweitem Teilnehmer gezielt testen.

## Funktionsprüfung

- [ ] Sollwertanforderung wird maximal fünfmal mitgeführt, danach verworfen; Bestätigung löscht die Anforderung früher.
- [ ] 0x0F ACK nur bei `dcm.0x0f_emulation: true`.
- [ ] Raumemulation nur bei gültiger Sensorreferenz und effektiver Aktivierung; nach Watchdog-Timeout keine Raumantwort. `room_temperature.enable` muss optional bleiben: ohne Sensorreferenz AUS, mit gültiger Referenz EIN, `false` überschreibt, `true` ohne Referenz ist ein Konfigurationsfehler.
- [ ] Pumpe bleibt nach jedem Neustart AUS (GPIO47); keine Änderung an diesem Verhalten.


## Home Assistant wizard / onboarding

- [ ] Verify the linked Home Assistant sensor receives the wizard-selected `entity_id` after initial pairing and after ESPHome reboot.
- [ ] Verify room emulation remains waiting (no response) until the wizard selection reconnects and a fresh valid temperature arrives.
- [ ] Verify setup wizard filtering presents only temperature sensors in Home Assistant 2026.11.
