// ESPHome glue for the Thermia iTec Eco bus. All protocol logic lives in thermia_core.
#pragma once

#include <string>
#include <vector>

#include "esphome/components/binary_sensor/binary_sensor.h"
#include "esphome/components/climate/climate.h"
#include "esphome/components/sensor/sensor.h"
#include "esphome/components/text_sensor/text_sensor.h"
#include "esphome/components/uart/uart.h"
#include "esphome/core/component.h"
#include "esphome/core/gpio.h"

#include "thermia_core.h"

namespace esphome {
namespace thermia_bus {

class ThermiaBus;

class ThermiaClimate : public climate::Climate, public Component {
 public:
  void set_parent(ThermiaBus *parent) { parent_ = parent; }
  void refresh();
  climate::ClimateTraits traits() override;
  void control(const climate::ClimateCall &call) override;

 protected:
  ThermiaBus *parent_{nullptr};
  bool has_published_state_{false};
  float last_current_temperature_{0.0f};
  float last_target_temperature_{0.0f};
  climate::ClimateAction last_action_{climate::CLIMATE_ACTION_IDLE};
  climate::ClimateMode last_mode_{climate::CLIMATE_MODE_HEAT};
};

class ThermiaBus : public Component, public uart::UARTDevice {
 public:
  void setup() override;
  void loop() override;
  void dump_config() override;
  float get_setup_priority() const override { return setup_priority::HARDWARE; }

  void set_de_pin(GPIOPin *pin) { de_pin_ = pin; }
  void set_room_temperature_sensor(sensor::Sensor *sensor) { room_temperature_sensor_ = sensor; }
  void set_room_emulation_enabled(bool enabled) { room_emulation_enabled_ = enabled; }
  void set_ack_emulation_enabled(bool enabled) { ack_emulation_enabled_ = enabled; }
  void set_register_stale_after_seconds(uint32_t seconds) {
    register_stale_after_ms_ = seconds * 1000UL;
    engine_.max_register_age_ms = register_stale_after_ms_;
  }
  void register_sensor(const std::string &key, sensor::Sensor *s);
  void register_binary_sensor(const std::string &key, binary_sensor::BinarySensor *s);
  void register_text_sensor(const std::string &key, text_sensor::TextSensor *s);
  void register_climate(ThermiaClimate *c) { climate_ = c; }

  // Called from YAML (button, sensors, number).
  void room_set_temperature(float celsius);
  void room_request_setpoint(float celsius);
  void room_request_topup();
  void set_watchdog_minutes(float minutes);

  // Used by the climate entity.
  float room_temperature() const;
  float room_target() const;
  bool heating_active();
  bool cooling_active();
  void set_room_setpoint_from_climate(float celsius) { room_request_setpoint(celsius); }

 protected:
  struct SensorSlot;
  struct BinarySlot;
  struct TextSlot;
  static constexpr int DIAG_NONE = -1;
  static int diag_id(const std::string &key);
  static int field_index(const std::string &key);

  void handle_tx();
  void publish_all();
  void publish_sensor(SensorSlot &slot);
  void publish_binary(BinarySlot &slot);
  void publish_text(TextSlot &slot);
  float diag_value(int diag);
  bool diag_binary_value(int diag, bool &value);
  std::string diag_text(int diag);

  thermia_core::Engine engine_;
  GPIOPin *de_pin_{nullptr};
  sensor::Sensor *room_temperature_sensor_{nullptr};
  ThermiaClimate *climate_{nullptr};
  bool room_emulation_enabled_{false};
  bool ack_emulation_enabled_{false};
  uint32_t register_stale_after_ms_{0};
  uint32_t last_rx_ms_{0};
  uint32_t last_publish_ms_{0};
  int heating_index_{-1};
  int cooling_index_{-1};

  struct SensorSlot {
    int ref;
    sensor::Sensor *sensor;
    float last_value{0.0f};
    bool has_published{false};
  };
  struct BinarySlot {
    int index;
    binary_sensor::BinarySensor *sensor;
    bool last_value{false};
    bool last_valid{false};
    bool has_published{false};
  };
  struct TextSlot {
    int ref;
    text_sensor::TextSensor *sensor;
    std::string last_value;
    bool has_published{false};
  };
  std::vector<SensorSlot> sensors_;
  std::vector<BinarySlot> binaries_;
  std::vector<TextSlot> texts_;
};

}  // namespace thermia_bus
}  // namespace esphome
