# Register-Übersicht

Automatisch aus `fields.py` erzeugt (`python3 tools/build_register_docs.py`). Nicht von Hand ändern.

Quelle der Adressen und Abläufe: ryckema/Thermia_itec, Ordner `Write (Beta)/iTec Eco`.

| Gerät (Slave) | Name (EN) | Quelle auf dem Bus | Art | Standard |
|---|---|---|---|---|
| controller | Supply temperature | `0x02 read A7F8` | sensor | an |
| controller | DHW upper temperature | `0x02 read A7FB` | sensor | an |
| controller | DHW temperature | `0x02 read A7FC (DHW main, repo)` | sensor | an |
| controller | Outdoor temperature | `0x02 read A802` | sensor | an |
| controller | SG mode | `0x02 read A7FD + A803` | text | an |
| controller | Condenser pump speed | `0x02 write A80F` | sensor | an |
| controller | Controller output bits A80C | `0x02 write A80C` | sensor | aus |
| controller | Controller context | `0x02 write A80C` | text | aus |
| controller | Controller accessory status A80E | `0x02 write A80E` | sensor | aus |
| controller | Controller flag A80C 0x10 | `0x02 write A80C` | binary | aus |
| controller | Controller flag A80C 0x20 | `0x02 write A80C` | binary | aus |
| controller | Controller flag A80E 0x08 | `0x02 write A80E` | binary | aus |
| controller | Controller flag A80E 0x20 | `0x02 write A80E` | binary | aus |
| room | Room temperature | `0x0A read B3B0` | sensor | an |
| room | Room setpoint | `0x0A write B3C5 (confirmed setpoint)` | sensor | an |
| room | Outdoor temperature (room bus) | `0x0A write B3C4` | sensor | aus |
| room | Hot water top-up active | `0x0A write B3C6 == 2` | binary | an |
| room | Room sensor control flag B3C6 | `0x0A write B3C6 != 0` | binary | aus |
| outdoor | Condenser inlet | `0x1E read 0000` | sensor | aus |
| outdoor | Condenser outlet | `0x1E read 0001` | sensor | aus |
| outdoor | Condenser delta T | `0x1E read 0000 + 0001` | sensor | aus |
| outdoor | Refrigerant temperature 1 | `0x1E read 0002` | sensor | aus |
| outdoor | Discharge gas temperature | `0x1E read 0003` | sensor | aus |
| outdoor | Refrigerant temperature 2 | `0x1E read 0004` | sensor | aus |
| outdoor | Average outdoor temperature | `0x1E read 0005` | sensor | aus |
| outdoor | Compressor temperature | `0x1E read 0006` | sensor | aus |
| outdoor | High pressure | `0x1E read 0008` | sensor | aus |
| outdoor | Outdoor unit target temperature | `0x1E read 000A` | sensor | aus |
| outdoor | Compressor frequency | `0x1E read 000B` | sensor | an |
| outdoor | Compressor max frequency ratio | `0x1E read 000C` | sensor | an |
| outdoor | Compressor current | `0x1E read 000D` | sensor | an |
| outdoor | Outdoor fan speed | `0x1E read 000E` | sensor | an |
| outdoor | Expansion valve steps | `0x1E read 0010` | sensor | aus |
| outdoor | Outdoor unit state bits | `0x1E read 0014` | sensor | aus |
| outdoor | Outdoor unit state | `0x1E read 0014` | text | an |
| outdoor | Compressor running | `0x1E read 0014 bit 0x01` | binary | an |
| outdoor | Compressor starting | `0x1E read 0000..000D (heuristic)` | binary | aus |
| outdoor | Outdoor fan running | `0x1E read 0014 bit 0x04` | binary | an |
| outdoor | Condenser pump running | `0x1E read 0014 bit 0x08` | binary | an |
| outdoor | Outdoor unit status flags | `0x1E read 0015` | sensor | aus |
| outdoor | Run enable acknowledged | `0x1E read 0015 bit 0x0200` | binary | an |
| outdoor | Heating context | `0x1E read 0015 bit 0x0020` | binary | an |
| outdoor | Hot water context | `0x1E read 0015 bit 0x0040` | binary | an |
| outdoor | Cooling context | `0x1E read 0015 bit 0x0080` | binary | aus |
| outdoor | Operating mode | `0x1E read 0015` | text | an |
| outdoor | Heating active | `0x1E read 0014/0015 + write 0007/0008` | binary | an |
| outdoor | Hot water active | `0x1E read 0014/0015 + write 0007/0008` | binary | an |
| outdoor | Cooling active | `0x1E read 0014/0015 + write 0007/0008` | binary | aus |
| outdoor | Commanded target temperature | `0x1E write 0001` | sensor | aus |
| outdoor | Mode request raw | `0x1E write 0004` | sensor | aus |
| outdoor | Mode request | `0x1E write 0004` | text | aus |
| outdoor | Outdoor unit cycle request | `0x1E write 0007` | binary | aus |
| outdoor | Outdoor unit run enable command | `0x1E write 0008` | binary | aus |
| dcm | Heating curve | `0x0F write 03E8` | sensor | an |
| dcm | Heating minimum | `0x0F write 03E9` | sensor | an |
| dcm | Heating maximum | `0x0F write 03EA` | sensor | an |
| dcm | Heating curve correction +5 | `0x0F write 03EB` | sensor | an |
| dcm | Heating curve correction 0 | `0x0F write 03EC` | sensor | an |
| dcm | Heating curve correction -5 | `0x0F write 03ED` | sensor | an |
| dcm | Heating stop | `0x0F write 03EE` | sensor | an |
| dcm | Reduced temperature | `0x0F write 03EF` | sensor | an |
| dcm | Room factor | `0x0F write 03F0` | sensor | an |
| dcm | High power | `0x0F write 03F3` | binary | an |
| dcm | Room setpoint (settings page) | `0x0F write 03F4` | sensor | aus |
| dcm | Hot water enabled | `0x0F write 042E` | binary | an |
| dcm | Hot water mode | `0x0F write 042F` | text | an |
| dcm | Startup HT | `0x0F write 0433` | sensor | aus |
| dcm | Heating time | `0x0F write 0434` | sensor | aus |
| dcm | Operation mode setting | `0x0F write 0553` | text | aus |
| dcm | Cooling enabled | `0x0F write 0442` | binary | aus |
| dcm | Cooling desired temperature | `0x0F write 0443` | sensor | aus |
| dcm | Cooling active above | `0x0F write 0445` | sensor | aus |
| dcm | Cooling time | `0x0F write 0449` | sensor | aus |
| dcm | Cooling room sensor | `0x0F write 044C` | binary | aus |
| dcm | Cooling room hysteresis low | `0x0F write 044D` | sensor | aus |
| dcm | Cooling room hysteresis high | `0x0F write 044E` | sensor | aus |
| accessory | Accessory context raw AFDC | `0x06 write AFDC` | sensor | aus |
| accessory | Accessory propagated outdoor temperature | `0x06 write AFE0` | sensor | an |
