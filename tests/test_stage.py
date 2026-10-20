import json
import threading
import time

import pytest

from backend.stage import StageController, StageError, validate_stage_settings, parse_stage_response


def test_defaults_use_nano_a4988_and_validate_real_configuration():
    settings = validate_stage_settings({})
    assert settings['board'] == 'nano' and settings['driver'] == 'a4988'
    assert settings['mode'] == 'serial'
    with pytest.raises(ValueError):
        validate_stage_settings({'steps_per_mm': [200, 0, 200]})
    with pytest.raises(ValueError):
        validate_stage_settings({'board': 'unknown'})


def test_simulator_requires_home_and_obeys_all_limits():
    stage = StageController()
    connected = stage.connect({'mode': 'simulator', 'travel_steps': [1000, 2000, 3000]})
    assert connected['board'] == 'nano' and connected['configured']
    with pytest.raises(StageError):
        stage.move(1, 2, 3)
    stage.home()
    assert stage.move(100, 200, 300)['pos'] == [100, 200, 300]
    for target in [(-1, 200, 300), (1001, 0, 0), (0, True, 0), (0, 0, 3001)]:
        with pytest.raises((StageError, ValueError)):
            stage.move(*target)
    assert stage.snapshot()['pos'] == [100, 200, 300]
    stage.close()
    assert not stage.snapshot()['connected']


def test_stop_can_interrupt_an_operation_and_requires_new_home():
    stage = StageController()
    stage.connect({'mode': 'simulator'})
    stage.home()
    started = threading.Event()
    stage._device.motion_delay = .3
    errors = []
    def move():
        started.set()
        try:
            stage.move(1000, 1000, 1000)
        except StageError as error:
            errors.append(str(error))
    thread = threading.Thread(target=move)
    thread.start();assert started.wait(1)
    deadline = time.monotonic() + 1
    while stage.snapshot()['state'] != 'MOVING' and time.monotonic() < deadline:
        time.sleep(.001)
    stage.stop();thread.join(1)
    assert not thread.is_alive() and errors
    assert not stage.snapshot()['homed']
    with pytest.raises(StageError):
        stage.move(1, 1, 1)
    stage.close()


@pytest.mark.parametrize('value', [b'not-json', b'[]', b'{"id":true,"ok":true}', b'{"id":1,"ok":true,"done":true}', b'x' * 1025])
def test_malformed_responses_cannot_authorize_motion(value):
    with pytest.raises(StageError):
        parse_stage_response(value)


def response(identifier=1, **fields):
    return {'id': identifier, 'ok': True, 'done': True, 'protocol': 1, 'state': 'IDLE',
            'homed': True, 'pos': [0, 0, 0], 'limits': [0, 0, 0], 'max': [10000]*3,
            'configured': True, 'board': 'nano', 'driver': 'a4988', **fields}


def test_done_requires_well_formed_coordinates_and_protocol():
    assert parse_stage_response(json.dumps(response()).encode())['pos'] == [0, 0, 0]
    for changed in [{'pos': [0, 1]}, {'pos': [0, True, 0]}, {'protocol': 2}, {'homed': 'yes'}, {'max': [0, 10, 10]}]:
        with pytest.raises(StageError):
            parse_stage_response(json.dumps(response(**changed)).encode())


def test_homing_requires_a_confirmed_reference():
    stage = StageController();stage.connect({'mode': 'simulator'})
    stage._device.home = lambda: {**stage.snapshot(), 'homed': False, 'state': 'UNHOMED'}
    with pytest.raises(StageError):
        stage.home()
    stage.close()


class FakeSerial:
    def __init__(self, *args, **kwargs):
        import queue
        self.incoming = queue.Queue()
        self.closed = False
        self.commands = []
        self.position = [0, 0, 0]
        self.homed = False
        self.hold_move = False

    def send(self, payload):
        raw = payload if isinstance(payload, bytes) else json.dumps(payload).encode() + b'\n'
        for index in range(0, len(raw), 7):
            self.incoming.put(raw[index:index + 7])

    def write(self, raw):
        tokens = raw.decode().strip().split();identifier = int(tokens[0]);command = tokens[1]
        self.commands.append((identifier, command))
        if command == 'PING':
            return len(raw)
        if command == 'HOME':
            self.homed = True
        if command == 'MOVE':
            if self.hold_move:
                self.send({'id': identifier, 'ok': True, 'done': False})
                return len(raw)
            # A well-formed stale response must not update host coordinates.
            self.send(response(identifier - 1, pos=[999, 999, 999]))
            self.position = list(map(int, tokens[2:]))
        if command == 'STOP':
            self.homed = False
        self.send(response(identifier, homed=self.homed, pos=self.position[:]))
        return len(raw)

    def read(self, size):
        import queue
        try:
            return self.incoming.get(timeout=.01)
        except queue.Empty:
            return b''

    def close(self):
        self.closed = True


def test_serial_handles_partial_lines_stale_done_and_stop_during_move():
    from backend.stage_transport import SerialStage
    serial = FakeSerial()
    stage = SerialStage(validate_stage_settings({'port': 'TEST'}), serial_factory=lambda *a, **k: serial)
    stage.home()
    assert stage.move(1, 2, 3)['pos'] == [1, 2, 3]
    serial.hold_move = True
    errors = []
    def move():
        try:
            stage.move(4, 5, 6)
        except StageError as error:
            errors.append(str(error))
    thread = threading.Thread(target=move);thread.start()
    deadline = time.monotonic() + 1
    while stage.snapshot()['state'] != 'MOVING' and time.monotonic() < deadline:
        time.sleep(.001)
    stage.stop();thread.join(1)
    assert not thread.is_alive() and errors and not stage.snapshot()['homed']
    stage.close();assert serial.closed


def test_an_idle_controller_reboot_invalidates_its_reference():
    from backend.stage_transport import SerialStage
    serial = FakeSerial()
    stage = SerialStage(validate_stage_settings({'port': 'TEST'}), serial_factory=lambda *a, **k: serial)
    stage.home();serial.send(b'BOOT OPA1\n')
    deadline = time.monotonic() + .3
    while stage.snapshot()['homed'] and time.monotonic() < deadline:
        time.sleep(.001)
    try:
        assert not stage.snapshot()['homed'] and not stage.snapshot()['connected']
    finally:
        stage.close()
