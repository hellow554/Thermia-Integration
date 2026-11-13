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
  DIAG_TX_DROPPED,
  DIAG_OLDEST_REGISTER_AGE,
  DIAG_REGISTER_DATA_STALE,
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
  if (key == "tx_dropped") return DIAG_TX_DROPPED;
  if (key == "oldest_register_age_seconds") return DIAG_OLDEST_REGISTER_AGE;
  if (key == "register_data_stale") return DIAG_REGISTER_DATA_STALE;
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
  // Emulation settings are declared in YAML. A room sensor is mandatory for 0x0A emulation.
  // The Python schema rejects an enabled configuration without a sensor; keep the runtime guard too.
  engine_.room.enabled = room_emulation_enabled_ && room_temperature_sensor_ != nullptr;
  engine_.ack.enabled = ack_emulation_enabled_;
  if (room_emulation_enabled_ && room_temperature_sensor_ == nullptr) {
    ESP_LOGE(TAG, "Room emulation requested without a temperature sensor; keeping it disabled");
  }
  if (engine_.room.enabled) {
    room_temperature_sensor_->add_on_state_callback([this](float value) { this->room_set_temperature(value); });
    if (room_temperature_sensor_->has_state()) {
      room_set_temperature(room_temperature_sensor_->get_state());
    }
  }
  heating_index_ = field_index("heating_active");
  cooling_index_ = field_index("cooling_active");
  last_rx_ms_ = millis();
  last_publish_ms_ = 0;
  ESP_LOGI(TAG, "Thermia bus ready: 9600 8E1, room emulation=%s, 0x0F ACK=%s, stale-after=%lu s",
           engine_.room.enabled ? "enabled" : "disabled", engine_.ack.enabled ? "enabled" : "disabled",
           static_cast<unsigned long>(register_stale_after_ms_ / 1000UL));
}

void ThermiaBus::dump_config() {
  ESP_LOGCONFIG(TAG, "Thermia iTec Eco bus");
  ESP_LOGCONFIG(TAG, "  Sensors: %u, binary: %u, text: %u", static_cast<unsigned>(sensors_.size()),
                static_cast<unsigned>(binaries_.size()), static_cast<unsigned>(texts_.size()));
  ESP_LOGCONFIG(TAG, "  Room emulation: %s", engine_.room.enabled ? "enabled" : "disabled");
  ESP_LOGCONFIG(TAG, "  0x0F ACK emulation: %s", ack_emulation_enabled_ ? "enabled" : "disabled");
  ESP_LOGCONFIG(TAG, "  Register stale after: %lu s", static_cast<unsigned long>(register_stale_after_ms_ / 1000UL));
  // UART settings (9600 8E1) are validated in the YAML schema; check_uart_settings() is deprecated.
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
  // Process frequently, but publish only actual value changes. The one-second refresh is
  // retained for age diagnostics and configured stale-value invalidation.
  if (received || now - last_publish_ms_ >= 1000) {
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
  for (auto &slot : sensors_) publish_sensor(slot);
  for (auto &slot : binaries_) publish_binary(slot);
  for (auto &slot : texts_) publish_text(slot);
  if (climate_ != nullptr) climate_->refresh();
}

void ThermiaBus::publish_sensor(SensorSlot &slot) {
  float value = NAN;
  if (slot.ref < 0) {
    value = diag_value(-slot.ref - 1);
  } else {
    thermia_core::Value v;
    if (thermia_core::evaluate(thermia_core::field_at(static_cast<size_t>(slot.ref)), engine_.decoder, v,
                               millis(), register_stale_after_ms_) &&
        v.type == thermia_core::Value::Type::NUM) {
      value = v.num;
    }
  }
  const bool equal = (std::isnan(value) && std::isnan(slot.last_value)) ||
                     (std::isfinite(value) && std::isfinite(slot.last_value) &&
                      std::fabs(value - slot.last_value) < 0.001f);
  if (!slot.has_published || !equal) {
    slot.sensor->publish_state(value);
    slot.last_value = value;
    slot.has_published = true;
  }
}

void ThermiaBus::publish_binary(BinarySlot &slot) {
  thermia_core::Value v;
  bool value = false;
  bool valid = false;
  if (slot.index < 0) {
    valid = diag_binary_value(-slot.index - 1, value);
  } else {
    valid = thermia_core::evaluate(thermia_core::field_at(static_cast<size_t>(slot.index)),
                                   engine_.decoder, v, millis(), register_stale_after_ms_) &&
            v.type == thermia_core::Value::Type::BOOL;
    value = valid && v.b;
  }
  if (!slot.has_published || valid != slot.last_valid || (valid && value != slot.last_value)) {
    if (valid) {
      slot.sensor->publish_state(value);
    } else {
      slot.sensor->invalidate_state();
    }
    slot.last_valid = valid;
    slot.last_value = value;
    slot.has_published = true;
  }
}

void ThermiaBus::publish_text(TextSlot &slot) {
  std::string value = "UNKNOWN";
  if (slot.ref < 0) {
    value = diag_text(-slot.ref - 1);
  } else {
    thermia_core::Value v;
    if (thermia_core::evaluate(thermia_core::field_at(static_cast<size_t>(slot.ref)), engine_.decoder, v,
                               millis(), register_stale_after_ms_) &&
        v.type == thermia_core::Value::Type::TEXT && v.text != nullptr) {
      value = v.text;
    }
  }
  if (!slot.has_published || value != slot.last_value) {
    slot.sensor->publish_state(value);
    slot.last_value = value;
    slot.has_published = true;
  }
}

bool ThermiaBus::diag_binary_value(int diag, bool &value) {
  if (diag != DIAG_REGISTER_DATA_STALE || register_stale_after_ms_ == 0) return false;
  uint32_t age_ms = 0;
  if (!engine_.decoder.oldest_reading_age_ms(millis(), age_ms)) {
    value = true;  // configured stale monitoring, but no register data has arrived yet
    return true;
  }
  value = age_ms > register_stale_after_ms_;
  return true;
}

float ThermiaBus::diag_value(int diag) {
  switch (diag) {
    case DIAG_FRAMES_OK: return static_cast<float>(engine_.parser.frames_ok);
    case DIAG_RESYNC_BYTES: return static_cast<float>(engine_.parser.resync_bytes);
    case DIAG_UNMATCHED: return static_cast<float>(engine_.decoder.unmatched_responses);
    case DIAG_ROOM_RESPONSES: return static_cast<float>(engine_.room.responses_sent);
    case DIAG_ACK_FRAMES:
      return static_cast<float>(engine_.ack.acks_sent + engine_.ack.idle_replies_sent);
    case DIAG_TX_DROPPED: return static_cast<float>(engine_.tx_dropped);
    case DIAG_OLDEST_REGISTER_AGE: {
      uint32_t age_ms = 0;
      if (engine_.decoder.oldest_reading_age_ms(millis(), age_ms)) return static_cast<float>(age_ms) / 1000.0f;
      return NAN;
    }
    default: return NAN;
  }
}

std::string ThermiaBus::diag_text(int diag) {
  const uint32_t now = millis();
  switch (diag) {
    case DIAG_BUS_STATUS: {
      uint32_t age_ms = 0;
      if (!engine_.decoder.oldest_reading_age_ms(now, age_ms)) return "WAITING_FOR_DATA";
      if (register_stale_after_ms_ > 0 && age_ms > register_stale_after_ms_) return "STALE";
      return "PASSIVE_LISTENING";
    }
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
  const int diag = diag_id(key);
  if (diag != DIAG_NONE) {
    binaries_.push_back({-(diag + 1), s});
    return;
  }
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

void ThermiaBus::room_set_temperature(float celsius) {
  if (!std::isfinite(celsius)) {
    engine_.room.clear_temperature();
    return;
  }
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

float ThermiaBus::room_temperature() const {
  return engine_.room.status(millis()) == thermia_core::RoomStatus::ACTIVE ? engine_.room.temp : NAN;
}

float ThermiaBus::room_target() const { return static_cast<float>(engine_.room.target); }

bool ThermiaBus::heating_active() {
  thermia_core::Value v;
  return heating_index_ >= 0 &&
         thermia_core::evaluate(thermia_core::field_at(static_cast<size_t>(heating_index_)), engine_.decoder, v,
                                millis(), register_stale_after_ms_) &&
         v.b;
}

bool ThermiaBus::cooling_active() {
  thermia_core::Value v;
  return cooling_index_ >= 0 &&
         thermia_core::evaluate(thermia_core::field_at(static_cast<size_t>(cooling_index_)), engine_.decoder, v,
                                millis(), register_stale_after_ms_) &&
         v.b;
}

// --- Climate -----------------------------------------------------------------

climate::ClimateTraits ThermiaClimate::traits() {
  auto t = climate::ClimateTraits();
  // ESPHome 2026.5+ uses feature flags instead of boolean setters.
  t.add_feature_flags(climate::CLIMATE_SUPPORTS_CURRENT_TEMPERATURE | climate::CLIMATE_SUPPORTS_ACTION);
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
  const bool current_changed = (std::isnan(current_temperature) && !std::isnan(last_current_temperature_)) ||
                               (!std::isnan(current_temperature) &&
                                (std::isnan(last_current_temperature_) ||
                                 std::fabs(current_temperature - last_current_temperature_) >= 0.001f));
  const bool target_changed = (std::isnan(target_temperature) && !std::isnan(last_target_temperature_)) ||
                              (!std::isnan(target_temperature) &&
                               (std::isnan(last_target_temperature_) ||
                                std::fabs(target_temperature - last_target_temperature_) >= 0.001f));
  if (!has_published_state_ || current_changed || target_changed || action != last_action_ || mode != last_mode_) {
    publish_state();
    last_current_temperature_ = current_temperature;
    last_target_temperature_ = target_temperature;
    last_action_ = action;
    last_mode_ = mode;
    has_published_state_ = true;
  }
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
