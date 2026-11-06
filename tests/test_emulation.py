"""Tests for room sensor (0x0A) and 0x0F ACK emulation. Pure logic, no bus, no Home Assistant."""
import unittest

import _loader  # noqa: F401
from frames import fc10_request, fc17_request, read_request
from thermia_pure import emulation as em
from thermia_pure.modbus_rtu import append_crc, has_valid_crc
from thermia_pure.emulation import AckEmulator, AckStatus, RoomSensorEmulator, RoomStatus


def active_room(now=0.0, watchdog=1800.0):
    room = RoomSensorEmulator(watchdog_seconds=watchdog, enabled=True)
    room.set_temperature(21.5, now)
    return room


def setpoint_bytes(frame):
    return frame[5:7]


def topup_bytes(frame):
    return frame[7:9]


class FrameTests(unittest.TestCase):
    def test_controller_poll_is_recognised(self):
        self.assertTrue(em.is_room_poll(fc17_request(0x0A, 0xB3B0, 3, 0xB3C4, [5, 21, 2])))

    def test_other_fc17_is_not_a_poll(self):
        self.assertFalse(em.is_room_poll(fc17_request(0x0A, 0xB3B0, 1, 0xB3C4, [5, 21, 2])))

    def test_room_response_layout(self):
        frame = em.room_poll_response(21.5, 22, 1)
        self.assertEqual(frame[:3], bytes([0x0A, 0x17, 0x06]))
        self.assertEqual(frame[3:9], bytes.fromhex("00 D7 00 16 00 01"))  # 215, 22, 1
        self.assertTrue(has_valid_crc(frame))
        self.assertTrue(em.is_room_response(frame))

    def test_idle_0708_reply_matches_repo_bytes(self):
        self.assertEqual(em.IDLE_0708_REPLY, bytes.fromhex("0F 03 0C 00 00 00 00 00 00 00 00 00 00 00 06 9D 76"))

    def test_fc10_ack_layout(self):
        frame = em.ack_fc10_response(0x03E8, 12)
        self.assertEqual(frame[:6], bytes.fromhex("0F 10 03 E8 00 0C"))
        self.assertTrue(has_valid_crc(frame))

    def test_pre_delays_follow_repo(self):
        self.assertEqual(em.tx_pre_delay(em.room_poll_response(21.5, 0, 0)), 0.0038)
        self.assertEqual(em.tx_pre_delay(em.ack_fc10_response(0x03E8, 12)), 0.005)
        self.assertEqual(em.tx_pre_delay(em.IDLE_0708_REPLY), 0.005)

    def test_parsers(self):
        self.assertEqual(em.parse_fc10_request(fc10_request(0x0F, 0x03E8, [1, 2])), (0x03E8, 2))
        self.assertEqual(em.parse_fc03_request(read_request(0x0F, 0x03, 0x0708, 6)), (0x0708, 6))
        self.assertIsNone(em.parse_fc03_request(fc10_request(0x0F, 0x03E8, [1])))


class RoomEmulatorTests(unittest.TestCase):
    def test_disabled_gives_no_response(self):
        room = RoomSensorEmulator()
        room.set_temperature(21.5, 0.0)
        self.assertIsNone(room.on_controller_poll(1.0, transmit=True))

    def test_no_transmit_permission_has_no_side_effects(self):
        room = active_room()
        room.request_topup()
        self.assertIsNone(room.on_controller_poll(1.0, transmit=False))
        self.assertTrue(room.topup_pending)
        self.assertEqual(room.responses_sent, 0)

    def test_topup_is_one_shot(self):
        room = active_room()
        room.request_topup()
        first = room.on_controller_poll(1.0, transmit=True)
        second = room.on_controller_poll(2.0, transmit=True)
        self.assertEqual(topup_bytes(first), b"\x00\x01")
        self.assertEqual(topup_bytes(second), b"\x00\x00")

    def test_confirmed_setpoint_clears_request(self):
        room = active_room()
        room.request_setpoint(22)
        self.assertEqual(setpoint_bytes(room.on_controller_poll(1.0, transmit=True)), b"\x00\x16")
        room.on_bus_setpoint(22)
        self.assertEqual(room.setpoint_request, 0)
        self.assertEqual(setpoint_bytes(room.on_controller_poll(2.0, transmit=True)), b"\x00\x00")

    def test_unconfirmed_setpoint_is_dropped_after_six_polls(self):
        room = active_room()
        room.request_setpoint(22)
        sent = [setpoint_bytes(room.on_controller_poll(1.0 + i, transmit=True)) for i in range(8)]
        self.assertEqual(sent.count(b"\x00\x16"), 6)
        self.assertEqual(sent[-1], b"\x00\x00")

    def test_setpoint_equal_to_bus_sends_no_request(self):
        room = active_room()
        room.on_bus_setpoint(21)
        room.request_setpoint(21)
        self.assertEqual(room.setpoint_request, 0)

    def test_setpoint_is_clamped(self):
        room = active_room()
        self.assertEqual(room.request_setpoint(45), 30)
        self.assertEqual(room.request_setpoint(3), 10)

    def test_panel_dial_syncs_target(self):
        room = RoomSensorEmulator(enabled=True)
        room.on_bus_setpoint(18)
        self.assertEqual(room.target, 18)

    def test_watchdog_stops_responses_and_recovers(self):
        room = active_room(0.0)
        self.assertIsNone(room.on_controller_poll(1801.0, transmit=True))
        self.assertEqual(room.status(1801.0), RoomStatus.TIMEOUT)
        room.set_temperature(20.0, 1900.0)
        self.assertIsNotNone(room.on_controller_poll(1901.0, transmit=True))

    def test_invalid_temperature_is_rejected(self):
        room = RoomSensorEmulator(enabled=True)
        self.assertFalse(room.set_temperature(40.0, 0.0))
        self.assertEqual(room.status(0.0), RoomStatus.WAITING)

    def test_own_echo_does_not_block(self):
        room = active_room()
        room.on_controller_poll(10.0, transmit=True)
        room.on_bus_room_response(10.1)
        self.assertNotEqual(room.status(10.1), RoomStatus.BLOCKED)

    def test_external_room_sensor_blocks(self):
        room = active_room()
        room.on_bus_room_response(10.0)
        self.assertEqual(room.status(10.0), RoomStatus.BLOCKED)
        self.assertIsNone(room.on_controller_poll(10.0, transmit=True))


class AckEmulatorTests(unittest.TestCase):
    def test_ack_only_when_enabled_and_transmit_released(self):
        ack = AckEmulator()
        self.assertIsNone(ack.on_fc10_request(0x0F, 0x03E8, 12, 1.0, transmit=True))
        ack.enabled = True
        self.assertIsNotNone(ack.on_fc10_request(0x0F, 0x03E8, 12, 1.0, transmit=True))
        self.assertEqual(ack.acks_sent, 1)
        self.assertIsNone(ack.on_fc10_request(0x0F, 0x03E8, 12, 2.0, transmit=False))

    def test_external_0f_responder_blocks(self):
        ack = AckEmulator(enabled=True)
        ack.observe_frame(append_crc(bytes([0x0F, 0x10, 0x03, 0xE8, 0x00, 0x0C])), now=10.0)
        self.assertEqual(ack.status(), AckStatus.BLOCKED)
        self.assertIsNone(ack.on_fc10_request(0x0F, 0x03E8, 12, 11.0, transmit=True))

    def test_own_echo_is_not_a_peer(self):
        ack = AckEmulator(enabled=True)
        ack.on_fc10_request(0x0F, 0x03E8, 12, now=10.0, transmit=True)
        ack.observe_frame(em.ack_fc10_response(0x03E8, 12), now=10.05)
        self.assertFalse(ack.peer_detected)

    def test_ack_is_on_by_default_like_the_repo(self):
        self.assertTrue(AckEmulator(enabled=True).status() is AckStatus.ACTIVE)

    def test_idle_reply_on_0708_request(self):
        ack = AckEmulator(enabled=True)
        self.assertEqual(ack.on_fc03_request(0x0F, 0x0708, 6, 1.0, transmit=True), em.IDLE_0708_REPLY)
        self.assertEqual(ack.idle_replies_sent, 1)


if __name__ == "__main__":
    unittest.main()
