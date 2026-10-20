"""XYZ controller contract, configuration and hardware-free simulator."""
import copy
import json
import math
import re
from threading import Event, Lock, RLock


class StageError(RuntimeError):
    pass


DEFAULT_STAGE_SETTINGS = {
    'mode': 'serial', 'port': '', 'board': 'nano', 'driver': 'a4988',
    'travel_steps': [10000, 10000, 10000], 'steps_per_mm': [200.0, 200.0, 200.0],
    'mechanics_confirmed': False, 'settle_ms': 300, 'move_timeout_s': 90.0,
}


def validate_stage_settings(settings=None):
    if settings is None:
        settings = {}
    if not isinstance(settings, dict) or set(settings) - set(DEFAULT_STAGE_SETTINGS):
        raise ValueError('Некорректные настройки стола')
    result = copy.deepcopy(DEFAULT_STAGE_SETTINGS)
    result.update(copy.deepcopy(settings))
    if result['mode'] not in ('serial', 'simulator') or result['board'] not in ('nano', 'uno', 'mega') or result['driver'] not in ('a4988', 'drv8825'):
        raise ValueError('Выберите поддерживаемые контроллер, драйвер и режим подключения')
    if not isinstance(result['port'], str) or len(result['port']) > 200:
        raise ValueError('Некорректный COM-порт')
    result['port'] = result['port'].strip()
    for key in ('travel_steps', 'steps_per_mm'):
        values = result[key]
        if not isinstance(values, list) or len(values) != 3:
            raise ValueError('Нужны три значения для осей X, Y, Z')
        if key == 'travel_steps':
            if any(type(v) is not int or not 1 <= v <= 10000000 for v in values):
                raise ValueError('Ход каждой оси должен быть целым числом от 1 до 10000000 шагов')
        elif any(type(v) not in (int, float) or not math.isfinite(v) or not 0 < v <= 10000000 for v in values):
            raise ValueError('Шагов на миллиметр должно быть конечное положительное число')
    if type(result['mechanics_confirmed']) is not bool:
        raise ValueError('Подтвердите параметры механики')
    if type(result['settle_ms']) is not int or not 0 <= result['settle_ms'] <= 10000:
        raise ValueError('Пауза после перемещения: от 0 до 10000 мс')
    timeout = result['move_timeout_s']
    if type(timeout) not in (int, float) or not math.isfinite(timeout) or not 1 <= timeout <= 600:
        raise ValueError('Таймаут перемещения: от 1 до 600 секунд')
    return result


def parse_stage_response(raw):
    try:
        if len(raw) > 1024:
            raise ValueError('Слишком длинный ответ')
        value = json.loads(raw)
        if not isinstance(value, dict) or type(value.get('id')) is not int or value['id'] <= 0 or type(value.get('ok')) is not bool:
            raise ValueError('Неверный заголовок')
        if not value['ok']:
            if not isinstance(value.get('error'), str):
                raise ValueError('Неверная ошибка')
            return value
        if type(value.get('done')) is not bool:
            raise ValueError('Нет признака завершения')
        if not value['done']:
            return value
        if value.get('protocol') != 1 or type(value.get('protocol')) is not int:
            raise ValueError('Версия протокола не поддерживается')
        if value.get('state') not in ('IDLE', 'UNHOMED', 'HOMING', 'MOVING', 'FAULT'):
            raise ValueError('Неверное состояние')
        for key in ('homed', 'configured'):
            if type(value.get(key)) is not bool:
                raise ValueError('Неверный флаг')
        for key in ('pos', 'limits', 'max'):
            values = value.get(key)
            if not isinstance(values, list) or len(values) != 3 or any(type(v) is not int for v in values):
                raise ValueError('Неверные координаты')
            if key == 'max' and any(not 1 <= v <= 10000000 for v in values):
                raise ValueError('Неверные пределы')
            if key == 'pos' and any(not -(2**31) < v < 2**31 for v in values):
                raise ValueError('Переполнение координат')
            if key == 'limits' and any(v not in (0, 1) for v in values):
                raise ValueError('Неверные концевики')
        if value.get('board') not in ('nano', 'uno', 'mega') or value.get('driver') not in ('a4988', 'drv8825'):
            raise ValueError('Неподдерживаемое оборудование')
        if not isinstance(value.get('machine_id'), str) or not re.fullmatch(r'[A-Za-z0-9_-]{1,80}', value['machine_id']):
            raise ValueError('Нет идентификатора стола')
        if type(value.get('config_id')) is not int or not 0 <= value['config_id'] <= 0xffffffff:
            raise ValueError('Нет отпечатка конфигурации прошивки')
        return value
    except (ValueError, TypeError, UnicodeError) as error:
        raise StageError(f'Некорректный ответ контроллера: {error}') from error


class SimulatedStage:
    def __init__(self, settings):
        self.settings = settings
        self.motion_delay = .025
        self._lock = RLock()
        self._operation = Lock()
        self._cancel = Event()
        self._state = {'connected': True, 'protocol': 1, 'state': 'UNHOMED', 'homed': False,
                       'pos': [0, 0, 0], 'limits': [0, 0, 0], 'max': settings['travel_steps'][:],
                       'configured': True, 'board': settings['board'], 'driver': settings['driver'],
                       'machine_id': 'simulator', 'config_id': 1, 'mode': 'simulator'}

    def snapshot(self):
        with self._lock:
            return copy.deepcopy(self._state)

    def _run(self, target, homing=False, cancel=None):
        if not self._operation.acquire(blocking=False):
            raise StageError('Стол уже выполняет перемещение')
        try:
            with self._lock:
                if not self._state['connected']:
                    raise StageError('Стол отключён')
                if cancel is not None and cancel.is_set():
                    raise StageError('Перемещение отменено до запуска')
                self._cancel.clear()
                self._state['state'] = 'HOMING' if homing else 'MOVING'
            if self._cancel.wait(self.motion_delay):
                raise StageError('Перемещение остановлено; выполните поиск нуля заново')
            with self._lock:
                if self._cancel.is_set() or not self._state['connected']:
                    raise StageError('Стол отключён или остановлен')
                self._state.update(pos=list(target), homed=True, state='IDLE')
                return self.snapshot()
        finally:
            self._operation.release()

    def home(self, cancel=None):
        return self._run([0, 0, 0], homing=True, cancel=cancel)

    def move(self, x, y, z, cancel=None):
        return self._run([x, y, z], cancel=cancel)

    def stop(self):
        with self._lock:
            self._cancel.set()
            self._state.update(state='UNHOMED', homed=False)
            return self.snapshot()

    def close(self):
        self.stop()
        with self._lock:
            self._state.update(connected=False, state='DISCONNECTED')


class StageController:
    def __init__(self):
        self._device = None
        self._lock = RLock()
        self.settings = validate_stage_settings()

    def connect(self, settings):
        settings = validate_stage_settings(settings)
        self.close()
        if settings['mode'] == 'simulator':
            device = SimulatedStage(settings)
        else:
            if not settings['port']:
                raise StageError('Выберите COM-порт контроллера')
            from backend.stage_transport import SerialStage
            device = SerialStage(settings)
        with self._lock:
            self.settings = settings
            self._device = device
        return self.snapshot()

    def _connected(self):
        with self._lock:
            device = self._device
        if device is None or not device.snapshot().get('connected'):
            raise StageError('Стол не подключён')
        return device

    def snapshot(self):
        with self._lock:
            device = self._device
        return device.snapshot() if device else {'connected': False, 'state': 'DISCONNECTED', 'homed': False}

    def home(self, cancel=None):
        device = self._connected()
        if not device.snapshot()['configured']:
            raise StageError('Инженер должен настроить и подтвердить конфигурацию прошивки')
        result = device.home() if cancel is None else device.home(cancel=cancel)
        if not result.get('homed') or result.get('state') != 'IDLE' or result.get('pos') != [0, 0, 0]:
            device.stop()
            raise StageError('Контроллер не подтвердил привязку всех осей к нулю')
        return result

    def move(self, x, y, z, cancel=None):
        device = self._connected()
        state = device.snapshot()
        if not state['configured'] or not state['homed']:
            raise StageError('Сначала настройте оборудование и выполните поиск нуля')
        target = [x, y, z]
        maximum = [min(a, b) for a, b in zip(state['max'], self.settings['travel_steps'])]
        if any(type(v) is not int or not 0 <= v <= limit for v, limit in zip(target, maximum)):
            raise ValueError('Координаты должны быть целыми и находиться в пределах хода стола')
        result = device.move(*target) if cancel is None else device.move(*target, cancel=cancel)
        if not result.get('homed') or result.get('state') != 'IDLE' or result.get('pos') != target:
            device.stop()
            raise StageError('Контроллер не подтвердил достижение требуемых координат')
        return result

    def stop(self):
        return self._connected().stop()

    def close(self):
        with self._lock:
            device, self._device = self._device, None
        if device:
            device.close()
