#pragma once

// Primary target: classic Arduino Nano / ATmega328P (not Nano Every/ESP32).
// Select the matching board in Arduino IDE. Uno and Mega2560 are alternatives.
// NO REAL MOTION until the engineer has verified every setting below.
#ifndef OPA_HARDWARE_CONFIGURED
#define OPA_HARDWARE_CONFIGURED 0
#endif

#define OPA_DRIVER_A4988 1
#define OPA_DRIVER_DRV8825 2
#ifndef OPA_DRIVER
#define OPA_DRIVER OPA_DRIVER_A4988
#endif
#if OPA_DRIVER != OPA_DRIVER_A4988 && OPA_DRIVER != OPA_DRIVER_DRV8825
#error Unsupported STEP/DIR driver
#endif

const uint8_t STEP_PINS[3] = {2, 3, 4};
const uint8_t DIR_PINS[3] = {5, 6, 7};
const uint8_t ENABLE_PIN = 8;  // Shared active-low enable, held on after STOP.
const uint8_t LIMIT_PINS[3] = {9, 10, 11};
// Normally-closed switches to GND + INPUT_PULLUP: pressed/broken wire = HIGH.
const uint8_t LIMIT_ACTIVE_LEVEL[3] = {HIGH, HIGH, HIGH};
const bool DIR_INVERT[3] = {false, false, false};
// Logical negative Z homing MUST physically retract the head from the sample.
const long MAX_TRAVEL[3] = {10000L, 10000L, 10000L};
const float MAX_SPEED = 800.0f;       // Step pulses / second / axis.
const float ACCELERATION = 400.0f;   // Step pulses / second squared.
const float HOME_SPEED = 200.0f;
const float HOME_SLOW_SPEED = 50.0f;
const long HOME_RELEASE_LIMIT = 400L;
const long HOME_PARK_STEPS = 80L;
const uint32_t HOME_AXIS_TIMEOUT_MS = 90000UL;
const uint32_t MOTION_TIMEOUT_MS = 120000UL;
const uint32_t WATCHDOG_MS = 2000UL;
const uint32_t LIMIT_DEBOUNCE_MS = 5UL;
const char MACHINE_ID[] = "opa-nano-001"; // Give each physical stage its own ID.
