"""Persistent microscope names and camera bindings, independent of camera state."""
import json
import os
import tempfile
from pathlib import Path
from threading import RLock

from backend.models import MICROSCOPES, MicroscopeType


def validate_camera_index(index):
    if type(index) is not int or index < 0:
        raise ValueError('Индекс камеры должен быть целым неотрицательным числом')


def _write_json(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = None
    try:
        with tempfile.NamedTemporaryFile(mode='w', encoding='utf-8', dir=path.parent, delete=False) as stream:
            temporary = Path(stream.name)
            json.dump(value, stream, ensure_ascii=False, indent=2)
        os.replace(temporary, path)
    finally:
        if temporary and temporary.exists():
            temporary.unlink()


class MicroscopeRegistry:
    def __init__(self, data_dir: Path):
        self.custom_path = data_dir / 'microscopes.json'
        self.bindings_path = data_dir / 'microscope_bindings.json'
        self._lock = RLock()

    @staticmethod
    def _read(path, expected, default):
        if not path.exists():
            return default
        try:
            value = json.loads(path.read_text('utf-8'))
            if not isinstance(value, expected):
                raise ValueError('Некорректная структура')
            return value
        except (ValueError, OSError) as error:
            raise ValueError(f'Не удалось прочитать {path.name}: {error}') from error

    def _custom(self):
        entries = self._read(self.custom_path, list, [])
        names = {m.name.casefold() for m in MICROSCOPES}
        ids = set()
        for entry in entries:
            if not isinstance(entry, dict) or not isinstance(entry.get('name'), str) or not entry['name'].strip():
                raise ValueError('Некорректная запись в microscopes.json')
            if entry.get('type') not in ('MANUAL', 'AUTOMATIC'):
                raise ValueError('Неизвестный тип в microscopes.json')
            validate_camera_index(entry.get('camera_index'))
            if type(entry.get('id')) is not int or entry['id'] <= 0 or entry['id'] in ids:
                raise ValueError('Некорректный идентификатор микроскопа')
            if entry['name'].casefold() in names:
                raise ValueError('Повторяющееся название микроскопа')
            names.add(entry['name'].casefold())
            ids.add(entry['id'])
        return entries

    def list(self) -> list[dict]:
        with self._lock:
            bindings = self._read(self.bindings_path, dict, {})
            for index in bindings.values():
                validate_camera_index(index)
            built_in = [dict(**m.to_dict(), custom=False,
                             camera_index=bindings.get(m.name) if m.type != MicroscopeType.DEFAULT else None)
                        for m in MICROSCOPES]
            custom = [dict(entry, custom=True, type_localized=MicroscopeType[entry['type']].value)
                      for entry in self._custom()]
            return built_in + custom

    def get(self, name: str) -> dict:
        for entry in self.list():
            if entry['name'] == name:
                return entry
        raise ValueError('Микроскоп не найден. Проверьте настройки')

    def save(self, data: dict) -> int:
        with self._lock:
            name = data.get('name', '')
            if not isinstance(name, str) or not name.strip():
                raise ValueError('Укажите название микроскопа')
            name = name.strip()
            if any(entry['name'].casefold() == name.casefold() for entry in self.list()):
                raise ValueError('Микроскоп с таким названием уже существует')
            kind = data.get('type')
            if kind not in ('MANUAL', 'AUTOMATIC'):
                raise ValueError('Выберите ручной или автоматический тип микроскопа')
            index = data.get('camera_index')
            validate_camera_index(index)
            entries = self._custom()
            identifier = max((entry['id'] for entry in entries), default=0) + 1
            entries.append({'id': identifier, 'name': name, 'type': kind,
                            'type_localized': MicroscopeType[kind].value, 'camera_index': index})
            _write_json(self.custom_path, entries)
            return identifier

    def bind(self, name: str, camera_index: int) -> None:
        with self._lock:
            validate_camera_index(camera_index)
            entry = self.get(name)
            if entry['type'] == 'DEFAULT':
                raise ValueError('Режим готовых фотографий не использует камеру')
            if entry['custom']:
                entries = self._custom()
                for item in entries:
                    if item['id'] == entry['id']:
                        item['camera_index'] = camera_index
                _write_json(self.custom_path, entries)
            else:
                bindings = self._read(self.bindings_path, dict, {})
                bindings[name] = camera_index
                _write_json(self.bindings_path, bindings)

    def delete(self, microscope_id: int) -> None:
        with self._lock:
            entries = self._custom()
            _write_json(self.custom_path, [entry for entry in entries if entry['id'] != microscope_id])
