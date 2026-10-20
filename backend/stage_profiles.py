"""Immutable measured Z presets. No interpolation between optical configurations."""
import copy
import json
import math
import os
import re
import tempfile
from pathlib import Path
from threading import RLock


def atomic_json(path, value):
    path = Path(path); path.parent.mkdir(parents=True, exist_ok=True)
    temporary = None
    try:
        with tempfile.NamedTemporaryFile(mode='w', encoding='utf-8', dir=path.parent, delete=False) as stream:
            temporary = Path(stream.name)
            json.dump(value, stream, ensure_ascii=False, indent=2, allow_nan=False)
        os.replace(temporary, path)
    finally:
        if temporary: temporary.unlink(missing_ok=True)


def validate_profile(value):
    p = copy.deepcopy(value)
    if not isinstance(p, dict) or not re.fullmatch(r'[a-zA-Z0-9_-]{1,80}', str(p.get('id', ''))):
        raise ValueError('Некорректный профиль Z')
    if not all(isinstance(p.get(k), str) and p[k].strip() for k in ('name', 'microscope')):
        raise ValueError('Укажите название профиля и микроскоп')
    if not isinstance(p.get('binding'), dict) or not p['binding'].get('machine_id'):
        raise ValueError('Нет привязки к оборудованию')
    points = p.get('points')
    if not isinstance(points, list) or not 1 <= len(points) <= 100:
        raise ValueError('Профиль должен содержать от 1 до 100 проверенных положений Z')
    seen = set()
    for point in points:
        if not isinstance(point, dict) or type(point.get('z')) is not int or not 0 <= point['z'] <= 10000000 or point['z'] in seen:
            raise ValueError('Положения Z должны быть целыми, положительными и уникальными')
        seen.add(point['z'])
        for key in ('width', 'height', 'calibration_id'):
            if type(point.get(key)) is not int or point[key] <= 0: raise ValueError('Неполная калибровка Z')
        for key in ('coefficient', 'division_um'):
            v = point.get(key)
            if type(v) not in (int, float) or not math.isfinite(v) or v <= 0: raise ValueError('Неверный масштаб Z')
        if not re.fullmatch(r'[0-9]+\.jpg', str(point.get('image', ''))): raise ValueError('Нет снимка эталона')
    return p


def profile_point(profile, z, dimensions, binding):
    p = validate_profile(profile)
    if p['binding'] != binding:
        raise ValueError('Оборудование или настройки изменились. Повторите калибровку Z')
    point = next((q for q in p['points'] if q['z'] == z and type(z) is int), None)
    if point is None: raise ValueError('Для этого Z нет измеренной калибровки; выполните мастер Z')
    if dimensions != [point['width'], point['height']]:
        raise ValueError('Разрешение камеры изменилось. Повторите калибровку Z')
    return copy.deepcopy(point)


class ProfileStore:
    def __init__(self, root):
        self.root = Path(root) / 'stage_profiles'
        self._lock = RLock()

    def save(self, profile):
        p = validate_profile(profile)
        with self._lock:
            path = self.root / (p['id'] + '.json')
            # Profiles are immutable: a new optical setup gets a new ID.
            if path.exists() and self.load(p['id']) != p: raise ValueError('Создайте новый профиль вместо изменения сохранённого')
            atomic_json(path, p)
        return copy.deepcopy(p)

    def load(self, identifier):
        if not isinstance(identifier, str) or not re.fullmatch(r'[a-zA-Z0-9_-]{1,80}', identifier): raise ValueError('Неверный идентификатор профиля')
        with self._lock:
            return validate_profile(json.loads((self.root / (identifier + '.json')).read_text(encoding='utf-8')))

    def list(self, microscope):
        with self._lock:
            result = []
            for path in sorted(self.root.glob('*.json')):
                try:
                    p = self.load(path.stem)
                    if p['microscope'] == microscope: result.append(p)
                except (ValueError, OSError): continue
            return result
