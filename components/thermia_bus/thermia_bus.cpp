#include "thermia_bus.h"

#include <algorithm>
#include <cmath>

#include "esphome/core/hal.h"
#include "esphome/core/log.h"

namespace esphome {
namespace thermia_bus {

static const char *const TAG = "thermia_bus";

// Diagnostic values that are not register fields. Negative refs encode them: ref = -(id + 1).
enum DiagId : int {
  DIAG_BUS_STATUS = 0,
  DIAG_FRAMES_OK,
  DIAG_RESYNC_BYTES,
  DIAG_UNMATCHED,
  DIAG_ROOM_STATUS,
  DIAG_ACK_STATUS,
  DIAG_ROOM_RESPONSES,
  DIAG_ACK_FRAMES,
};

int ThermiaBus::diag_id(const std::string &key) {
  if (key == "bus_status") return DIAG_BUS_STATUS;
  if (key == "frames_ok") return DIAG_FRAMES_OK;
  if (key == "resync_bytes") return DIAG_RESYNC_BYTES;
  if (key == "unmatched_responses") return DIAG_UNMATCHED;
  if (key == "room_emulation_status") return DIAG_ROOM_STATUS;
  if (key == "ack_emulation_status") return DIAG_ACK_STATUS;
  if (key == "room_responses_sent") return DIAG_ROOM_RESPONSES;
  if (key == "ack_frames_sent") return DIAG_ACK_FRAMES;
  return DIAG_NONE;
}

int ThermiaBus::field_index(const std::string &key) {
  const size_t n = thermia_core::field_count();
  for (size_t i = 0; i < n; ++i) {
    if (key == thermia_core::field_at(i).key) return static_cast<int>(i);
  }
  return -1;
}

void ThermiaBus::setup() {
  if (de_pin_ != nullptr) {
    // Drive DE low as early as possible. Before this line the pin is undefined, see docs/SAFETY.md.
    de_pin_->setup();
    de_pin_->pin_mode(gpio::FLAG_OUTPUT);
    de_pin_->digital_write(false);
  }
  // Repo defaults: room emulation OFF, 0x0F ACK ON. The ACK only sends once it sees writes to 0x0F.
  engine_.room.enabled = false;
  engine_.ack.enabled = true;
  heating_index_ = field_index("heating_active");
  cooling_index_ = field_index("cooling_active");
  last_rx_ms_ = millis();
  last_publish_ms_ = 0;
  ESP_LOGI(TAG, "Thermia bus ready: 9600 8E1, DE on GPIO (set via de_pin)");
}

void ThermiaBus::dump_config() {
  ESP_LOGCONFIG(TAG, "Thermia iTec Eco bus");
  ESP_LOGCONFIG(TAG, "  Sensors: %u, binary: %u, text: %u", static_cast<unsigned>(sensors_.size()),
                static_cast<unsigned>(binaries_.size()), static_cast<unsigned>(texts_.size()));
  this->check_uart_settings(9600, 1, uart::UART_CONFIG_PARITY_EVEN, 8);
}

void ThermiaBus::loop() {
  uint8_t buf[64];
  bool received = false;
  int available;
  while ((available = this->available()) > 0) {
    const size_t n = std::min<size_t>(static_cast<size_t>(available), sizeof(buf));
    this->read_array(buf, n);
    engine_.feed(buf, n, micros(), millis());
    received = true;
  }
  const uint32_t now = millis();
  if (received) {
    last_rx_ms_ = now;
  } else if (now - last_rx_ms_ > 200) {
    engine_.parser.flush();  // silence longer than any frame: drop a partial frame
    last_rx_ms_ = now;
  }
  handle_tx();
  if (received || now - last_publish_ms_ > 1000) {
    publish_all();
    last_publish_ms_ = now;
  }
}

void ThermiaBus::handle_tx() {
  // Hardware is driven here. The timing decisions live in thermia_core::TxScheduler.
  switch (engine_.tx.tick(micros())) {
    case thermia_core::TxAction::DE_ON:
      if (de_pin_ != nullptr) de_pin_->digital_write(true);
      break;
    case thermia_core::TxAction::WRITE: {
      const auto &frame = engine_.tx.frame();
      this->write_array(frame.data(), frame.size());
      this->flush();  // blocks until the frame has left the UART
      engine_.tx.on_written(micros());
      break;
    }
    case thermia_core::TxAction::DE_OFF:
      if (de_pin_ != nullptr) de_pin_->digital_write(false);
      break;
    case thermia_core::TxAction::NONE:
      break;
  }
}

void ThermiaBus::publish_all() {
  for (auto &slot : sensors_) publish_sensor(slot.ref, slot.sensor);
  for (auto &slot : binaries_) publish_binary(slot.index, slot.sensor);
  for (auto &slot : texts_) publish_text(slot.ref, slot.sensor);
  if (climate_ != nullptr) climate_->refresh();
}

void ThermiaBus::publish_sensor(int ref, sensor::Sensor *s) {
  if (ref < 0) {
    s->publish_state(diag_value(-ref - 1));
    return;
  }
  thermia_core::Value v;
  if (thermia_core::evaluate(thermia_core::field_at(static_cast<size_t>(ref)), engine_.decoder, v) &&
      v.type == thermia_core::Value::Type::NUM) {
    s->publish_state(v.num);
  } else {
    s->publish_state(NAN);
  }
}

void ThermiaBus::publish_binary(int index, binary_sensor::BinarySensor *s) {
  thermia_core::Value v;
  if (thermia_core::evaluate(thermia_core::field_at(static_cast<size_t>(index)), engine_.decoder, v) &&
      v.type == thermia_core::Value::Type::BOOL) {
    s->publish_state(v.b);
  } else {
    s->invalidate_state();
  }
}

void ThermiaBus::publish_text(int ref, text_sensor::TextSensor *s) {
  if (ref < 0) {
    s->publish_state(diag_text(-ref - 1));
    return;
  }
  thermia_core::Value v;
  if (thermia_core::evaluate(thermia_core::field_at(static_cast<size_t>(ref)), engine_.decoder, v) &&
      v.type == thermia_core::Value::Type::TEXT) {
    s->publish_state(v.text);
  } else {
    s->publish_state("UNKNOWN");
  }
}

float ThermiaBus::diag_value(int diag) {
  switch (diag) {
    case DIAG_FRAMES_OK: return static_cast<float>(engine_.parser.frames_ok);
    case DIAG_RESYNC_BYTES: return static_cast<float>(engine_.parser.resync_bytes);
    case DIAG_UNMATCHED: return static_cast<float>(engine_.decoder.unmatched_responses);
    case DIAG_ROOM_RESPONSES: return static_cast<float>(engine_.room.responses_sent);
    case DIAG_ACK_FRAMES:
      return static_cast<float>(engine_.ack.acks_sent + engine_.ack.idle_replies_sent);
    default: return NAN;
  }
}

std::string ThermiaBus::diag_text(int diag) {
  const uint32_t now = millis();
  switch (diag) {
    case DIAG_BUS_STATUS: return "PASSIVE_LISTENING";
    case DIAG_ROOM_STATUS: return thermia_core::room_status_name(engine_.room.status(now));
    case DIAG_ACK_STATUS:
      switch (engine_.ack.status()) {
        case thermia_core::AckStatus::DISABLED: return "DISABLED";
        case thermia_core::AckStatus::ACTIVE: return "ACTIVE";
        case thermia_core::AckStatus::BLOCKED: return "BLOCKED_BY_EXTERNAL_RESPONDER";
      }
      return "UNKNOWN";
    default: return "UNKNOWN";
  }
}

void ThermiaBus::register_sensor(const std::string &key, sensor::Sensor *s) {
  const int diag = diag_id(key);
  if (diag != DIAG_NONE) {
    sensors_.push_back({-(diag + 1), s});
    return;
  }
  sensors_.push_back({field_index(key), s});
}

void ThermiaBus::register_binary_sensor(const std::string &key, binary_sensor::BinarySensor *s) {
  binaries_.push_back({field_index(key), s});
}

void ThermiaBus::register_text_sensor(const std::string &key, text_sensor::TextSensor *s) {
  const int diag = diag_id(key);
  if (diag != DIAG_NONE) {
    texts_.push_back({-(diag + 1), s});
    return;
  }
  texts_.push_back({field_index(key), s});
}

void ThermiaBus::set_room_enabled(bool on) {
  if (on && engine_.room.peer) {
    ESP_LOGW(TAG, "Room emulation refused: external room sensor on the bus");
    return;
  }
  engine_.room.enabled = on;
  ESP_LOGI(TAG, "Room sensor emulation %s", on ? "ON" : "OFF");
}

void ThermiaBus::set_ack_enabled(bool on) {
  if (on && engine_.ack.peer) {
    ESP_LOGW(TAG, "0x0F ACK refused: external responder on the bus");
    return;
  }
  engine_.ack.enabled = on;
  ESP_LOGI(TAG, "0x0F ACK emulation %s", on ? "ON" : "OFF");
}

void ThermiaBus::room_set_temperature(float celsius) {
  if (!engine_.room.set_temperature(celsius, millis())) {
    engine_.room.clear_temperature();  // out of range: no response, like the repo
    ESP_LOGW(TAG, "Room temperature %.1f rejected (5..35 degC)", celsius);
  }
}

void ThermiaBus::room_request_setpoint(float celsius) { engine_.room.request_setpoint(celsius); }

void ThermiaBus::room_request_topup() { engine_.room.request_topup(); }

void ThermiaBus::set_watchdog_minutes(float minutes) {
  engine_.room.watchdog_ms = static_cast<uint32_t>(std::max(0.0f, minutes) * 60000.0f);
}

float ThermiaBus::room_temperature() const { return engine_.room.has_temp ? engine_.room.temp : NAN; }

float ThermiaBus::room_target() const { return static_cast<float>(engine_.room.target); }

bool ThermiaBus::heating_active() {
  thermia_core::Value v;
  return heating_index_ >= 0 &&
         thermia_core::evaluate(thermia_core::field_at(static_cast<size_t>(heating_index_)), engine_.decoder, v) &&
         v.b;
}

bool ThermiaBus::cooling_active() {
  thermia_core::Value v;
  return cooling_index_ >= 0 &&
         thermia_core::evaluate(thermia_core::field_at(static_cast<size_t>(cooling_index_)), engine_.decoder, v) &&
         v.b;
}

// --- Climate -----------------------------------------------------------------

climate::ClimateTraits ThermiaClimate::traits() {
  auto t = climate::ClimateTraits();
  t.set_supports_current_temperature(true);
  t.set_supported_modes({climate::CLIMATE_MODE_HEAT});
  t.set_visual_min_temperature(10.0f);
  t.set_visual_max_temperature(30.0f);
  t.set_visual_temperature_step(1.0f);
  return t;
}

void ThermiaClimate::refresh() {
  if (parent_ == nullptr) return;
  current_temperature = parent_->room_temperature();
  target_temperature = parent_->room_target();
  mode = climate::CLIMATE_MODE_HEAT;
  if (parent_->cooling_active()) {
    action = climate::CLIMATE_ACTION_COOLING;
  } else if (parent_->heating_active()) {
    action = climate::CLIMATE_ACTION_HEATING;
  } else {
    action = climate::CLIMATE_ACTION_IDLE;
  }
  publish_state();
}

void ThermiaClimate::control(const climate::ClimateCall &call) {
  if (parent_ == nullptr) return;
  if (call.get_target_temperature().has_value()) {
    parent_->set_room_setpoint_from_climate(*call.get_target_temperature());
  }
  refresh();
}

}  // namespace thermia_bus
}  // namespace esphome
