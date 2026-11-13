// Host-side unit tests for the protocol core. Build and run with tests/run_tests.sh.
#include <cstdio>
#include <cstring>
#include <string>

#include "thermia_core.h"

using namespace thermia_core;

static int g_failures = 0;
static int g_checks = 0;

#define CHECK(cond)                                                                 \
  do {                                                                              \
    ++g_checks;                                                                     \
    if (!(cond)) {                                                                  \
      ++g_failures;                                                                 \
      std::printf("FAIL %s:%d: %s\n", __FILE__, __LINE__, #cond);                   \
    }                                                                               \
  } while (0)

static Bytes hex(const char* s) {
  Bytes out;
  unsigned v;
  while (*s) {
    if (*s == ' ') { ++s; continue; }
    std::sscanf(s, "%2x", &v);
    out.push_back(static_cast<uint8_t>(v));
    s += 2;
  }
  return out;
}

static Bytes fc03_req(uint8_t slave, uint16_t start, uint16_t count) {
  Bytes p = {slave, FC_READ_HOLDING, static_cast<uint8_t>(start >> 8), static_cast<uint8_t>(start & 0xFF),
             static_cast<uint8_t>(count >> 8), static_cast<uint8_t>(count & 0xFF)};
  return append_crc(p);
}

static Bytes read_resp(uint8_t slave, uint8_t fc, const std::vector<int>& values) {
  Bytes p = {slave, fc, static_cast<uint8_t>(values.size() * 2)};
  for (int v : values) {
    p.push_back(static_cast<uint8_t>((v >> 8) & 0xFF));
    p.push_back(static_cast<uint8_t>(v & 0xFF));
  }
  return append_crc(p);
}

static Bytes fc10_req(uint8_t slave, uint16_t start, const std::vector<int>& values) {
  Bytes p = {slave, FC_WRITE_MULTIPLE, static_cast<uint8_t>(start >> 8), static_cast<uint8_t>(start & 0xFF),
             static_cast<uint8_t>(values.size() >> 8), static_cast<uint8_t>(values.size() & 0xFF),
             static_cast<uint8_t>(values.size() * 2)};
  for (int v : values) {
    p.push_back(static_cast<uint8_t>((v >> 8) & 0xFF));
    p.push_back(static_cast<uint8_t>(v & 0xFF));
  }
  return append_crc(p);
}

static Bytes fc17_req(uint8_t slave, uint16_t rs, uint16_t rc, uint16_t ws, const std::vector<int>& writes) {
  Bytes p = {slave, FC_READ_WRITE, static_cast<uint8_t>(rs >> 8), static_cast<uint8_t>(rs & 0xFF),
             static_cast<uint8_t>(rc >> 8), static_cast<uint8_t>(rc & 0xFF),
             static_cast<uint8_t>(ws >> 8), static_cast<uint8_t>(ws & 0xFF),
             static_cast<uint8_t>(writes.size() >> 8), static_cast<uint8_t>(writes.size() & 0xFF),
             static_cast<uint8_t>(writes.size() * 2)};
  for (int v : writes) {
    p.push_back(static_cast<uint8_t>((v >> 8) & 0xFF));
    p.push_back(static_cast<uint8_t>(v & 0xFF));
  }
  return append_crc(p);
}

static const FieldSpec* spec(const char* key) {
  for (size_t i = 0; i < field_count(); ++i) {
    if (std::strcmp(field_at(i).key, key) == 0) return &field_at(i);
  }
  return nullptr;
}

static bool value_of(const char* key, const PassiveDecoder& d, Value& v) {
  const FieldSpec* f = spec(key);
  return f != nullptr && evaluate(*f, d, v);
}

// --- CRC and framing -------------------------------------------------------

static void test_crc() {
  CHECK(append_crc(hex("01 03 00 00 00 0A")) == hex("01 03 00 00 00 0A C5 CD"));
  CHECK(has_valid_crc(hex("01 03 00 00 00 0A C5 CD").data(), 8));
  Bytes bad = hex("01 03 00 00 00 0A C5 CC");
  CHECK(!has_valid_crc(bad.data(), bad.size()));
}

static void test_framing() {
  Bytes req = fc03_req(0x0A, 0xA7FB, 1);
  FrameParser p;
  p.feed(req.data(), 3);
  Bytes out;
  CHECK(!p.pop(out));
  p.feed(req.data() + 3, req.size() - 3);
  CHECK(p.pop(out) && out == req);

  FrameParser q;
  Bytes two = req;
  Bytes resp = read_resp(0x0A, 0x03, {33});
  two.insert(two.end(), resp.begin(), resp.end());
  q.feed(two.data(), two.size());
  CHECK(q.pop(out) && out == req);
  CHECK(q.pop(out) && out == resp);

  FrameParser r;
  Bytes garbage = {0x55, 0x33};
  garbage.insert(garbage.end(), req.begin(), req.end());
  r.feed(garbage.data(), garbage.size());
  CHECK(r.pop(out) && out == req);
  CHECK(r.resync_bytes > 0);

  FrameParser s;
  Bytes corrupted = req;
  corrupted.back() ^= 0xFF;
  s.feed(corrupted.data(), corrupted.size());
  CHECK(!s.pop(out));
}

static void test_fc17_short_response_is_not_stalled() {
  // Regression: a 9-byte FC17 response must not wait for the 11-byte request header.
  Bytes resp = read_resp(0x02, 0x17, {1, 2});
  Bytes req = fc17_req(0x0A, 0xB3B0, 3, 0xB3C4, {5, 21, 2});
  Bytes both = resp;
  both.insert(both.end(), req.begin(), req.end());
  FrameParser p;
  p.feed(both.data(), both.size());
  Bytes a, b;
  CHECK(p.pop(a) && a == resp);
  CHECK(p.pop(b) && b == req);
}

// --- Passive decoder and fields --------------------------------------------

static void test_decoder_fc04_and_rw_separation() {
  Engine e;
  // FC04 block 0x1E 0000..0001 and a commanded target at 0x1E 0001 written by the controller.
  Bytes fc04_req = append_crc(Bytes{SLAVE_OUTDOOR, FC_READ_INPUT, 0x00, 0x00, 0x00, 0x02});
  Bytes fc04_resp = read_resp(SLAVE_OUTDOOR, FC_READ_INPUT, {-20, 50});
  Bytes write = fc10_req(SLAVE_OUTDOOR, 0x0001, {1000});
  e.feed(fc04_req.data(), fc04_req.size(), 0, 0);
  e.feed(fc04_resp.data(), fc04_resp.size(), 0, 0);
  e.feed(write.data(), write.size(), 0, 0);
  Value v;
  CHECK(value_of("condenser_out", e.decoder, v) && v.num == 5.0f);
  CHECK(value_of("commanded_target_temperature", e.decoder, v) && v.num == 100.0f);
  CHECK(value_of("condenser_in", e.decoder, v) && v.num == -2.0f);
}

static void test_controller_block_and_sentinel() {
  Engine e;
  std::vector<int> vals(15, 0);
  vals[0] = 35;     // A7F8 supply
  vals[3] = -1000;  // A7FB sentinel: no value
  vals[5] = 1000;   // A7FD
  vals[10] = -3;    // A802 outdoor
  vals[11] = 232;   // A803
  Bytes req = fc17_req(SLAVE_CONTROLLER, 0xA7F8, 15, 0, {});
  Bytes resp = read_resp(SLAVE_CONTROLLER, FC_READ_WRITE, vals);
  e.feed(req.data(), req.size(), 0, 0);
  e.feed(resp.data(), resp.size(), 0, 0);
  Value v;
  CHECK(value_of("supply_temperature", e.decoder, v) && v.num == 35.0f);
  CHECK(!value_of("dhw_upper_temperature", e.decoder, v));
  CHECK(value_of("outdoor_temperature", e.decoder, v) && v.num == -3.0f);
  CHECK(value_of("sg_mode", e.decoder, v) && std::strcmp(v.text, "Peak (1-1)") == 0);
}

static void test_outdoor_state_and_active_flags() {
  Engine e;
  std::vector<int> block(0x16, 0);
  block[0x0B] = 60;
  block[0x0D] = 35;
  block[0x0E] = 1200;
  block[0x14] = 29;
  block[0x15] = 0x0221;
  Bytes req = fc03_req(SLAVE_OUTDOOR, 0x0000, 0x16);
  Bytes resp = read_resp(SLAVE_OUTDOOR, FC_READ_INPUT, block);
  Bytes req4 = append_crc(Bytes{SLAVE_OUTDOOR, FC_READ_INPUT, 0x00, 0x00, 0x00, 0x16});
  e.feed(req4.data(), req4.size(), 0, 0);
  e.feed(resp.data(), resp.size(), 0, 0);
  Value v;
  CHECK(value_of("compressor_frequency", e.decoder, v) && v.num == 60.0f);
  CHECK(value_of("compressor_current", e.decoder, v) && v.num == 3.5f);
  CHECK(value_of("outdoor_unit_state", e.decoder, v) && std::strcmp(v.text, "Water flow + fan + compressor") == 0);
  CHECK(value_of("operating_mode", e.decoder, v) && std::strcmp(v.text, "Heating") == 0);
  CHECK(value_of("compressor_running", e.decoder, v) && v.b);
  CHECK(value_of("heating_active", e.decoder, v) && !v.b);  // no controller commands yet
  Bytes cmd = fc10_req(SLAVE_OUTDOOR, 0x0007, {1, 1});
  e.feed(cmd.data(), cmd.size(), 0, 0);
  CHECK(value_of("heating_active", e.decoder, v) && v.b);
}

static void test_settings_block_and_room_exchange() {
  Engine e;
  Bytes block = fc10_req(SLAVE_DCM, 0x03E8, {27, 20, 45, 0, 0, 1, 17, 17, 0, 0, 0, 1});
  e.feed(block.data(), block.size(), 0, 0);
  Value v;
  CHECK(value_of("heating_curve", e.decoder, v) && v.num == 27.0f);
  CHECK(value_of("heating_max", e.decoder, v) && v.num == 45.0f);
  CHECK(value_of("high_power", e.decoder, v) && v.b);

  Bytes exch = fc17_req(SLAVE_ROOM, 0xB3B0, 3, 0xB3C4, {5, 21, 2});
  Bytes resp = read_resp(SLAVE_ROOM, FC_READ_WRITE, {215, 0, 0});
  e.feed(exch.data(), exch.size(), 0, 0);
  e.feed(resp.data(), resp.size(), 0, 0);
  CHECK(value_of("room_temperature", e.decoder, v) && v.num == 21.5f);
  CHECK(value_of("room_setpoint", e.decoder, v) && v.num == 21.0f);
  CHECK(value_of("room_bus_outdoor_temperature", e.decoder, v) && v.num == 5.0f);
  CHECK(value_of("dhw_topup_active", e.decoder, v) && v.b);
  CHECK(e.room.bus_setpoint == 21);
}

static void test_values_are_kept_without_expiry_and_age_is_reported() {
  Engine e;
  Bytes req = fc17_req(SLAVE_ROOM, 0xB3B0, 3, 0xB3C4, {5, 21, 2});
  Bytes resp = read_resp(SLAVE_ROOM, FC_READ_WRITE, {215, 0, 0});
  e.feed(req.data(), req.size(), 0, 0);
  e.feed(resp.data(), resp.size(), 0, 0);
  Value v;
  CHECK(value_of("room_temperature", e.decoder, v));
  uint32_t age_ms = 999;
  CHECK(e.decoder.oldest_reading_age_ms(5000, age_ms));
  CHECK(age_ms == 5000);
  int32_t raw = 0;
  CHECK(e.decoder.get(SLAVE_ROOM, Space::READ, 0xB3B0, raw, 0, 1000));
  CHECK(!e.decoder.get(SLAVE_ROOM, Space::READ, 0xB3B0, raw, 1001, 1000));
  const FieldSpec* room_temp = spec("room_temperature");
  CHECK(room_temp != nullptr);
  CHECK(evaluate(*room_temp, e.decoder, v, 0, 1000));
  CHECK(!evaluate(*room_temp, e.decoder, v, 1001, 1000));
}

// --- Emulation -------------------------------------------------------------

static void test_engine_does_not_reuse_expired_room_setpoint() {
  Engine e;
  e.max_register_age_ms = 500;
  Bytes room_poll = fc17_req(SLAVE_ROOM, 0xB3B0, 3, 0xB3C4, {5, 21, 2});
  e.feed(room_poll.data(), room_poll.size(), 0, 1000);
  CHECK(e.room.bus_setpoint == 21);

  // A later unrelated frame runs sync_bus again after the stored room values expired.
  Bytes unrelated = fc03_req(SLAVE_CONTROLLER, 0xA7FB, 1);
  e.feed(unrelated.data(), unrelated.size(), 1000000, 2000);
  CHECK(e.room.bus_setpoint == -1);
  CHECK(!e.room.topup_active);
}

static void test_room_poll_response_bytes() {
  RoomEmulator r;
  r.enabled = true;
  r.set_temperature(21.5f, 0);
  r.setpoint_request = 22;
  r.topup_pending = true;
  Bytes out;
  CHECK(r.on_poll(10, out));
  CHECK(out.size() == 11);
  CHECK(std::memcmp(out.data(), hex("0A 17 06 00 D7 00 16 00 01").data(), 9) == 0);
  CHECK(has_valid_crc(out.data(), out.size()));
  CHECK(is_room_response(out));
}

static void test_setpoint_retry_and_topup_one_shot() {
  RoomEmulator r;
  r.enabled = true;
  r.set_temperature(21.5f, 0);
  r.request_setpoint(22);
  int carried = 0;
  Bytes out;
  for (int i = 0; i < 8; ++i) {
    r.on_poll(1000 + i, out);
    if (out[5] == 0x00 && out[6] == 0x16) ++carried;
  }
  CHECK(carried == 5);      // exactly five transmissions, then stop retrying
  CHECK(out[5] == 0 && out[6] == 0);
  r.request_topup();
  r.on_poll(2000, out);
  CHECK(out[7] == 0 && out[8] == 1);
  r.on_poll(2001, out);
  CHECK(out[7] == 0 && out[8] == 0);
}

static void test_setpoint_confirmed_clears_request() {
  RoomEmulator r;
  r.enabled = true;
  r.set_temperature(21.5f, 0);
  r.request_setpoint(22);
  r.on_bus_setpoint(22);
  CHECK(r.setpoint_request == 0);
  Bytes out;
  r.on_poll(5, out);
  CHECK(out[5] == 0 && out[6] == 0);
}

static void test_strict_watchdog_after_boot_and_timeout() {
  RoomEmulator r;
  r.enabled = true;
  Bytes out;
  CHECK(r.status(0) == RoomStatus::WAITING);
  CHECK(!r.on_poll(0, out));  // no response without fresh data after boot
  r.set_temperature(21.0f, 0);
  CHECK(r.status(1000) == RoomStatus::ACTIVE);
  CHECK(r.on_poll(1000, out));
  CHECK(r.status(30u * 60u * 1000u + 1u) == RoomStatus::TIMEOUT);
  CHECK(!r.on_poll(30u * 60u * 1000u + 1u, out));
  r.set_temperature(20.0f, 2000000);
  CHECK(r.status(2000001) == RoomStatus::ACTIVE);
}

static void test_range_and_clamp() {
  RoomEmulator r;
  CHECK(!r.set_temperature(40.0f, 0));
  CHECK(!r.has_temp);
  CHECK(r.request_setpoint(45.0f) == 30);
  CHECK(r.request_setpoint(3.0f) == 10);
}

static void test_room_peer_detection_and_own_echo() {
  RoomEmulator r;
  r.enabled = true;
  r.set_temperature(21.0f, 0);
  Bytes out;
  r.on_poll(10000, out);
  r.on_bus_room_response(10100);  // own echo
  CHECK(r.status(10100) == RoomStatus::ACTIVE);
  r.on_bus_room_response(50000);  // not ours: external sensor
  CHECK(r.status(50000) == RoomStatus::BLOCKED);
  CHECK(!r.on_poll(50001, out));
}

static void test_ack_emulation_and_peer() {
  AckEmulator a;
  Bytes out;
  CHECK(!a.on_fc10(SLAVE_DCM, 0x03E8, 12, 1, out));  // disabled
  a.enabled = true;
  CHECK(a.on_fc10(SLAVE_DCM, 0x03E8, 12, 1, out));
  CHECK(out == hex("0F 10 03 E8 00 0C") || std::memcmp(out.data(), hex("0F 10 03 E8 00 0C").data(), 6) == 0);
  CHECK(has_valid_crc(out.data(), out.size()));
  // Own echo within 150 ms is not a peer. A foreign 8-byte FC10 ACK is.
  a.observe_frame(out, 100);
  CHECK(!a.peer);
  Bytes foreign = append_crc(Bytes{SLAVE_DCM, FC_WRITE_MULTIPLE, 0x03, 0xE8, 0x00, 0x0C});
  a.observe_frame(foreign, 10000);
  CHECK(a.status() == AckStatus::BLOCKED);
  CHECK(!a.on_fc10(SLAVE_DCM, 0x03E8, 12, 10001, out));
}

static void test_idle_0708_reply_matches_repo_bytes() {
  AckEmulator a;
  a.enabled = true;
  Bytes out;
  CHECK(a.on_fc03(SLAVE_DCM, 0x0708, 6, 1, out));
  CHECK(out == hex("0F 03 0C 00 00 00 00 00 00 00 00 00 00 00 06 9D 76"));
}

// --- TX timing and engine ----------------------------------------------------

static void test_tx_timeline() {
  TxScheduler t;
  Bytes frame = hex("0A 17 06 00 00 00 00 00 00 DE AD");
  CHECK(t.request(frame, 10000));
  CHECK(!t.request(frame, 10000));  // busy
  CHECK(t.tick(9999) == TxAction::NONE);
  CHECK(t.tick(10000) == TxAction::DE_ON);
  CHECK(t.tick(10100) == TxAction::NONE);
  CHECK(t.tick(10200) == TxAction::WRITE);
  t.on_written(10250);
  CHECK(t.tick(11400) == TxAction::NONE);
  CHECK(t.tick(11450) == TxAction::DE_OFF);
  CHECK(!t.busy());
}

static void test_engine_poll_to_transmit() {
  Engine e;
  e.room.enabled = true;
  e.room.set_temperature(21.5f, 0);
  Bytes poll = fc17_req(SLAVE_ROOM, 0xB3B0, 3, 0xB3C4, {5, 21, 2});
  CHECK(poll.size() == 19);
  e.feed(poll.data(), poll.size(), 1000000, 1000);
  CHECK(e.tx.busy());
  // Due at last byte + 5 ms silence + 3.8 ms pre-delay = 1008800 us.
  CHECK(e.tx.tick(1008799) == TxAction::NONE);
  CHECK(e.tx.tick(1008800) == TxAction::DE_ON);
  CHECK(e.tx.tick(1009000) == TxAction::WRITE);
  CHECK(is_room_response(e.tx.frame()));
  CHECK(has_valid_crc(e.tx.frame().data(), e.tx.frame().size()));
  e.tx.on_written(1009100);
  CHECK(e.tx.tick(1010300) == TxAction::DE_OFF);
}

static void test_engine_no_response_when_disabled() {
  Engine e;
  Bytes poll = fc17_req(SLAVE_ROOM, 0xB3B0, 3, 0xB3C4, {5, 21, 2});
  e.feed(poll.data(), poll.size(), 0, 0);
  CHECK(!e.tx.busy());
}

static void test_engine_ack_on_fc10_write() {
  Engine e;
  e.ack.enabled = true;
  Bytes write = fc10_req(SLAVE_DCM, 0x03E8, {27, 20});
  e.feed(write.data(), write.size(), 0, 0);
  CHECK(e.tx.busy());
  CHECK(e.tx.frame() == append_crc(Bytes{SLAVE_DCM, FC_WRITE_MULTIPLE, 0x03, 0xE8, 0x00, 0x02}));
}

static void test_engine_counts_dropped_tx_requests() {
  Engine e;
  e.ack.enabled = true;
  Bytes first = fc10_req(SLAVE_DCM, 0x03E8, {27, 20});
  Bytes second = fc10_req(SLAVE_DCM, 0x03EA, {45, 17});
  first.insert(first.end(), second.begin(), second.end());
  CHECK(e.feed(first.data(), first.size(), 1000000, 1000) == 2);
  CHECK(e.tx.busy());
  CHECK(e.tx_dropped == 1);
}

int main() {
  test_crc();
  test_framing();
  test_fc17_short_response_is_not_stalled();
  test_decoder_fc04_and_rw_separation();
  test_controller_block_and_sentinel();
  test_outdoor_state_and_active_flags();
  test_settings_block_and_room_exchange();
  test_values_are_kept_without_expiry_and_age_is_reported();
  test_engine_does_not_reuse_expired_room_setpoint();
  test_room_poll_response_bytes();
  test_setpoint_retry_and_topup_one_shot();
  test_setpoint_confirmed_clears_request();
  test_strict_watchdog_after_boot_and_timeout();
  test_range_and_clamp();
  test_room_peer_detection_and_own_echo();
  test_ack_emulation_and_peer();
  test_idle_0708_reply_matches_repo_bytes();
  test_tx_timeline();
  test_engine_poll_to_transmit();
  test_engine_no_response_when_disabled();
  test_engine_ack_on_fc10_write();
  test_engine_counts_dropped_tx_requests();
  std::printf("checks: %d, failures: %d\n", g_checks, g_failures);
  return g_failures == 0 ? 0 : 1;
}
