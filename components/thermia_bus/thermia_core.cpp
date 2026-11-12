#include "thermia_core.h"

#include <cmath>

namespace thermia_core {
namespace {

constexpr size_t MAX_BUFFER = 512;

void put_be16(Bytes& out, uint16_t value) {
  out.push_back(static_cast<uint8_t>(value >> 8));
  out.push_back(static_cast<uint8_t>(value & 0xFF));
}

uint16_t get_be16(const uint8_t* p) {
  return static_cast<uint16_t>((p[0] << 8) | p[1]);
}

uint32_t register_key(uint8_t slave, Space space, uint16_t addr) {
  return (static_cast<uint32_t>(slave) << 24) | (static_cast<uint32_t>(static_cast<char>(space)) << 16) | addr;
}

uint16_t pending_key(uint8_t slave, uint8_t fc) {
  return static_cast<uint16_t>((slave << 8) | fc);
}

struct Candidates {
  bool need_more = false;
  int n = 0;
  size_t len[2] = {0, 0};
};

// Possible lengths of the frame starting at b[0]. Requests and responses are both listed,
// because passive capture cannot tell the direction. The CRC decides.
Candidates candidates(const Bytes& b) {
  Candidates c;
  if (b.size() < 2) {
    c.need_more = true;
    return c;
  }
  const uint8_t fc = b[1];
  if (fc & 0x80) {
    c.n = 1;
    c.len[0] = 5;
    return c;
  }
  if (fc == FC_READ_HOLDING || fc == FC_READ_INPUT) {
    if (b.size() < 3) {
      c.need_more = true;
      return c;
    }
    c.n = 2;
    c.len[0] = 8;
    c.len[1] = 5u + b[2];
    return c;
  }
  if (fc == FC_WRITE_MULTIPLE) {
    if (b.size() < 7) {
      c.need_more = true;
      return c;
    }
    c.n = 2;
    c.len[0] = 8;
    c.len[1] = 9u + b[6];
    return c;
  }
  if (fc == FC_READ_WRITE) {
    if (b.size() < 3) {
      c.need_more = true;
      return c;
    }
    if (b.size() < 11) {
      c.n = 1;
      c.len[0] = 5u + b[2];
      return c;
    }
    c.n = 2;
    c.len[0] = 5u + b[2];
    c.len[1] = 13u + b[10];
    return c;
  }
  return c;  // unknown function code: n == 0, the caller resyncs
}

bool raw_value(const PassiveDecoder& d, uint8_t slave, Space space, uint16_t addr, int32_t& raw) {
  return d.get(slave, space, addr, raw);
}

bool num_in_range(float value, float lo, float hi) {
  return value >= lo && value <= hi;
}

bool outdoor_read(const PassiveDecoder& d, uint16_t addr, float div, bool unsigned_, float lo, float hi,
                  float& out) {
  int32_t raw;
  if (!raw_value(d, SLAVE_OUTDOOR, Space::READ, addr, raw)) return false;
  if (unsigned_) raw &= 0xFFFF;
  const float v = static_cast<float>(raw) / div;
  if (!num_in_range(v, lo, hi)) return false;
  out = v;
  return true;
}

bool flags_read(const PassiveDecoder& d, uint32_t& flags) {
  int32_t raw;
  if (!raw_value(d, SLAVE_OUTDOOR, Space::READ, 0x0015, raw)) return false;
  flags = static_cast<uint32_t>(raw) & 0xFFFF;
  return true;
}

bool truthy(const PassiveDecoder& d, uint8_t slave, Space space, uint16_t addr) {
  int32_t raw;
  return raw_value(d, slave, space, addr, raw) && raw != 0;
}

bool evaluate_derived(Derived which, const PassiveDecoder& d, Value& out) {
  switch (which) {
    case Derived::CONDENSER_DELTA: {
      float cin, cout;
      if (!outdoor_read(d, 0x0000, 10.0f, false, -50.0f, 150.0f, cin)) return false;
      if (!outdoor_read(d, 0x0001, 10.0f, false, -50.0f, 150.0f, cout)) return false;
      out.type = Value::Type::NUM;
      out.num = std::round((cout - cin) * 100.0f) / 100.0f;
      return true;
    }
    case Derived::COMPRESSOR_STARTING: {
      float freq, current;
      if (!outdoor_read(d, 0x000B, 1.0f, true, 0.0f, 200.0f, freq)) return false;
      if (!outdoor_read(d, 0x000D, 10.0f, true, 0.0f, 100.0f, current)) return false;
      out.type = Value::Type::BOOL;
      out.b = freq > 0.0f && current < 0.2f;
      return true;
    }
    case Derived::OPERATING_MODE: {
      uint32_t flags;
      if (!flags_read(d, flags)) return false;
      out.type = Value::Type::TEXT;
      if (flags & 0x0080) out.text = "Cooling";
      else if (flags & 0x0040) out.text = "DHW / high temperature";
      else if (flags & 0x0020) out.text = "Heating";
      else out.text = "Unknown";
      return true;
    }
    case Derived::HEATING_ACTIVE:
    case Derived::DHW_ACTIVE:
    case Derived::COOLING_ACTIVE: {
      uint32_t flags;
      if (!flags_read(d, flags)) return false;
      const uint32_t mask = which == Derived::HEATING_ACTIVE ? 0x0020
                            : which == Derived::DHW_ACTIVE   ? 0x0040
                                                             : 0x0080;
      const bool context = (flags & mask) != 0;
      int32_t state;
      const bool running = raw_value(d, SLAVE_OUTDOOR, Space::READ, 0x0014, state) && (state & 0x01);
      out.type = Value::Type::BOOL;
      out.b = context && running &&
              truthy(d, SLAVE_OUTDOOR, Space::WRITE, 0x0007) &&
              truthy(d, SLAVE_OUTDOOR, Space::WRITE, 0x0008);
      return true;
    }
    case Derived::SG_MODE: {
      int32_t a, b;
      if (!raw_value(d, SLAVE_CONTROLLER, Space::READ, 0xA7FD, a)) return false;
      if (!raw_value(d, SLAVE_CONTROLLER, Space::READ, 0xA803, b)) return false;
      out.type = Value::Type::TEXT;
      if (a == -1000 && b == 224) out.text = "Normal (0-0)";
      else if (a == -1000 && b == 232) out.text = "Blocked (1-0)";
      else if (a == 1000 && b == 224) out.text = "Enhanced (0-1)";
      else if (a == 1000 && b == 232) out.text = "Peak (1-1)";
      else return false;  // transitional state: no value, like the repo's entity without state
      return true;
    }
    case Derived::CONTROLLER_CONTEXT: {
      int32_t a80c;
      if (!raw_value(d, SLAVE_CONTROLLER, Space::WRITE, 0xA80C, a80c)) return false;
      const bool active = (a80c & 0x0040) != 0;
      const bool valve = (a80c & 0x0001) != 0;
      out.type = Value::Type::TEXT;
      if (active && valve) out.text = "Active / DHW valve";
      else if (active) out.text = "Active / non-DHW";
      else if (valve) out.text = "DHW valve / controller inactive";
      else out.text = "Controller inactive";
      return true;
    }
    case Derived::NONE:
      break;
  }
  return false;
}

}  // namespace

// --- CRC and framing -------------------------------------------------------

uint16_t crc16(const uint8_t* data, size_t len) {
  uint16_t crc = 0xFFFF;
  for (size_t i = 0; i < len; ++i) {
    crc = static_cast<uint16_t>(crc ^ data[i]);
    for (int bit = 0; bit < 8; ++bit) {
      if (crc & 0x0001) {
        crc = static_cast<uint16_t>((crc >> 1) ^ 0xA001);
      } else {
        crc = static_cast<uint16_t>(crc >> 1);
      }
    }
  }
  return crc;
}

bool has_valid_crc(const uint8_t* data, size_t len) {
  if (len < 4) return false;
  const uint16_t received = static_cast<uint16_t>(data[len - 2] | (data[len - 1] << 8));
  return crc16(data, len - 2) == received;
}

Bytes append_crc(const Bytes& payload) {
  const uint16_t crc = crc16(payload.data(), payload.size());
  Bytes out = payload;
  out.push_back(static_cast<uint8_t>(crc & 0xFF));
  out.push_back(static_cast<uint8_t>(crc >> 8));
  return out;
}

void FrameParser::feed(const uint8_t* data, size_t len) {
  buf_.insert(buf_.end(), data, data + len);
  while (!buf_.empty()) {
    const Candidates c = candidates(buf_);
    if (c.need_more) break;
    bool found = false;
    for (int i = 0; i < c.n; ++i) {
      const size_t length = c.len[i];
      if (buf_.size() >= length && has_valid_crc(buf_.data(), length)) {
        frames_.emplace_back(buf_.begin(), buf_.begin() + static_cast<std::ptrdiff_t>(length));
        buf_.erase(buf_.begin(), buf_.begin() + static_cast<std::ptrdiff_t>(length));
        ++frames_ok;
        found = true;
        break;
      }
    }
    if (found) continue;
    bool all_available = true;
    for (int i = 0; i < c.n; ++i) {
      if (buf_.size() < c.len[i]) all_available = false;
    }
    if (all_available) {
      buf_.erase(buf_.begin());
      ++resync_bytes;
    } else {
      break;  // a longer candidate may still complete
    }
  }
  if (buf_.size() > MAX_BUFFER) {
    const size_t drop = buf_.size() - MAX_BUFFER;
    buf_.erase(buf_.begin(), buf_.begin() + static_cast<std::ptrdiff_t>(drop));
    resync_bytes += static_cast<uint32_t>(drop);
  }
}

bool FrameParser::pop(Bytes& out) {
  if (frames_.empty()) return false;
  out = std::move(frames_.front());
  frames_.pop_front();
  return true;
}

void FrameParser::flush() {
  if (!buf_.empty()) {
    resync_bytes += static_cast<uint32_t>(buf_.size());
    buf_.clear();
  }
}

// --- Passive decoder -------------------------------------------------------

void PassiveDecoder::handle(const Bytes& f, uint32_t now_ms) {
  if (f.size() < 2) return;
  const uint8_t slave = f[0];
  const uint8_t fc = f[1];
  if (fc & 0x80) {
    pending_.erase(pending_key(slave, static_cast<uint8_t>(fc & 0x7F)));
    return;
  }
  if (fc == FC_READ_HOLDING || fc == FC_READ_INPUT) {
    if (f.size() == 8) {
      pending_[pending_key(slave, fc)] = std::make_pair(get_be16(&f[2]), get_be16(&f[4]));
      return;
    }
    if (f.size() == 5u + f[2]) read_response(slave, fc, f, now_ms);
    return;
  }
  if (fc == FC_WRITE_MULTIPLE) {
    if (f.size() >= 9 && f.size() == 9u + f[6]) {
      const uint16_t start = get_be16(&f[2]);
      const uint16_t count = get_be16(&f[4]);
      if (f[6] == count * 2) store(slave, Space::WRITE, start, &f[7], f[6], now_ms);
    }
    return;
  }
  if (fc == FC_READ_WRITE) {
    if (f.size() >= 11 && f.size() == 13u + f[10]) {  // request: read part + write part
      const uint16_t rstart = get_be16(&f[2]);
      const uint16_t rcount = get_be16(&f[4]);
      const uint16_t wstart = get_be16(&f[6]);
      const uint16_t wcount = get_be16(&f[8]);
      const uint8_t bc = f[10];
      if (bc == wcount * 2) store(slave, Space::WRITE, wstart, &f[11], bc, now_ms);
      pending_[pending_key(slave, fc)] = std::make_pair(rstart, rcount);
    } else if (f.size() == 5u + f[2]) {  // response
      read_response(slave, fc, f, now_ms);
    }
  }
}

void PassiveDecoder::read_response(uint8_t slave, uint8_t fc, const Bytes& f, uint32_t now_ms) {
  const auto it = pending_.find(pending_key(slave, fc));
  if (it == pending_.end()) {
    ++unmatched_responses;
    return;
  }
  const auto pending = it->second;
  pending_.erase(it);
  const uint8_t byte_count = f[2];
  if (byte_count != pending.second * 2) {
    ++unmatched_responses;
    return;
  }
  store(slave, Space::READ, pending.first, &f[3], byte_count, now_ms);
}

void PassiveDecoder::store(uint8_t slave, Space space, uint16_t start, const uint8_t* data, size_t len,
                           uint32_t now_ms) {
  for (size_t i = 0; i + 1 < len; i += 2) {
    const int16_t value = static_cast<int16_t>(get_be16(data + i));
    registers_[register_key(slave, space, static_cast<uint16_t>(start + i / 2))] = Reading{value, now_ms};
  }
}

bool PassiveDecoder::get(uint8_t slave, Space space, uint16_t addr, int32_t& out) const {
  const auto it = registers_.find(register_key(slave, space, addr));
  if (it == registers_.end()) return false;
  out = it->second.value;
  return true;
}

bool evaluate(const FieldSpec& f, const PassiveDecoder& d, Value& out) {
  out = Value{};
  int32_t raw = 0;
  switch (f.kind) {
    case Kind::NUM: {
      if (!d.get(f.slave, f.space, f.addr, raw)) return false;
      if (f.has_sentinel && raw == f.sentinel) return false;
      if (f.is_unsigned) raw &= 0xFFFF;
      const float v = static_cast<float>(raw) / f.div;
      if (f.has_valid && !num_in_range(v, f.vmin, f.vmax)) return false;
      out.type = Value::Type::NUM;
      out.num = v;
      return true;
    }
    case Kind::BIT:
      if (!d.get(f.slave, f.space, f.addr, raw)) return false;
      out.type = Value::Type::BOOL;
      out.b = (raw & f.mask) != 0;
      return true;
    case Kind::NONZERO:
      if (!d.get(f.slave, f.space, f.addr, raw)) return false;
      out.type = Value::Type::BOOL;
      out.b = raw != 0;
      return true;
    case Kind::SWITCH:
      if (!d.get(f.slave, f.space, f.addr, raw)) return false;
      if (raw != 0 && raw != 1) return false;
      out.type = Value::Type::BOOL;
      out.b = raw == 1;
      return true;
    case Kind::EQ:
      if (!d.get(f.slave, f.space, f.addr, raw)) return false;
      out.type = Value::Type::BOOL;
      out.b = raw == f.eq;
      return true;
    case Kind::ENUM: {
      if (!d.get(f.slave, f.space, f.addr, raw)) return false;
      const int32_t key = raw & 0xFFFF;
      out.type = Value::Type::TEXT;
      out.text = f.enum_default;
      for (uint8_t i = 0; i < f.enum_count; ++i) {
        if (f.enums[i].raw == key) {
          out.text = f.enums[i].text;
          break;
        }
      }
      return true;
    }
    case Kind::DERIVED:
      return evaluate_derived(f.derived, d, out);
  }
  return false;
}

// --- Frame recognition -----------------------------------------------------

bool is_room_poll(const Bytes& f) {
  if (f.size() != 19 || f[0] != SLAVE_ROOM || f[1] != 0x17) return false;
  return get_be16(&f[2]) == 0xB3B0 && get_be16(&f[4]) == 3 && get_be16(&f[6]) == 0xB3C4 &&
         get_be16(&f[8]) == 3;
}

bool is_room_response(const Bytes& f) {
  return f.size() == 11 && f[0] == SLAVE_ROOM && f[1] == 0x17 && f[2] == 0x06;
}

bool parse_fc10_request(const Bytes& f, uint16_t& start, uint16_t& count) {
  if (f.size() < 9 || f[1] != FC_WRITE_MULTIPLE || f.size() != 9u + f[6]) return false;
  start = get_be16(&f[2]);
  count = get_be16(&f[4]);
  return f[6] == count * 2;
}

bool parse_fc03_request(const Bytes& f, uint16_t& start, uint16_t& count) {
  if (f.size() != 8 || f[1] != FC_READ_HOLDING) return false;
  start = get_be16(&f[2]);
  count = get_be16(&f[4]);
  return true;
}

// --- Room sensor emulation -------------------------------------------------

const char* room_status_name(RoomStatus status) {
  switch (status) {
    case RoomStatus::DISABLED: return "DISABLED";
    case RoomStatus::WAITING: return "WAITING";
    case RoomStatus::ACTIVE: return "ACTIVE";
    case RoomStatus::TIMEOUT: return "TIMEOUT";
    case RoomStatus::BLOCKED: return "BLOCKED_BY_EXTERNAL_SENSOR";
  }
  return "UNKNOWN";
}

RoomStatus RoomEmulator::status(uint32_t now_ms) const {
  if (peer) return RoomStatus::BLOCKED;
  if (!enabled) return RoomStatus::DISABLED;
  if (!has_temp) return RoomStatus::WAITING;
  if (watchdog_ms > 0 && static_cast<uint32_t>(now_ms - temp_ms) > watchdog_ms) return RoomStatus::TIMEOUT;
  return RoomStatus::ACTIVE;
}

bool RoomEmulator::set_temperature(float value, uint32_t now_ms) {
  if (!(value >= 5.0f && value <= 35.0f)) return false;
  has_temp = true;
  temp = value;
  temp_ms = now_ms;
  return true;
}

void RoomEmulator::clear_temperature() {
  has_temp = false;
  temp = 0.0f;
  temp_ms = 0;
}

int RoomEmulator::request_setpoint(float value) {
  int t = static_cast<int>(std::lround(value));
  if (t < 10) t = 10;
  if (t > 30) t = 30;
  target = t;
  setpoint_request = (bus_setpoint == t) ? 0 : t;
  setpoint_retries = 0;
  return t;
}

void RoomEmulator::request_topup() { topup_pending = true; }

bool RoomEmulator::on_poll(uint32_t now_ms, Bytes& out) {
  if (status(now_ms) != RoomStatus::ACTIVE) return false;
  int req = 0;
  if (setpoint_request > 0) {
    req = setpoint_request;
    ++setpoint_retries;
    if (setpoint_retries > MAX_SETPOINT_RETRIES) {  // repo: not acknowledged after 5 cycles
      setpoint_request = 0;
      setpoint_retries = 0;
    }
  }
  int topup = 0;
  if (topup_pending) {  // one-shot
    topup = 1;
    topup_pending = false;
  }
  const int raw = static_cast<int>(std::lround(temp * 10.0f));
  Bytes payload = {SLAVE_ROOM, 0x17, 0x06};
  put_be16(payload, static_cast<uint16_t>(static_cast<int16_t>(raw)));
  put_be16(payload, static_cast<uint16_t>(static_cast<int16_t>(req)));
  put_be16(payload, static_cast<uint16_t>(static_cast<int16_t>(topup)));
  out = append_crc(payload);
  has_last_tx = true;
  last_tx_ms = now_ms;
  ++responses_sent;
  return true;
}

void RoomEmulator::on_bus_room_response(uint32_t now_ms) {
  if (!has_last_tx || static_cast<uint32_t>(now_ms - last_tx_ms) > ROOM_OWN_WINDOW_MS) peer = true;
}

void RoomEmulator::on_bus_setpoint(int value) {
  bus_setpoint = value;
  if (setpoint_request > 0) {
    if (value == setpoint_request) {
      setpoint_request = 0;
      setpoint_retries = 0;
    }
  } else if (value >= 10 && value <= 30) {
    target = value;  // panel dial changed: follow the controller
  }
}

void RoomEmulator::on_bus_topup(int value) { topup_active = value == 2; }

// --- 0x0F ACK emulation ----------------------------------------------------

AckStatus AckEmulator::status() const {
  if (peer) return AckStatus::BLOCKED;
  return enabled ? AckStatus::ACTIVE : AckStatus::DISABLED;
}

void AckEmulator::observe_frame(const Bytes& f, uint32_t now_ms) {
  if (f.size() < 2 || f[0] != SLAVE_DCM || peer) return;
  if (has_last_tx && static_cast<uint32_t>(now_ms - last_tx_ms) < ACK_OWN_WINDOW_MS) return;
  const bool fc10_ack = f[1] == FC_WRITE_MULTIPLE && f.size() == 8;
  const bool fc03_reply = f[1] == FC_READ_HOLDING && f.size() != 8;
  if (fc10_ack || fc03_reply) peer = true;
}

bool AckEmulator::on_fc10(uint8_t slave, uint16_t start, uint16_t count, uint32_t now_ms, Bytes& out) {
  if (slave != SLAVE_DCM || status() != AckStatus::ACTIVE) return false;
  Bytes payload = {SLAVE_DCM, FC_WRITE_MULTIPLE};
  put_be16(payload, start);
  put_be16(payload, count);
  out = append_crc(payload);
  has_last_tx = true;
  last_tx_ms = now_ms;
  ++acks_sent;
  return true;
}

bool AckEmulator::on_fc03(uint8_t slave, uint16_t start, uint16_t count, uint32_t now_ms, Bytes& out) {
  if (slave != SLAVE_DCM || start != 0x0708 || count != 6 || status() != AckStatus::ACTIVE) return false;
  // Idle reply to FC03 0x0708 x6: 12 data bytes, all zero except the last (0x06), as captured in the repo.
  Bytes payload = {SLAVE_DCM, FC_READ_HOLDING, 0x0C};
  for (int i = 0; i < 11; ++i) payload.push_back(0x00);
  payload.push_back(0x06);
  out = append_crc(payload);
  has_last_tx = true;
  last_tx_ms = now_ms;
  ++idle_replies_sent;
  return true;
}

// --- TX timing ---------------------------------------------------------------

bool TxScheduler::request(const Bytes& frame, uint32_t due_us) {
  if (busy()) return false;
  frame_ = frame;
  due_ = due_us;
  state_ = State::WAIT;
  return true;
}

TxAction TxScheduler::tick(uint32_t now_us) {
  switch (state_) {
    case State::WAIT:
      if (static_cast<int32_t>(now_us - due_) >= 0) {
        state_ = State::SETTLE;
        t_ = now_us;
        return TxAction::DE_ON;
      }
      break;
    case State::SETTLE:
      if (now_us - t_ >= TX_DE_SETTLE_US) {
        state_ = State::WRITE_PENDING;
        return TxAction::WRITE;
      }
      break;
    case State::HOLD:
      if (now_us - t_ >= TX_HOLD_US) {
        state_ = State::IDLE;
        return TxAction::DE_OFF;
      }
      break;
    case State::IDLE:
    case State::WRITE_PENDING:
      break;
  }
  return TxAction::NONE;
}

void TxScheduler::on_written(uint32_t now_us) {
  if (state_ == State::WRITE_PENDING) {
    state_ = State::HOLD;
    t_ = now_us;
  }
}

// --- Engine ----------------------------------------------------------------

size_t Engine::feed(const uint8_t* data, size_t len, uint32_t now_us, uint32_t now_ms) {
  parser.feed(data, len);
  size_t handled = 0;
  Bytes frame;
  while (parser.pop(frame)) {
    ++handled;
    handle(frame, now_us, now_ms);
  }
  sync_bus();
  return handled;
}

void Engine::handle(const Bytes& frame, uint32_t now_us, uint32_t now_ms) {
  decoder.handle(frame, now_ms);
  ack.observe_frame(frame, now_ms);
  if (is_room_response(frame)) room.on_bus_room_response(now_ms);
  if (is_room_poll(frame)) {
    Bytes out;
    if (room.on_poll(now_ms, out)) schedule(out, ROOM_TX_PRE_US, now_us);
    return;
  }
  uint16_t start = 0;
  uint16_t count = 0;
  if (parse_fc10_request(frame, start, count)) {
    Bytes out;
    if (ack.on_fc10(SLAVE_DCM, start, count, now_ms, out)) schedule(out, ACK_TX_PRE_US, now_us);
  } else if (parse_fc03_request(frame, start, count)) {
    Bytes out;
    if (ack.on_fc03(SLAVE_DCM, start, count, now_ms, out)) schedule(out, ACK_TX_PRE_US, now_us);
  }
}

void Engine::schedule(const Bytes& frame, uint32_t pre_us, uint32_t now_us) {
  if (!tx.request(frame, now_us + TX_SILENCE_US + pre_us)) ++tx_dropped;
}

void Engine::sync_bus() {
  int32_t value = 0;
  if (decoder.get(SLAVE_ROOM, Space::WRITE, 0xB3C5, value)) room.on_bus_setpoint(value);
  if (decoder.get(SLAVE_ROOM, Space::WRITE, 0xB3C6, value)) room.on_bus_topup(value);
}

}  // namespace thermia_core
