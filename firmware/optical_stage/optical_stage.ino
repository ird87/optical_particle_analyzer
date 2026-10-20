// OPA XYZ stage, protocol 1. No motion from serial open / startup.
// AccelStepper 1.64+; see ../README.md for wiring and commissioning.
#include <Arduino.h>
#include <AccelStepper.h>
#include <errno.h>
#include <limits.h>
#include "stage_config.h"

AccelStepper motorX(AccelStepper::DRIVER, STEP_PINS[0], DIR_PINS[0], false);
AccelStepper motorY(AccelStepper::DRIVER, STEP_PINS[1], DIR_PINS[1], false);
AccelStepper motorZ(AccelStepper::DRIVER, STEP_PINS[2], DIR_PINS[2], false);
AccelStepper* motors[3] = {&motorX, &motorY, &motorZ};

enum State {IDLE, HOMING, MOVING, FAULT};
enum HomePhase {RELEASE, SEEK, WAIT_PRESS, BACKOFF, APPROACH, WAIT_FINAL, PARK};
State state = IDLE;
HomePhase homePhase = SEEK;
bool homed = false;
bool rawLimit[3] = {false, false, false};
bool stableLimit[3] = {false, false, false};
uint32_t limitChanged[3] = {0, 0, 0};
const uint8_t homeOrder[3] = {2, 0, 1};
uint8_t homeIndex = 0;
uint32_t activeId = 0, lastRx = 0, motionStart = 0, homeAxisStart = 0;
long phaseStart = 0;
char input[96];
uint8_t inputLength = 0;
bool inputOverflow = false;

const __FlashStringHelper* boardName() {
#if defined(ARDUINO_AVR_NANO)
  return F("nano");
#elif defined(ARDUINO_AVR_UNO)
  return F("uno");
#elif defined(ARDUINO_AVR_MEGA2560)
  return F("mega");
#else
#error Select classic Nano ATmega328P, Uno, or Mega2560.
#endif
}

void errorReply(uint32_t id, const __FlashStringHelper* code) {
  Serial.print(F("{\"id\":")); Serial.print(id);
  Serial.print(F(",\"ok\":false,\"error\":\"")); Serial.print(code); Serial.println(F("\"}"));
}

void ackReply(uint32_t id) {
  Serial.print(F("{\"id\":")); Serial.print(id); Serial.println(F(",\"ok\":true,\"done\":false}"));
}

uint32_t configFingerprint() {
  uint32_t hash = 2166136261UL;
  const long config[] = {OPA_DRIVER, ENABLE_PIN, HOME_RELEASE_LIMIT, HOME_PARK_STEPS,
    (long)(MAX_SPEED * 1000), (long)(ACCELERATION * 1000),
    (long)(HOME_SPEED * 1000), (long)(HOME_SLOW_SPEED * 1000)};
  for (uint8_t i = 0; i < sizeof(config) / sizeof(config[0]); ++i) hash = (hash ^ (uint32_t)config[i]) * 16777619UL;
  for (uint8_t i = 0; i < 3; ++i) {
    hash = (hash ^ STEP_PINS[i]) * 16777619UL;
    hash = (hash ^ DIR_PINS[i]) * 16777619UL;
    hash = (hash ^ LIMIT_PINS[i]) * 16777619UL;
    hash = (hash ^ LIMIT_ACTIVE_LEVEL[i]) * 16777619UL;
    hash = (hash ^ DIR_INVERT[i]) * 16777619UL;
    hash = (hash ^ (uint32_t)MAX_TRAVEL[i]) * 16777619UL;
  }
  return hash;
}

void doneReply(uint32_t id) {
  Serial.print(F("{\"id\":")); Serial.print(id);
  Serial.print(F(",\"ok\":true,\"done\":true,\"protocol\":1,\"state\":\""));
  if (state == FAULT) Serial.print(F("FAULT"));
  else if (state == HOMING) Serial.print(F("HOMING"));
  else if (state == MOVING) Serial.print(F("MOVING"));
  else Serial.print(homed ? F("IDLE") : F("UNHOMED"));
  Serial.print(F("\",\"homed\":")); Serial.print(homed ? F("true") : F("false"));
  Serial.print(F(",\"configured\":")); Serial.print(OPA_HARDWARE_CONFIGURED ? F("true") : F("false"));
  Serial.print(F(",\"pos\":["));
  for (uint8_t i = 0; i < 3; ++i) { if (i) Serial.print(','); Serial.print(motors[i]->currentPosition()); }
  Serial.print(F("],\"limits\":["));
  for (uint8_t i = 0; i < 3; ++i) { if (i) Serial.print(','); Serial.print(rawLimit[i] ? 1 : 0); }
  Serial.print(F("],\"max\":["));
  for (uint8_t i = 0; i < 3; ++i) { if (i) Serial.print(','); Serial.print(MAX_TRAVEL[i]); }
  Serial.print(F("],\"board\":\"")); Serial.print(boardName());
  Serial.print(F("\",\"driver\":\""));
#if OPA_DRIVER == OPA_DRIVER_DRV8825
  Serial.print(F("drv8825"));
#else
  Serial.print(F("a4988"));
#endif
  Serial.print(F("\",\"config_id\":")); Serial.print(configFingerprint());
  Serial.print(F(",\"machine_id\":\"")); Serial.print(MACHINE_ID); Serial.println(F("\"}"));
}

void haltMotors() {
  for (uint8_t i = 0; i < 3; ++i) motors[i]->setCurrentPosition(motors[i]->currentPosition());
  // Do not disable holding current on a vertical Z axis.
}

void failMotion(const __FlashStringHelper* code) {
  haltMotors(); homed = false; state = FAULT;
  if (activeId) errorReply(activeId, code);
  activeId = 0;
}

void updateLimits() {
  const uint32_t now = millis();
  for (uint8_t i = 0; i < 3; ++i) {
    bool current = digitalRead(LIMIT_PINS[i]) == LIMIT_ACTIVE_LEVEL[i];
    if (current != rawLimit[i]) { rawLimit[i] = current; limitChanged[i] = now; }
    if ((uint32_t)(now - limitChanged[i]) >= LIMIT_DEBOUNCE_MS) stableLimit[i] = rawLimit[i];
  }
}

void setHomePhase(HomePhase phase) {
  uint8_t axis = homeOrder[homeIndex];
  motors[axis]->setCurrentPosition(motors[axis]->currentPosition());
  homePhase = phase; phaseStart = motors[axis]->currentPosition();
}

void startHomeAxis() {
  homeAxisStart = millis();
  uint8_t axis = homeOrder[homeIndex];
  setHomePhase(rawLimit[axis] ? RELEASE : SEEK);
}

void runHoming() {
  const uint8_t axis = homeOrder[homeIndex];
  AccelStepper& motor = *motors[axis];
  long traveled = labs(motor.currentPosition() - phaseStart);
  if ((uint32_t)(millis() - homeAxisStart) > HOME_AXIS_TIMEOUT_MS) { failMotion(F("HOME_TIMEOUT")); return; }
  if (homePhase == RELEASE) {
    if (!rawLimit[axis] && !stableLimit[axis]) { setHomePhase(SEEK); return; }
    if (traveled >= HOME_RELEASE_LIMIT) { failMotion(F("LIMIT_STUCK")); return; }
    if (!rawLimit[axis]) return; // Wait stationary for debounce.
    motor.setSpeed(HOME_SPEED); motor.runSpeed();
  } else if (homePhase == SEEK || homePhase == APPROACH) {
    if (rawLimit[axis]) { setHomePhase(homePhase == SEEK ? WAIT_PRESS : WAIT_FINAL); return; }
    long allowed = homePhase == SEEK ? MAX_TRAVEL[axis] + HOME_RELEASE_LIMIT : HOME_PARK_STEPS * 2;
    if (traveled > allowed) { failMotion(F("LIMIT_NOT_FOUND")); return; }
    motor.setSpeed(homePhase == SEEK ? -HOME_SPEED : -HOME_SLOW_SPEED); motor.runSpeed();
  } else if (homePhase == WAIT_PRESS || homePhase == WAIT_FINAL) {
    if (!rawLimit[axis]) { setHomePhase(homePhase == WAIT_PRESS ? SEEK : APPROACH); return; }
    if (!stableLimit[axis]) return;
    if (homePhase == WAIT_PRESS) setHomePhase(BACKOFF);
    else { motor.setCurrentPosition(-HOME_PARK_STEPS); setHomePhase(PARK); }
  } else if (homePhase == BACKOFF || homePhase == PARK) {
    if (traveled >= HOME_PARK_STEPS) {
      if (rawLimit[axis] || stableLimit[axis]) { failMotion(F("LIMIT_STUCK")); return; }
      if (homePhase == BACKOFF) { setHomePhase(APPROACH); return; }
      motor.setCurrentPosition(0);
      if (++homeIndex < 3) startHomeAxis();
      else {
        for (uint8_t i = 0; i < 3; ++i) if (rawLimit[i] || stableLimit[i]) { failMotion(F("LIMIT_ACTIVE")); return; }
        homed = true; state = IDLE;
        uint32_t id = activeId; activeId = 0; doneReply(id);
      }
      return;
    }
    motor.setSpeed(HOME_SPEED); motor.runSpeed();
  }
}

bool parseLong(char* token, long& value) {
  if (!token || strlen(token) > 11) return false;
  errno = 0; char* end;
  value = strtol(token, &end, 10);
  return !errno && *token && !*end;
}

void handleLine(char* line) {
  char* save = NULL;
  char* idText = strtok_r(line, " ", &save);
  char* verb = strtok_r(NULL, " ", &save);
  if (!idText || !verb) { if (activeId) failMotion(F("BAD_COMMAND")); return; }
  errno = 0; char* end;
  unsigned long id = strtoul(idText, &end, 10);
  if (errno || *end || *idText == '-' || strlen(idText) > 10) { if (activeId) failMotion(F("BAD_ID")); return; }
  if (id == 0 && strcmp(verb, "PING") == 0 && !strtok_r(NULL, " ", &save)) { lastRx = millis(); return; }
  if (!id) return;
  lastRx = millis();
  if (!strcmp(verb, "STOP") || !strcmp(verb, "HELLO")) {
    if (strtok_r(NULL, " ", &save)) { errorReply(id, F("BAD_ARGUMENTS")); return; }
    if (activeId) failMotion(F("STOPPED"));
    haltMotors(); homed = false; state = IDLE; doneReply(id); return;
  }
  if (!strcmp(verb, "STATUS")) { doneReply(id); return; }
  if (state == MOVING || state == HOMING) { errorReply(id, F("BUSY")); return; }
  if (!OPA_HARDWARE_CONFIGURED) { errorReply(id, F("HARDWARE_NOT_CONFIGURED")); return; }
  if (!strcmp(verb, "HOME")) {
    if (strtok_r(NULL, " ", &save)) { errorReply(id, F("BAD_ARGUMENTS")); return; }
    homed = false; state = HOMING; activeId = id; homeIndex = 0;
    digitalWrite(ENABLE_PIN, LOW); ackReply(id); startHomeAxis(); return;
  }
  if (!strcmp(verb, "MOVE")) {
    if (!homed || state == FAULT) { errorReply(id, F("HOME_REQUIRED")); return; }
    long target[3];
    for (uint8_t i = 0; i < 3; ++i) {
      if (!parseLong(strtok_r(NULL, " ", &save), target[i]) || target[i] < 0 || target[i] > MAX_TRAVEL[i]) {
        errorReply(id, F("OUT_OF_RANGE")); return;
      }
    }
    if (strtok_r(NULL, " ", &save)) { errorReply(id, F("BAD_ARGUMENTS")); return; }
    for (uint8_t i = 0; i < 3; ++i) if (rawLimit[i]) { failMotion(F("LIMIT_ACTIVE")); errorReply(id, F("LIMIT_ACTIVE")); return; }
    for (uint8_t i = 0; i < 3; ++i) motors[i]->moveTo(target[i]);
    activeId = id; state = MOVING; motionStart = millis(); ackReply(id); return;
  }
  errorReply(id, F("UNKNOWN_COMMAND"));
}

void setup() {
  pinMode(ENABLE_PIN, OUTPUT); digitalWrite(ENABLE_PIN, HIGH);
  for (uint8_t i = 0; i < 3; ++i) {
    pinMode(LIMIT_PINS[i], INPUT_PULLUP);
    motors[i]->setPinsInverted(DIR_INVERT[i], false, false);
    motors[i]->setMaxSpeed(MAX_SPEED); motors[i]->setAcceleration(ACCELERATION);
    motors[i]->setMinPulseWidth(3); motors[i]->enableOutputs();
    rawLimit[i] = stableLimit[i] = digitalRead(LIMIT_PINS[i]) == LIMIT_ACTIVE_LEVEL[i];
  }
  Serial.begin(115200); Serial.println(F("BOOT OPA1")); lastRx = millis();
}

void loop() {
  updateLimits();
  // Bounded parsing per tick keeps stepping and STOP servicing responsive.
  for (uint8_t budget = 0; budget < 16 && Serial.available(); ++budget) {
    char c = Serial.read();
    if (c == '\r') continue;
    if (c == '\n') {
      if (inputOverflow) { if (activeId) failMotion(F("LINE_TOO_LONG")); }
      else if (inputLength) { input[inputLength] = 0; handleLine(input); }
      inputLength = 0; inputOverflow = false;
    } else if (inputLength < sizeof(input) - 1 && !inputOverflow) input[inputLength++] = c;
    else inputOverflow = true;
  }
  if ((state == MOVING || state == HOMING) && (uint32_t)(millis() - lastRx) > WATCHDOG_MS) { failMotion(F("HOST_TIMEOUT")); return; }
  if (state == HOMING) { runHoming(); return; }
  if (state == MOVING) {
    for (uint8_t i = 0; i < 3; ++i) if (rawLimit[i]) { failMotion(F("LIMIT_ACTIVE")); return; }
    if ((uint32_t)(millis() - motionStart) > MOTION_TIMEOUT_MS) { failMotion(F("MOTION_TIMEOUT")); return; }
    bool running = false;
    for (uint8_t i = 0; i < 3; ++i) { motors[i]->run(); running |= motors[i]->distanceToGo() != 0; }
    if (!running) { state = IDLE; uint32_t id = activeId; activeId = 0; doneReply(id); }
  }
}
