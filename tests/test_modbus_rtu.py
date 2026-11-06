"""Unit tests for the pure Modbus RTU logic. Standard library only."""
import unittest

import _loader  # noqa: F401
from frames import fc10_request, fc17_request, read_request, read_response
from thermia_pure import modbus_rtu as rtu


class CrcTests(unittest.TestCase):
    def test_known_modbus_vector(self):
        self.assertEqual(
            rtu.append_crc(bytes.fromhex("01 03 00 00 00 0A")),
            bytes.fromhex("01 03 00 00 00 0A C5 CD"),
        )

    def test_corrupted_frame_is_rejected(self):
        frame = read_request(0x0A, 0x03, 0xA7FB, 1)
        corrupted = frame[:-1] + bytes([frame[-1] ^ 0x01])
        self.assertFalse(rtu.has_valid_crc(corrupted))


class FrameParserTests(unittest.TestCase):
    def test_frame_split_across_chunks(self):
        frame = read_request(0x0A, 0x03, 0xA7FB, 1)
        parser = rtu.FrameParser()
        self.assertEqual(parser.feed(frame[:3]), [])
        self.assertEqual(parser.feed(frame[3:]), [frame])

    def test_two_frames_in_one_chunk(self):
        a = fc17_request(0x02, 0xA7F8, 15, 0, [])
        b = read_response(0x02, 0x17, [1, 2])
        self.assertEqual(rtu.FrameParser().feed(a + b), [a, b])

    def test_resync_after_leading_garbage(self):
        frame = read_request(0x0A, 0x03, 0xA7FB, 1)
        parser = rtu.FrameParser()
        self.assertEqual(parser.feed(b"\x55\x33" + frame), [frame])
        self.assertGreater(parser.resync_bytes, 0)

    def test_corrupted_frame_is_not_emitted(self):
        frame = read_request(0x0A, 0x03, 0xA7FB, 1)
        corrupted = frame[:-1] + bytes([frame[-1] ^ 0xFF])
        self.assertEqual(rtu.FrameParser().feed(corrupted), [])

    def test_fc17_request_and_response(self):
        req = fc17_request(0x0A, 0xB3B0, 3, 0xB3C4, [5, 21, 2])
        resp = read_response(0x0A, 0x17, [215, 0, 0])
        parser = rtu.FrameParser()
        self.assertEqual(parser.feed(req), [req])
        self.assertEqual(parser.feed(resp), [resp])

    def test_short_fc17_response_followed_by_request(self):
        # Regression: a 9-byte FC17 response must not wait for the 11-byte request header.
        resp = read_response(0x02, 0x17, [1, 2])
        req = fc17_request(0x0A, 0xB3B0, 3, 0xB3C4, [5, 21, 2])
        self.assertEqual(rtu.FrameParser().feed(resp + req), [resp, req])

    def test_exception_frame(self):
        frame = rtu.append_crc(bytes([0x0A, 0x83, 0x02]))
        self.assertEqual(rtu.FrameParser().feed(frame), [frame])

    def test_flush_discards_partial_frame(self):
        frame = read_request(0x0A, 0x03, 0xA7FB, 1)
        parser = rtu.FrameParser()
        parser.feed(frame[:4])
        parser.flush()
        resp = read_response(0x0A, 0x03, [33])
        self.assertEqual(parser.feed(resp), [resp])


class PassiveDecoderTests(unittest.TestCase):
    def _decode(self, *frames, now=100.0):
        parser = rtu.FrameParser()
        dec = rtu.PassiveDecoder()
        for chunk in frames:
            for frame in parser.feed(chunk):
                dec.handle_frame(frame, now)
        return dec

    def test_fc04_request_response_stores_read_space(self):
        dec = self._decode(read_request(0x1E, 0x04, 0x0000, 2),
                           read_response(0x1E, 0x04, [-20, 50]))
        self.assertEqual(dec.fresh(0x1E, "r", 0x0000, 100.0), -20)
        self.assertEqual(dec.fresh(0x1E, "r", 0x0001, 100.0), 50)

    def test_fc03_request_response(self):
        dec = self._decode(read_request(0x0A, 0x03, 0x0000, 1), read_response(0x0A, 0x03, [33]))
        self.assertEqual(dec.fresh(0x0A, "r", 0x0000, 100.0), 33)

    def test_write_and_read_on_same_address_are_kept_apart(self):
        dec = self._decode(
            read_request(0x1E, 0x04, 0x0000, 2),
            read_response(0x1E, 0x04, [0, 50]),
            fc10_request(0x1E, 0x0001, [1000]),
        )
        self.assertEqual(dec.fresh(0x1E, "r", 0x0001, 100.0), 50)
        self.assertEqual(dec.fresh(0x1E, "w", 0x0001, 100.0), 1000)

    def test_fc17_write_part_is_stored_from_request(self):
        dec = self._decode(fc17_request(0x0A, 0xB3B0, 3, 0xB3C4, [5, 21, 2]))
        self.assertEqual(dec.fresh(0x0A, "w", 0xB3C4, 100.0), 5)
        self.assertEqual(dec.fresh(0x0A, "w", 0xB3C6, 100.0), 2)

    def test_response_without_request_is_counted(self):
        dec = self._decode(read_response(0x0A, 0x03, [33]))
        self.assertEqual(dec.unmatched_responses, 1)
        self.assertIsNone(dec.fresh(0x0A, "r", 0x0000, 100.0))

    def test_values_are_kept_until_replaced(self):
        dec = self._decode(read_request(0x0A, 0x03, 0, 1), read_response(0x0A, 0x03, [33]))
        self.assertEqual(dec.fresh(0x0A, "r", 0, 100.0 + 10 * rtu.STALE_SECONDS), 33)

    def test_explicit_max_age_expires_values(self):
        dec = self._decode(read_request(0x0A, 0x03, 0, 1), read_response(0x0A, 0x03, [33]))
        self.assertIsNone(dec.fresh(0x0A, "r", 0, 100.0 + rtu.STALE_SECONDS + 1, max_age=rtu.STALE_SECONDS))


if __name__ == "__main__":
    unittest.main()
