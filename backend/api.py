import base64
import math
from pathlib import Path
from functools import wraps
from inspect import signature
from threading import RLock

import numpy as np

import cv2

import backend.database as db
import backend.storage as storage
from backend.analyzer import run_calibration_analysis, run_research_analysis
from backend.camera import CameraController
from backend.microscopes import MicroscopeRegistry, validate_camera_index
from backend.logger import logger
from backend.models import (
    DIVISION_PRICES,
    MICROSCOPES,
    Calibration,
    ContourData,
    Research,
)

def _cal_to_dict(cal: Calibration) -> dict:
    return {
        'id': cal.id,
        'name': cal.name,
        'microscope': cal.microscope,
        'coefficient': cal.coefficient,
        'division_price': cal.division_price,
        'date': cal.date.isoformat(),
    }


def _res_to_dict(res: Research, contours: list[ContourData] | None = None) -> dict:
    d = {
        'id': res.id,
        'name': res.name,
        'employee': res.employee,
        'microscope': res.microscope,
        'calibration_id': res.calibration_id,
        'average_perimeter': res.average_perimeter,
        'average_area': res.average_area,
        'average_width': res.average_width,
        'average_length': res.average_length,
        'average_dek': res.average_dek,
        'date': res.date.isoformat(),
    }
    if contours is not None:
        d['contours'] = [
            {
                'contour_number': c.contour_number,
                'perimeter': c.perimeter,
                'area': c.area,
                'width': c.width,
                'length': c.length,
                'dek': c.dek,
            }
            for c in contours
        ]
    return d


def _calibration_scale(cal: Calibration | None) -> tuple[float, float]:
    if cal is None:
        raise ValueError('Выбранная калибровка не найдена')
    divisions = {price.name: price.value for price in DIVISION_PRICES}
    if cal.division_price not in divisions:
        raise ValueError('Выберите корректную цену деления')
    coefficient = float(cal.coefficient)
    if not math.isfinite(coefficient) or coefficient <= 0:
        raise ValueError('Коэффициент калибровки должен быть конечным положительным числом')
    return coefficient, divisions[cal.division_price]


def _api_method(method):
    @wraps(method)
    def call(self, *args, **kwargs):
        with self._lock:
            try:
                return {'ok': True, **method(self, *args, **kwargs)}
            except Exception as error:
                logger.exception('Ошибка %s', method.__name__)
                return {'ok': False, 'error': str(error)}
    call.__signature__ = signature(method)
    return call


class Api:
    """All bridge mutations share a lock; camera ownership is scoped to a session."""
    def __init__(self):
        self._lock = RLock()
        self.session = {'research_id': 0, 'calibration_id': 0}
        self.registry = MicroscopeRegistry(storage.DATA_DIR)
        self.camera = CameraController()
        self._revisions = {'research': 0, 'calibration': 0}
        self._analysis = None
        self._owner = None

    def _context(self, context):
        if context not in self._revisions:
            raise ValueError('Неизвестный контекст')

    def _check_revision(self, context, revision):
        self._context(context)
        if type(revision) is not int or revision != self._revisions[context]:
            raise ValueError('Сессия изменилась. Обновите данные и повторите действие')

    def _changed(self, context):
        self._revisions[context] += 1
        if context == 'research':
            self._analysis = None
            storage.clear_research_outputs()
        return self._revisions[context]

    def _close_camera(self):
        self.camera.close()
        self._owner = None

    def _calibration_signature(self, identifier):
        cal = db.get_calibration(identifier) if identifier else None
        return (cal.id, cal.microscope, cal.coefficient, cal.division_price) if cal else None

    def _camera_owner(self, token, context=None):
        if not self._owner or self._owner['token'] != token:
            raise ValueError('Подключение камеры устарело')
        if context is not None and self._owner['context'] != context:
            raise ValueError('Камера подключена к другой вкладке')
        return self._owner

    @_api_method
    def get_session_state(self, context: str) -> dict:
        self._context(context)
        return {'revision': self._revisions[context]}

    @_api_method
    def new_research(self) -> dict:
        self._close_camera()
        storage.clear_session_research()
        self.session['research_id'] = 0
        return {'revision': self._changed('research')}

    @_api_method
    def new_calibration(self) -> dict:
        self._close_camera()
        storage.clear_session_calibration()
        self.session['calibration_id'] = 0
        return {'revision': self._changed('calibration')}

    @_api_method
    def invalidate_research(self, revision: int) -> dict:
        self._check_revision('research', revision)
        return {'revision': self._changed('research')}

    @_api_method
    def upload_image(self, filename: str, b64_data: str, context: str) -> dict:
        self._context(context)
        if not filename or Path(filename).name != filename or '/' in filename or '\\' in filename:
            raise ValueError('Некорректное имя файла')
        raw = base64.b64decode(b64_data.split(',', 1)[-1], validate=True)
        frame = cv2.imdecode(np.frombuffer(raw, np.uint8), cv2.IMREAD_COLOR)
        if frame is None:
            raise ValueError('Не удалось прочитать изображение')
        if context == 'calibration':
            filename = storage.save_session_frame(frame, context)
        else:
            filename = Path(filename).stem + '.jpg'
            storage.write_jpeg(storage.SESSION_RES_DIR / 'sources' / filename, frame)
        return {'filename': filename, 'revision': self._changed(context)}

    @_api_method
    def delete_image(self, filename: str, context: str) -> dict:
        self._context(context)
        if Path(filename).name != filename or '/' in filename or '\\' in filename:
            raise ValueError('Некорректное имя файла')
        if context == 'calibration':
            for name in ('sources.jpg', 'contrasted.jpg', 'contours.jpg', 'calibrated.jpg'):
                (storage.SESSION_CAL_DIR / name).unlink(missing_ok=True)
        else:
            (storage.SESSION_RES_DIR / 'sources' / filename).unlink(missing_ok=True)
        return {'revision': self._changed(context)}

    @_api_method
    def list_images(self, context: str) -> dict:
        self._context(context)
        return {'files': storage.list_session_images(context), 'revision': self._revisions[context]}

    @_api_method
    def get_image(self, filename: str, folder: str, context: str) -> dict:
        self._context(context)
        if Path(filename).name != filename or '/' in filename or '\\' in filename:
            raise ValueError('Некорректное имя файла')
        if context == 'research' and folder not in ('sources', 'contrasted', 'contours', 'analyzed'):
            raise ValueError('Неизвестная папка изображения')
        return {'data': storage.get_session_image_b64(filename, folder, context)}

    @_api_method
    def execute_research(self, calibration_id: int) -> dict:
        self._analysis = None
        cal = db.get_calibration(calibration_id) if calibration_id else None
        coeff, division = _calibration_scale(cal)
        result = run_research_analysis(coeff, division)
        if not result['contours']:
            self._analysis = None
            raise ValueError('Частицы не найдены. Проверьте резкость, освещение и исходные изображения')
        revision = self._revisions['research']
        self._analysis = dict(result, revision=revision, calibration_id=cal.id,
                              calibration_signature=self._calibration_signature(cal.id))
        return dict(result, revision=revision)

    @_api_method
    def execute_calibration(self) -> dict:
        return dict(run_calibration_analysis(), revision=self._revisions['calibration'])

    @_api_method
    def get_calibrations(self) -> dict:
        return {'calibrations': [_cal_to_dict(cal) for cal in db.get_all_calibrations()]}

    @_api_method
    def get_calibration(self, calibration_id: int) -> dict:
        cal = db.get_calibration(calibration_id)
        if cal is None:
            raise ValueError('Калибровка не найдена')
        return {'calibration': _cal_to_dict(cal)}

    @_api_method
    def save_calibration(self, data: dict) -> dict:
        self._check_revision('calibration', data.get('revision'))
        if data.get('id', 0) != self.session['calibration_id']:
            raise ValueError('Открытая калибровка изменилась или была удалена')
        name = data.get('name', '').strip()
        microscope = data.get('microscope', '')
        self.registry.get(microscope)
        if not name:
            raise ValueError('Укажите название калибровки')
        cal = Calibration(id=data.get('id', 0), name=name, microscope=microscope,
                          coefficient=float(data['coefficient']), division_price=data['division_price'])
        _calibration_scale(cal)
        identifier = db.save_calibration(cal)
        storage.save_calibration_files(identifier)
        self.session['calibration_id'] = identifier
        return {'id': identifier}

    @_api_method
    def load_calibration(self, calibration_id: int) -> dict:
        cal = db.get_calibration(calibration_id)
        if cal is None:
            raise ValueError('Калибровка не найдена')
        self._close_camera()
        storage.load_calibration_files(calibration_id)
        self.session['calibration_id'] = calibration_id
        return {'calibration': _cal_to_dict(cal), 'files': storage.list_session_images('calibration'),
                'revision': self._changed('calibration')}

    @_api_method
    def delete_calibration(self, calibration_id: int) -> dict:
        db.delete_calibration(calibration_id)
        storage.delete_calibration_files(calibration_id)
        active = self.session['calibration_id'] == calibration_id
        if active:
            self._close_camera()
            self.session['calibration_id'] = 0
            self._changed('calibration')
        return {'active': active, 'revision': self._revisions['calibration']}

    @_api_method
    def get_researches(self) -> dict:
        return {'researches': [_res_to_dict(res) for res in db.get_all_researches()]}

    @_api_method
    def get_research(self, research_id: int) -> dict:
        res = db.get_research(research_id)
        if res is None:
            raise ValueError('Исследование не найдено')
        return {'research': _res_to_dict(res, db.get_contours(research_id))}

    @_api_method
    def save_research(self, data: dict) -> dict:
        self._check_revision('research', data.get('revision'))
        if data.get('id', 0) != self.session['research_id']:
            raise ValueError('Открытое исследование изменилось или было удалено')
        analysis = self._analysis
        if not analysis or analysis['revision'] != self._revisions['research']:
            raise ValueError('Исходные данные изменились. Выполните анализ заново')
        identifier = data.get('calibration_id') or None
        if identifier != analysis['calibration_id'] or self._calibration_signature(identifier) != analysis['calibration_signature']:
            raise ValueError('Калибровка изменилась. Выполните анализ заново')
        signature = analysis['calibration_signature']
        if signature and data['microscope'] != signature[1]:
            raise ValueError('Калибровка не соответствует выбранному микроскопу')
        averages = analysis['averages']
        res = Research(id=data.get('id', 0), name=data['name'], employee=data['employee'],
                       microscope=data['microscope'], calibration_id=identifier,
                       **{'average_' + key: averages[key] for key in ('perimeter','area','width','length','dek')})
        identifier = db.save_research(res)
        contours = [ContourData(research_id=identifier, **{key: result[key] for key in
                    ('contour_number','perimeter','area','width','length','dek')}) for result in analysis['contours']]
        db.save_contours(identifier, contours)
        storage.save_research_files(identifier)
        self.session['research_id'] = identifier
        return {'id': identifier}

    @_api_method
    def load_research(self, research_id: int) -> dict:
        res = db.get_research(research_id)
        if res is None:
            raise ValueError('Исследование не найдено')
        self._close_camera()
        storage.load_research_files(research_id)
        # Loading is a new revision, but must retain the saved processed images.
        self._revisions['research'] += 1
        revision = self._revisions['research']
        self.session['research_id'] = research_id
        result = _res_to_dict(res, db.get_contours(research_id))
        self._analysis = {'revision': revision, 'calibration_id': res.calibration_id,
                          'calibration_signature': self._calibration_signature(res.calibration_id),
                          'contours': result['contours'],
                          'averages': {key: getattr(res, 'average_' + key) for key in ('perimeter','area','width','length','dek')}}
        return {'research': result, 'files': storage.list_session_images('research'), 'revision': revision}

    @_api_method
    def delete_research(self, research_id: int) -> dict:
        db.delete_research(research_id)
        storage.delete_research_files(research_id)
        active = self.session['research_id'] == research_id
        if active:
            self._close_camera()
            self.session['research_id'] = 0
            self._changed('research')
        return {'active': active, 'revision': self._revisions['research']}

    @_api_method
    def get_microscopes(self) -> dict:
        return {'microscopes': self.registry.list()}

    @_api_method
    def get_division_prices(self) -> dict:
        return {'division_prices': [price.to_dict() for price in DIVISION_PRICES]}

    @_api_method
    def bind_microscope(self, name: str, camera_index: int) -> dict:
        self.registry.bind(name, camera_index)
        if self._owner and self._owner['name'] == name:
            self._close_camera()
        return {}

    @_api_method
    def save_custom_microscope(self, data: dict) -> dict:
        return {'id': self.registry.save(data)}

    @_api_method
    def delete_custom_microscope(self, microscope_id: int) -> dict:
        if self._owner and self._owner['name'] is not None and self.registry.get(self._owner['name']).get('id') == microscope_id:
            self._close_camera()
        self.registry.delete(microscope_id)
        return {}

    @_api_method
    def scan_cameras(self) -> dict:
        return {'cameras': self.camera.scan()}

    @_api_method
    def get_test_frame(self, camera_index: int) -> dict:
        if self._owner:
            raise ValueError('Сначала отключите текущий предпросмотр')
        token = self.camera.open(camera_index)
        try:
            return {'data': self._encode_preview(self.camera.read(token))}
        finally:
            self.camera.close(token)

    @staticmethod
    def _encode_jpeg(frame, quality=95):
        success, encoded = cv2.imencode('.jpg', frame, [cv2.IMWRITE_JPEG_QUALITY, quality])
        if not success:
            raise OSError('Не удалось подготовить кадр')
        return 'data:image/jpeg;base64,' + base64.b64encode(encoded).decode('ascii')

    @staticmethod
    def _encode_preview(frame):
        h, w = frame.shape[:2]
        if max(h,w) > 800:
            scale = 800 / max(h,w)
            frame = cv2.resize(frame, (round(w * scale), round(h * scale)))
        return Api._encode_jpeg(frame, quality=80)

    @_api_method
    def connect_camera(self, camera_index: int) -> dict:
        """Test a discovered camera before registering a microscope."""
        validate_camera_index(camera_index)
        self._close_camera()
        token = self.camera.open(camera_index)
        self._owner = {'token': token, 'name': None, 'context': 'settings'}
        return {'connection_id': token}

    @_api_method
    def capture_test_frame(self, connection_id: str) -> dict:
        self._camera_owner(connection_id, 'settings')
        frame = self.camera.read(connection_id)
        height, width = frame.shape[:2]
        return {'data': self._encode_jpeg(frame), 'width': width, 'height': height}

    @_api_method
    def connect_microscope(self, name: str, context: str) -> dict:
        if context not in ('settings','research','calibration'):
            raise ValueError('Неизвестный контекст камеры')
        microscope = self.registry.get(name)
        index = microscope.get('camera_index')
        if index is None:
            raise ValueError('Сначала привяжите камеру к микроскопу в настройках')
        self._close_camera()
        token = self.camera.open(index)
        self._owner = {'token': token, 'name': name, 'context': context}
        return {'connection_id': token, 'revision': self._revisions.get(context, 0)}

    @_api_method
    def get_camera_frame(self, connection_id: str) -> dict:
        self._camera_owner(connection_id)
        return {'data': self._encode_preview(self.camera.read(connection_id))}

    @_api_method
    def disconnect_camera(self, connection_id: str) -> dict:
        if self._owner and self._owner['token'] == connection_id:
            self._close_camera()
        return {}

    @_api_method
    def capture_image(self, connection_id: str, context: str, revision: int) -> dict:
        self._check_revision(context, revision)
        self._camera_owner(connection_id, context)
        frame = self.camera.read(connection_id)
        filename = storage.save_session_frame(frame, context)
        return {'filename': filename, 'revision': self._changed(context)}

    def shutdown(self) -> None:
        with self._lock:
            self._close_camera()
