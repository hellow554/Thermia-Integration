# Register-Übersicht

Automatisch erzeugt aus `components/thermia_bus/catalogue.py` (`python3 tools/gen.py`). Nicht von Hand ändern.

Quelle der Adressen und Abläufe: ryckema/Thermia_itec, Ordner `Write (Beta)/iTec Eco`.

Zusätzlich gibt es Diagnose- und Emulationswerte ohne Register: `bus_status`, `frames_ok`, `resync_bytes`, `unmatched_responses`, `room_emulation_status`, `ack_emulation_status`, `room_responses_sent`, `ack_frames_sent`.

| Gerät | Name (DE) | Quelle auf dem Bus | Art | Standard |
|---|---|---|---|---|
| Regler (0x02) | Vorlauftemperatur | `0x02 read A7F8` | sensor | an |
| Regler (0x02) | Warmwassertemperatur oben | `0x02 read A7FB` | sensor | an |
| Regler (0x02) | Warmwassertemperatur | `0x02 read A7FC` | sensor | an |
| Regler (0x02) | Außentemperatur | `0x02 read A802` | sensor | an |
| Regler (0x02) | SG-Modus | `0x02 read A7FD + A803` | text | an |
| Regler (0x02) | Kondensatorpumpe Drehzahl | `0x02 write A80F` | sensor | an |
| Regler (0x02) | Reglerausgänge A80C | `0x02 write A80C` | sensor | aus |
| Regler (0x02) | Reglerkontext | `0x02 write A80C` | text | aus |
| Regler (0x02) | Reglerzubehör A80E | `0x02 write A80E` | sensor | aus |
| Regler (0x02) | Reglerflag A80C 0x10 | `0x02 write A80C` | binary | aus |
| Regler (0x02) | Reglerflag A80C 0x20 | `0x02 write A80C` | binary | aus |
| Regler (0x02) | Reglerflag A80E 0x08 | `0x02 write A80E` | binary | aus |
| Regler (0x02) | Reglerflag A80E 0x20 | `0x02 write A80E` | binary | aus |
| Zubehör (0x06) | Zubehör Kontext Rohwert AFDC | `0x06 write AFDC` | sensor | aus |
| Zubehör (0x06) | Außentemperatur (Zubehör) | `0x06 write AFE0` | sensor | an |
| Raumregler (0x0A) | Raumtemperatur | `0x0A read B3B0` | sensor | an |
| Raumregler (0x0A) | Raum-Sollwert | `0x0A write B3C5` | sensor | an |
| Raumregler (0x0A) | Außentemperatur (Raumbus) | `0x0A write B3C4` | sensor | aus |
| Raumregler (0x0A) | Warmwasser-Nachheizung aktiv | `0x0A write B3C6 == 2` | binary | an |
| Raumregler (0x0A) | Raumsensor-Steuerflag B3C6 | `0x0A write B3C6 != 0` | binary | aus |
| Außeneinheit (0x1E) | Kondensator Eintritt | `0x1E read 0000` | sensor | aus |
| Außeneinheit (0x1E) | Kondensator Austritt | `0x1E read 0001` | sensor | aus |
| Außeneinheit (0x1E) | Kondensator Spreizung | `0x1E read 0000 + 0001` | sensor | aus |
| Außeneinheit (0x1E) | Kältemittel Temperatur 1 | `0x1E read 0002` | sensor | aus |
| Außeneinheit (0x1E) | Heißgastemperatur | `0x1E read 0003` | sensor | aus |
| Außeneinheit (0x1E) | Kältemittel Temperatur 2 | `0x1E read 0004` | sensor | aus |
| Außeneinheit (0x1E) | Mittlere Außentemperatur | `0x1E read 0005` | sensor | aus |
| Außeneinheit (0x1E) | Verdichtertemperatur | `0x1E read 0006` | sensor | aus |
| Außeneinheit (0x1E) | Hochdruck | `0x1E read 0008` | sensor | aus |
| Außeneinheit (0x1E) | Zielwert Außeneinheit | `0x1E read 000A` | sensor | aus |
| Außeneinheit (0x1E) | Verdichterfrequenz | `0x1E read 000B` | sensor | an |
| Außeneinheit (0x1E) | Verdichter max. Frequenzanteil | `0x1E read 000C` | sensor | an |
| Außeneinheit (0x1E) | Verdichterstrom | `0x1E read 000D` | sensor | an |
| Außeneinheit (0x1E) | Ventilatordrehzahl | `0x1E read 000E` | sensor | an |
| Außeneinheit (0x1E) | Expansionsventil Schritte | `0x1E read 0010` | sensor | aus |
| Außeneinheit (0x1E) | Außeneinheit Zustandsbits | `0x1E read 0014` | sensor | aus |
| Außeneinheit (0x1E) | Außeneinheit Zustand | `0x1E read 0014` | text | an |
| Außeneinheit (0x1E) | Verdichter läuft | `0x1E read 0014 bit 0x01` | binary | an |
| Außeneinheit (0x1E) | Verdichter startet | `0x1E read 0000..000D (heuristic)` | binary | aus |
| Außeneinheit (0x1E) | Außenventilator läuft | `0x1E read 0014 bit 0x04` | binary | an |
| Außeneinheit (0x1E) | Kondensatorpumpe läuft | `0x1E read 0014 bit 0x08` | binary | an |
| Außeneinheit (0x1E) | Außeneinheit Statusflags | `0x1E read 0015` | sensor | aus |
| Außeneinheit (0x1E) | Freigabe bestätigt | `0x1E read 0015 bit 0x0200` | binary | an |
| Außeneinheit (0x1E) | Heizkontext | `0x1E read 0015 bit 0x0020` | binary | an |
| Außeneinheit (0x1E) | Warmwasserkontext | `0x1E read 0015 bit 0x0040` | binary | an |
| Außeneinheit (0x1E) | Kühlkontext | `0x1E read 0015 bit 0x0080` | binary | aus |
| Außeneinheit (0x1E) | Betriebsmodus | `0x1E read 0015` | text | an |
| Außeneinheit (0x1E) | Heizen aktiv | `0x1E read 0014/0015 + write 0007/0008` | binary | an |
| Außeneinheit (0x1E) | Warmwasser aktiv | `0x1E read 0014/0015 + write 0007/0008` | binary | an |
| Außeneinheit (0x1E) | Kühlen aktiv | `0x1E read 0014/0015 + write 0007/0008` | binary | aus |
| Außeneinheit (0x1E) | Vorgegebene Zieltemperatur | `0x1E write 0001` | sensor | aus |
| Außeneinheit (0x1E) | Betriebsanforderung Rohwert | `0x1E write 0004` | sensor | aus |
| Außeneinheit (0x1E) | Betriebsanforderung | `0x1E write 0004` | text | aus |
| Außeneinheit (0x1E) | Außeneinheit Zyklusanforderung | `0x1E write 0007` | binary | aus |
| Außeneinheit (0x1E) | Außeneinheit Freigabebefehl | `0x1E write 0008` | binary | aus |
| DCM / Online-Modul (0x0F) | Heizkurve | `0x0F write 03E8` | sensor | an |
| DCM / Online-Modul (0x0F) | Heizen Minimum | `0x0F write 03E9` | sensor | an |
| DCM / Online-Modul (0x0F) | Heizen Maximum | `0x0F write 03EA` | sensor | an |
| DCM / Online-Modul (0x0F) | Heizkurvenkorrektur +5 | `0x0F write 03EB` | sensor | an |
| DCM / Online-Modul (0x0F) | Heizkurvenkorrektur 0 | `0x0F write 03EC` | sensor | an |
| DCM / Online-Modul (0x0F) | Heizkurvenkorrektur -5 | `0x0F write 03ED` | sensor | an |
| DCM / Online-Modul (0x0F) | Heizgrenze | `0x0F write 03EE` | sensor | an |
| DCM / Online-Modul (0x0F) | Absenktemperatur | `0x0F write 03EF` | sensor | an |
| DCM / Online-Modul (0x0F) | Raumeinfluss | `0x0F write 03F0` | sensor | an |
| DCM / Online-Modul (0x0F) | Hochleistung | `0x0F write 03F3` | binary | an |
| DCM / Online-Modul (0x0F) | Raum-Sollwert (Einstellungsseite) | `0x0F write 03F4` | sensor | aus |
| DCM / Online-Modul (0x0F) | Warmwasser aktiv (Einstellung) | `0x0F write 042E` | binary | an |
| DCM / Online-Modul (0x0F) | Warmwasser-Modus | `0x0F write 042F` | text | an |
| DCM / Online-Modul (0x0F) | Startzeit HT | `0x0F write 0433` | sensor | aus |
| DCM / Online-Modul (0x0F) | Heizzeit | `0x0F write 0434` | sensor | aus |
| DCM / Online-Modul (0x0F) | Betriebsart (Einstellung) | `0x0F write 0553` | text | aus |
| DCM / Online-Modul (0x0F) | Kühlung aktiv (Einstellung) | `0x0F write 0442` | binary | aus |
| DCM / Online-Modul (0x0F) | Kühl-Solltemperatur | `0x0F write 0443` | sensor | aus |
| DCM / Online-Modul (0x0F) | Kühlung aktiv ab | `0x0F write 0445` | sensor | aus |
| DCM / Online-Modul (0x0F) | Kühlzeit | `0x0F write 0449` | sensor | aus |
| DCM / Online-Modul (0x0F) | Kühlung Raumsensor | `0x0F write 044C` | binary | aus |
| DCM / Online-Modul (0x0F) | Kühlung Raumhysterese niedrig | `0x0F write 044D` | sensor | aus |
| DCM / Online-Modul (0x0F) | Kühlung Raumhysterese hoch | `0x0F write 044E` | sensor | aus |
