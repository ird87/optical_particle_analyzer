"""Single serial reader and interruptible requests for the OPA stage protocol."""
import copy
import json
import secrets
import time
from threading import Event, Lock, RLock, Thread

from backend.stage import StageError, parse_stage_response


class SerialStage:
    def __init__(self, settings, serial_factory=None):
        if serial_factory is None:
            try:
                import serial
            except ImportError as error:
                raise StageError('Не установлен pySerial; пересоберите приложение с обновлёнными зависимостями') from error
            serial_factory = serial.Serial
        self.settings = settings
        self._state_lock = RLock()
        self._write_lock = RLock()
        self._operation = Lock()
        self._pending = {}
        self._closed = Event()
        self._sequence = secrets.randbelow(1000000000) + 1
        self._state = {'connected': False, 'state': 'UNHOMED', 'homed': False, 'mode': 'serial'}
        self._serial = serial_factory(settings['port'], 115200, timeout=.1, write_timeout=.5)
        self._reader = Thread(target=self._read_loop, daemon=True, name='stage-serial')
        self._reader.start()
        try:
            # AVR Nano/Uno may reset on DTR. Handshake happens after its bootloader.
            if self._closed.wait(2):
                raise StageError('Контроллер отключился при подключении')
            state = self._request('HELLO', timeout=5)
            if state['board'] != settings['board'] or state['driver'] != settings['driver']:
                raise StageError('Выбранные плата/драйвер не совпадают с прошивкой контроллера')
            with self._state_lock:
                self._state.update(state, connected=True, mode='serial')
        except Exception:
            self.close()
            raise

    def snapshot(self):
        with self._state_lock:
            return copy.deepcopy(self._state)

    def _write(self, line):
        with self._write_lock:
            if self._closed.is_set():
                raise StageError('Контроллер отключён')
            raw = line.encode('ascii')
            if self._serial.write(raw) != len(raw):
                raise StageError('Команда передана не полностью')

    def _fail(self, message):
        with self._state_lock:
            self._state.update(connected=False, state='FAULT', homed=False, error=message)
            for pending in self._pending.values():
                pending['error'] = message
                pending['event'].set()
        self._closed.set()

    def _read_loop(self):
        buffer = bytearray()
        ping_at = time.monotonic()
        try:
            while not self._closed.is_set():
                if time.monotonic() >= ping_at:
                    self._write('0 PING\n')
                    ping_at = time.monotonic() + .5
                chunk = self._serial.read(128)
                if not chunk:
                    continue
                buffer.extend(chunk)
                if len(buffer) > 2048:
                    raise StageError('Слишком длинный ответ контроллера')
                while b'\n' in buffer:
                    raw, _, remaining = buffer.partition(b'\n')
                    buffer = bytearray(remaining)
                    if raw.strip() == b'BOOT OPA1':
                        with self._state_lock:
                            active = bool(self._pending) or self._state.get('connected')
                        if active:
                            raise StageError('Контроллер перезапустился; выполните подключение и поиск нуля заново')
                        continue
                    response = parse_stage_response(raw)
                    with self._state_lock:
                        pending = self._pending.get(response['id'])
                        if pending is None or pending.get('error'):
                            continue  # Never use a late DONE as current position.
                        if not response['ok']:
                            pending['error'] = response['error']
                            pending['event'].set()
                        elif response['done']:
                            pending['result'] = response
                            self._state.update(response)
                            pending['event'].set()
        except Exception as error:
            if not self._closed.is_set():
                self._fail(str(error))

    def _request(self, command, timeout=None, cancel=None):
        timeout = timeout or self.settings['move_timeout_s']
        pending = {'event': Event(), 'command': command}
        with self._state_lock:
            self._sequence += 1
            identifier = self._sequence
            self._pending[identifier] = pending
        try:
            with self._write_lock:
                if (cancel is not None and cancel.is_set()) or pending.get('error'):
                    raise StageError('Перемещение отменено до отправки')
                self._write(f'{identifier} {command}\n')
            if not pending['event'].wait(timeout):
                try:
                    self._write(f'{identifier + 1000000000} STOP\n')
                finally:
                    self._fail('Контроллер не завершил команду за отведённое время')
                raise StageError('Таймаут контроллера; положение стола неизвестно')
            if 'error' in pending:
                with self._state_lock:
                    self._state.update(homed=False, state='FAULT')
                raise StageError(pending['error'])
            return pending['result']
        finally:
            with self._state_lock:
                self._pending.pop(identifier, None)

    def _motion(self, command, state, timeout=None, cancel=None):
        if not self._operation.acquire(blocking=False):
            raise StageError('Стол уже выполняет перемещение')
        try:
            with self._state_lock:
                self._state['state'] = state
            return self._request(command, timeout=timeout, cancel=cancel)
        finally:
            self._operation.release()

    def home(self, cancel=None):
        return self._motion('HOME', 'HOMING', timeout=max(280, self.settings['move_timeout_s']), cancel=cancel)

    def move(self, x, y, z, cancel=None):
        return self._motion(f'MOVE {x} {y} {z}', 'MOVING', cancel=cancel)

    def stop(self):
        # Cancel pending motion BEFORE STOP so a late DONE cannot restore homed.
        with self._state_lock:
            self._state.update(homed=False, state='UNHOMED')
            for pending in self._pending.values():
                if pending['command'] == 'HOME' or pending['command'].startswith('MOVE '):
                    pending['error'] = 'Перемещение остановлено'
                    pending['event'].set()
        return self._request('STOP', timeout=3)

    def close(self):
        if not self._closed.is_set():
            try:
                self.stop()
            except Exception:
                pass
        self._closed.set()
        with self._state_lock:
            self._state.update(connected=False, homed=False, state='DISCONNECTED')
            for pending in self._pending.values():
                pending['error'] = 'Контроллер отключён'
                pending['event'].set()
        self._serial.close()
        if self._reader.is_alive():
            self._reader.join(1)
