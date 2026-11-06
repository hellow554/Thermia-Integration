# Übergabe: Thermia iTec Eco Integration

Dieses Dokument fasst den Stand des Projekts zusammen, damit andere Agenten oder Entwickler direkt weitermachen können.
Es ist eine verdichtete Übergabe, kein Wortprotokoll der Konversation.

## Ziel

Lokale Home-Assistant-Integration (HACS) für eine **Thermia iTec Eco 5 kW** Wärmepumpe über den internen RS485-Bus.
Ohne Cloud. Mitlesen, Emulation von Raumsensor (0x0A) und Online/DCM-ACK (0x0F), Raumthermostat und Warmwasser-Nachheizung.

## Hardware und Umgebung

- Wärmepumpe: Thermia iTec Eco 5 kW, Display-Firmware 2.4.1A
- Adapter: DSD TECH SH-U14, USB-ID `0403:6001` (FTDI FT232R). Der Chip schaltet die Senderichtung selbst (TXDEN). Ein normaler UART-Schreibvorgang sendet. Der Nutzer hat das getestet.
- Serielle Parameter: 9600 Baud, 8E1
- Home Assistant OS, Zugriff über VS Code und SSH

## Ausgangslage und Quellen

- **Maßgebliche Quelle für Adressen, Skalierung, Zeiten und Abläufe: `ryckema/Thermia_itec`**, Ordner `Write (Beta)/iTec Eco`
  (Raumsensor-Profil, 0f_ack-Profil, README). Der Nutzer hat ausdrücklich verlangt, sich daran zu halten.
- Die erste Spezifikation des Nutzers ist nicht mehr maßgeblich, wo sie vom Repo abweicht. Dazu gehören Vorlauf/Warmwasser-Adressen
  und die Standardwerte für die ACK-Emulation.
- Die XTR-Dateien im Repo sind für den Eco nicht maßgeblich, weil sie andere Register nutzen.

## Architektur

```
custom_components/thermia_itec_eco/
  modbus_rtu.py     CRC16, Frame-Parser (Resync), passiver Decoder (Schlüssel: Slave, r/w, Adresse)
  fields.py         Feldkatalog (Adresse, Skalierung, Gültigkeit, Standard) und Slave-zu-Gerät-Zuordnung
  emulation.py      Raumsensor- und 0x0F-ACK-Logik, reine Funktionen ohne HA
  transport.py      Serieller Port, Lese-Thread, Schreiben mit Repo-Zeiten
  runtime.py        Verbindet Bus, Dekoder und Emulationen, Quellsensor, Senden
  config_flow.py    Setup (Port, optionaler Raumsensor) und Optionen
  base.py           Gemeinsame Entitätsbasis, Geräte je Slave
  sensor.py, binary_sensor.py, climate.py, button.py, switch.py   Entitäten
tests/              Standardbibliothek (unittest), ohne Home Assistant
tools/              build_translations.py (Übersetzungen), build_register_docs.py (docs/REGISTERS.md)
```

Die reinen Module (`modbus_rtu`, `fields`, `emulation`) haben keine HA-Abhängigkeit und werden über `tests/_loader.py` geladen.
Die HA-Module werden nur auf Syntax geprüft (`py_compile`). **Sie wurden noch nie in einer echten Home-Assistant-Instanz ausgeführt.**

## Geräte in Home Assistant

- Thermia iTec Eco: Bus-Diagnose
- Regler (0x02), Zubehör-Schnittstelle (0x06), Raumregler (0x0A), DCM / Online-Modul (0x0F), Außeneinheit (0x1E)
- Die Slaves 0x04, 0x14, 0xA4, 0xA5 sind im Repo nicht dokumentiert und haben bewusst kein Gerät.

## Emulationen (Repo-Verhalten)

- **Raumsensor (0x0A):** Antwort auf den FC17-Poll (Lesen B3B0×3, Schreiben B3C4×3), 3,8 ms Wartezeit.
  Schalter AUS nach Neustart. Watchdog nur durch neue Werte des Quellsensors, Standard 30 min.
  Sollwert-Anforderung wird nach 5 Abfragen verworfen. Warmwasser-Auslöser einmalig.
- **0x0F ACK:** 8-Byte-FC10-Quittung 5 ms nach Empfang. FC03 0x0708 ×6 mit fester 17-Byte-Antwort, 5 ms.
  Schalter AN (wie im Repo, `RESTORE_DEFAULT_ON`).
- **Externer Teilnehmer:** Antwort eines zweiten Teilnehmers sperrt die jeweilige Emulation bis zum Neustart.
  Eigene Echos werden über Zeitfenster erkannt (0A: 500 ms, 0F: 150 ms).
- Es gibt keine globale Sendefreigabe mehr. Die Schalter sind die einzige Sperre.

## Entscheidungen (chronologisch, verdichtet)

1. Phase 1 passiv, Phase 2 Emulation. Sendefreigabe erst nach Prüfstand (später entfernt, siehe unten).
2. Adressen und Abläufe aus dem Repo. Vorlauf = `0xA7F8`, Warmwasser oben = `0xA7FB`, Warmwasser = `0xA7FC` (dezimal 43004).
3. Diagnose-Entitäten und Kandidaten standardmäßig aus. Emulationsstatus-Sensoren ebenfalls aus.
4. Ein Gerät pro Modbus-Slave, Zuordnung nach dem Repo-Protokollüberblick.
5. Passive Werte bleiben erhalten, bis ein neuer Wert kommt (wie im Repo). Kein Ablauf nach Zeit.
6. Watchdog wie im Repo: nur durch Änderungen des Quellsensors zurückgesetzt.
7. Globale Sendefreigabe (`tx_release`) entfernt, auf Wunsch des Nutzers.

## Offene Punkte

- **0x0F-ACK-Standard AN:** Ohne Freigabe sendet die ACK-Emulation direkt nach dem Start. Das entspricht dem Repo, ist aber ein echtes Sendeereignis. Entscheidung des Nutzers offen.
- **Timing:** Die Repo-Zeiten (3,8 ms, 5 ms) sind auf einem ESP32 mit Echtzeitverhalten gemessen. Python auf HA kann Jitter haben. Am Prüfstand messen.
- **Warmwasser- und Vorlaufwerte am Bus:** Am Display gegenprüfen, dass A7F8 wirklich die Vorlauftemperatur ist.
- **Unbekannte Slaves 0x04, 0x14, 0xA4, 0xA5:** keine Geräte. Auf Wunsch ein Gerät „Unbekannt“ mit Rohwerten.
- **Nicht getestet:** die Integration in einer echten HA-Instanz, die Oberfläche (Setup-Dialog, Optionen, Geräte) und das Senden am Bus.

## Nutzerpräferenzen

- Kommunikation auf Deutsch.
- Das Repo ist die Quelle der Wahrheit. Bei Abweichungen den Nutzer fragen, nicht selbst entscheiden.
- Bei Unklarheiten lieber nachfragen als raten.
- Diagnose-Entitäten standardmäßig aus.

## Weiterarbeiten

1. Tests ausführen: `python3 -m unittest discover -s tests -v`
2. Übersetzungen nach Änderungen an `fields.py` neu erzeugen: `python3 tools/build_translations.py`
3. Register-Doku neu erzeugen: `python3 tools/build_register_docs.py`
4. Neue Register immer mit Quellstelle im Repo belegen. Keine erfundenen Bedeutungen.
5. Änderungen am Sendepfad nur, wenn der Nutzer sie am Bus freigegeben hat.
