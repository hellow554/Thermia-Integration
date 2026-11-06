"""Tests for the field catalogue: values from synthetic bus traffic and table rules."""
import unittest

import _loader  # noqa: F401
from frames import fc10_request, fc17_request, read_request, read_response
from thermia_pure import modbus_rtu as rtu
from thermia_pure.fields import BUS_ENTITY_NAMES, FIELDS, SLAVE_DEVICES, device_of

BY_KEY = {f.key: f for f in FIELDS}
NOW = 100.0


def decode(*chunks, now=NOW):
    parser = rtu.FrameParser()
    dec = rtu.PassiveDecoder()
    for chunk in chunks:
        for frame in parser.feed(chunk):
            dec.handle_frame(frame, now)
    return dec


def value(key, dec, now=NOW):
    return BY_KEY[key].getter(dec, now)


class ControllerBlockTests(unittest.TestCase):
    def test_a7f8_block_gives_supply_outdoor_and_sg(self):
        values = [0] * 15
        values[0] = 35      # A7F8 supply
        values[3] = 50      # A7FB DHW upper
        values[5] = 1000    # A7FD SG discriminator 1
        values[10] = -3     # A802 outdoor
        values[11] = 232    # A803 SG discriminator 2
        dec = decode(fc17_request(0x02, 0xA7F8, 15, 0, []),
                     read_response(0x02, 0x17, values))
        self.assertEqual(value("supply_temperature", dec), 35.0)
        self.assertEqual(value("dhw_upper_temperature", dec), 50.0)
        self.assertEqual(value("outdoor_temperature", dec), -3.0)
        self.assertEqual(value("sg_mode", dec), "Peak (1-1)")

    def test_sentinel_minus_1000_means_no_value(self):
        values = [0] * 15
        values[0] = -1000
        values[3] = -1000
        dec = decode(fc17_request(0x02, 0xA7F8, 15, 0, []),
                     read_response(0x02, 0x17, values))
        self.assertIsNone(value("supply_temperature", dec))
        self.assertIsNone(value("dhw_upper_temperature", dec))

    def test_controller_context_from_a80c_write(self):
        dec = decode(fc10_request(0x02, 0xA80C, [0x0041]))
        self.assertEqual(value("controller_context", dec), "Active / DHW valve")
        self.assertTrue(value("controller_flag_a80c_0x10", dec) is False)


class OutdoorUnitTests(unittest.TestCase):
    def _block(self):
        values = [0] * 0x16
        values[0x00] = -20    # condenser inlet  -2.0 C
        values[0x01] = 50     # condenser outlet  5.0 C
        values[0x0B] = 60     # compressor frequency 60 Hz
        values[0x0D] = 35     # compressor current 3.5 A
        values[0x0E] = 1200   # fan rpm
        values[0x14] = 29     # state bits: compressor, fan, pump, base
        values[0x15] = 0x0221 # status flags: heating context, run enable acknowledged
        return values

    def test_fc04_block_values_and_bits(self):
        dec = decode(read_request(0x1E, 0x04, 0x0000, 0x16),
                     read_response(0x1E, 0x04, self._block()))
        self.assertEqual(value("condenser_in", dec), -2.0)
        self.assertEqual(value("condenser_delta", dec), 7.0)
        self.assertEqual(value("compressor_frequency", dec), 60.0)
        self.assertEqual(value("compressor_current", dec), 3.5)
        self.assertEqual(value("fan_speed", dec), 1200.0)
        self.assertTrue(value("compressor_running", dec))
        self.assertTrue(value("outdoor_fan_running", dec))
        self.assertTrue(value("condenser_pump_running", dec))
        self.assertEqual(value("outdoor_unit_state", dec), "Water flow + fan + compressor")
        self.assertEqual(value("operating_mode", dec), "Heating")
        self.assertTrue(value("run_enable_acknowledged", dec))

    def test_active_flag_needs_controller_commands(self):
        dec = decode(read_request(0x1E, 0x04, 0x0000, 0x16),
                     read_response(0x1E, 0x04, self._block()))
        self.assertFalse(value("heating_active", dec))
        dec = decode(read_request(0x1E, 0x04, 0x0000, 0x16),
                     read_response(0x1E, 0x04, self._block()),
                     fc10_request(0x1E, 0x0007, [1, 1]))
        self.assertTrue(value("heating_active", dec))

    def test_commanded_target_does_not_overwrite_condenser_outlet(self):
        dec = decode(read_request(0x1E, 0x04, 0x0000, 0x16),
                     read_response(0x1E, 0x04, self._block()),
                     fc10_request(0x1E, 0x0001, [1000]))
        self.assertEqual(value("condenser_out", dec), 5.0)
        self.assertEqual(value("commanded_target_temperature", dec), 100.0)


class SettingsAndRoomTests(unittest.TestCase):
    def test_heating_curve_block_from_0f_writes(self):
        block = [27, 20, 45, 0, 0, 1, 17, 17, 0, 0, 0, 1]  # 0x03E8..0x03F3
        dec = decode(fc10_request(0x0F, 0x03E8, block))
        self.assertEqual(value("heating_curve", dec), 27.0)
        self.assertEqual(value("heating_min", dec), 20.0)
        self.assertEqual(value("heating_max", dec), 45.0)
        self.assertEqual(value("curve_minus5", dec), 1.0)
        self.assertEqual(value("heating_stop", dec), 17.0)
        self.assertTrue(value("high_power", dec))

    def test_room_sensor_exchange(self):
        dec = decode(fc17_request(0x0A, 0xB3B0, 3, 0xB3C4, [5, 21, 2]),
                     read_response(0x0A, 0x17, [215, 0, 0]))
        self.assertEqual(value("room_temperature", dec), 21.5)
        self.assertEqual(value("room_setpoint", dec), 21.0)
        self.assertEqual(value("room_bus_outdoor_temperature", dec), 5.0)
        self.assertTrue(value("dhw_topup_active", dec))

    def test_values_are_kept_like_the_repo(self):
        dec = decode(fc17_request(0x0A, 0xB3B0, 3, 0xB3C4, [5, 21, 2]),
                     read_response(0x0A, 0x17, [215, 0, 0]))
        self.assertEqual(value("room_temperature", dec, now=NOW + 10 * rtu.STALE_SECONDS), 21.5)


class AccessoryAndDeviceTests(unittest.TestCase):
    def test_accessory_outdoor_temperature_from_fc17_write(self):
        dec = decode(fc10_request(0x06, 0xAFE0, [12]))
        self.assertEqual(value("accessory_outdoor_temperature", dec), 12.0)

    def test_every_field_maps_to_a_device(self):
        for f in FIELDS:
            self.assertIn(device_of(f), set(SLAVE_DEVICES.values()), f.key)

    def test_undocumented_slaves_have_no_device(self):
        for f in FIELDS:
            self.assertNotIn(f.source.split()[0], ("0x04", "0x14", "0xA4", "0xA5"), f.key)


class TableRuleTests(unittest.TestCase):
    def test_keys_are_unique(self):
        keys = [f.key for f in FIELDS] + list(BUS_ENTITY_NAMES)
        self.assertEqual(len(keys), len(set(keys)))

    def test_every_field_has_both_names(self):
        for f in FIELDS:
            self.assertTrue(f.name_en.strip(), f.key)
            self.assertTrue(f.name_de.strip(), f.key)

    def test_diagnostic_and_candidate_disabled_by_default(self):
        for f in FIELDS:
            if f.diagnostic or f.candidate or f.blocked:
                self.assertFalse(f.enabled_default, f.key)
            else:
                self.assertTrue(f.enabled_default, f.key)

    def test_dhw_main_sensor_is_enabled_per_repo(self):
        self.assertFalse(BY_KEY["dhw_temperature"].blocked)
        self.assertTrue(BY_KEY["dhw_temperature"].enabled_default)

    def test_bus_diagnostics_are_not_register_fields(self):
        self.assertFalse(set(BUS_ENTITY_NAMES) & set(BY_KEY))


if __name__ == "__main__":
    unittest.main()
