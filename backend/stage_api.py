"""Bridge for Nano XYZ, discrete optical calibration and automatic acquisition."""
import copy
import json
import math
import shutil
from datetime import datetime, timezone
from functools import wraps
from inspect import signature
from uuid import uuid4

import cv2
import numpy as np
from backend import database as db, storage
from backend.analyzer import calibrate_scale_image
from backend.camera import CameraController
from backend.logger import logger
from backend.models import Calibration, DIVISION_PRICES
from backend.stage import StageController, validate_stage_settings
from backend.stage_jobs import StageJobs, check_cancel
from backend.stage_profiles import ProfileStore, atomic_json, profile_point


def bridge(method):
    @wraps(method)
    def call(self, *args, **kwargs):
        try: return {'ok': True, **method(self, *args, **kwargs)}
        except Exception as error:
            logger.exception('Ошибка %s', method.__name__)
            return {'ok': False, 'error': str(error)}
    call.__signature__ = signature(method)
    return call


def stamp():
    return datetime.now(timezone.utc).isoformat()


def synthetic_frame(kind, z):
    """Explicit simulator: neither opens a camera nor represents a measurement."""
    frame = np.full((360, 480, 3), 235, np.uint8)
    if kind == 'profile':
        spacing = 35 + min(z // 100, 25)
        for x in range(35, 450, spacing): cv2.line(frame, (x, 70), (x, 290), (15, 15, 15), 3)
    else:
        cv2.ellipse(frame, (140, 130), (42, 24), 20, 0, 360, (35, 35, 35), -1)
        cv2.ellipse(frame, (330, 235), (32, 48), -25, 0, 360, (35, 35, 35), -1)
    return frame


class StageApiMixin:
    def _init_stage(self):
        self.stage = StageController()
        self.jobs = StageJobs()
        self.profiles = ProfileStore(storage.DATA_DIR)
        self._stage_name = None
        self._acquisition = None
        self._shutting_down = False

    def _idle_stage(self):
        if self.jobs.snapshot()['active']: raise ValueError('Сначала остановите задание стола и дождитесь завершения')
        if self._shutting_down: raise ValueError('Приложение закрывается')

    def _stage_settings(self, name):
        path = storage.DATA_DIR / 'stage_settings.json'
        values = json.loads(path.read_text(encoding='utf-8')) if path.exists() else {}
        if not isinstance(values, dict): raise ValueError('Повреждены настройки стола')
        return validate_stage_settings(values.get(name))

    def _automatic(self, name):
        m = self.registry.get(name)
        if m['type'] != 'AUTOMATIC': raise ValueError('Выберите автоматический микроскоп')
        return m

    def _stage_binding(self, name):
        state = self.stage.snapshot()
        if not state.get('connected') or self._stage_name != name: raise ValueError('Подключите стол выбранного микроскопа')
        settings = self.stage.settings
        return {'machine_id': state.get('machine_id'), 'firmware_config': state.get('config_id'), 'camera_index': self.registry.get(name).get('camera_index'),
                'settings': {k: copy.deepcopy(settings[k]) for k in ('mode','board','driver','travel_steps','steps_per_mm')}}

    def _require_homed(self, name):
        self._stage_binding(name)
        state = self.stage.snapshot()
        if not state.get('homed') or state.get('state') != 'IDLE': raise ValueError('Сначала выполните поиск нуля всех осей')
        return state

    @bridge
    def get_stage_state(self, name: str) -> dict:
        with self._lock:
            self._automatic(name)
            return {'settings': self._stage_settings(name), 'stage': self.stage.snapshot(), 'connected_microscope': self._stage_name,
                    'profiles': self.profiles.list(name), 'job': self.jobs.snapshot(), 'acquisition': copy.deepcopy(self._acquisition)}

    @bridge
    def get_stage_ports(self) -> dict:
        from serial.tools import list_ports
        return {'ports': [{'port': p.device, 'label': f'{p.device} · {p.description}'} for p in list_ports.comports()]}

    @bridge
    def save_stage_settings(self, name: str, settings: dict) -> dict:
        with self._lock:
            self._idle_stage(); self._automatic(name)
            values = validate_stage_settings(settings)
            path = storage.DATA_DIR / 'stage_settings.json'
            all_settings = json.loads(path.read_text(encoding='utf-8')) if path.exists() else {}
            all_settings[name] = values
            atomic_json(path, all_settings)
            # Serial close belongs outside the API lock (STOP may await an ACK).
            self.jobs.start('disconnect', lambda cancel, progress: self._disconnect_stage()) if self.stage.snapshot().get('connected') else None
            return {'settings': values}

    def _disconnect_stage(self):
        self.stage.close()
        self._stage_name = None
        return {}

    @bridge
    def disconnect_stage(self) -> dict:
        with self._lock:
            self._idle_stage()
            return {'job': self.jobs.start('disconnect', lambda cancel, progress: self._disconnect_stage())}

    @bridge
    def stop_stage(self) -> dict:
        self.jobs.cancel()
        if self.stage.snapshot().get('connected'): self.stage.stop()
        return {'stage': self.stage.snapshot(), 'job': self.jobs.snapshot()}

    @bridge
    def get_stage_profile_image(self, profile_id: str, z: int) -> dict:
        with self._lock:
            p = self.profiles.load(profile_id)
            point = next((q for q in p['points'] if q['z'] == z), None)
            if point is None: raise ValueError('Положение Z не найдено')
            checked = self.profiles.root / p['id'] / (str(z) + '-checked.jpg')
            return {'data': storage.image_to_base64(checked if checked.exists() else self.profiles.root / p['id'] / point['image'])}

    def _grid(self, params, state):
        for key in ('x','y','z','columns','rows','dx','dy'):
            if type(params.get(key)) is not int: raise ValueError('Координаты, шаг и размер сетки должны быть целыми')
        x,y,z,columns,rows,dx,dy = (params[k] for k in ('x','y','z','columns','rows','dx','dy'))
        if not 1 <= columns <= 100 or not 1 <= rows <= 100 or columns*rows > 1000 or dx <= 0 or dy <= 0:
            raise ValueError('Сетка: до 1000 кадров, шаг каждой оси больше нуля')
        maxpos = [min(a,b) for a,b in zip(state['max'], self.stage.settings['travel_steps'])]
        if any(not 0 <= v <= m for v,m in zip((x,y,z),maxpos)) or x+(columns-1)*dx > maxpos[0] or y+(rows-1)*dy > maxpos[1]:
            raise ValueError('Сетка выходит за пределы хода стола')
        return [[x+col*dx,y+row*dy,z] for row in range(rows) for col in (range(columns) if row%2==0 else reversed(range(columns)))]

    @bridge
    def start_stage_job(self, name: str, kind: str, params: dict) -> dict:
        with self._lock:
            self._idle_stage(); m = self._automatic(name)
            if not isinstance(params, dict): raise ValueError('Некорректные параметры задания')
            params = copy.deepcopy(params)
            if kind == 'connect':
                settings = self._stage_settings(name)
                if settings['mode'] == 'serial' and not settings['mechanics_confirmed']: raise ValueError('Инженер должен подтвердить параметры механики')
                def connect(cancel, progress):
                    try:
                        check_cancel(cancel)
                        result = self.stage.connect(settings)
                        check_cancel(cancel)
                        self._stage_name = name
                        return result
                    except Exception:
                        self._disconnect_stage(); raise
                return {'job': self.jobs.start(kind, connect)}
            state = self.stage.snapshot()
            if self._stage_name != name or not state.get('connected'): raise ValueError('Подключите стол этого микроскопа')
            if kind == 'home':
                work = lambda cancel, progress: self._motion_job(cancel, lambda: self.stage.home(cancel=cancel))
            elif kind == 'move':
                self._require_homed(name)
                xyz = params.get('xyz')
                if not isinstance(xyz,list) or len(xyz)!=3: raise ValueError('Укажите X, Y и Z в шагах')
                work = lambda cancel, progress: self._motion_job(cancel, lambda: self.stage.move(*xyz, cancel=cancel))
            elif kind in ('profile', 'scan'):
                state = self._require_homed(name)
                if self.stage.settings['mode'] != 'simulator' and m.get('camera_index') is None: raise ValueError('Привяжите камеру в настройках')
                binding = self._stage_binding(name)
                if kind == 'profile':
                    positions = params.get('positions')
                    if not isinstance(positions,list) or not 1<=len(positions)<=100 or any(type(z) is not int or not 0<=z<=min(state['max'][2],self.stage.settings['travel_steps'][2]) for z in positions) or len(set(positions))!=len(positions):
                        raise ValueError('Нужно от 1 до 100 уникальных положений Z в пределах хода')
                    division = next((p for p in DIVISION_PRICES if p.name == params.get('division_price')),None)
                    if division is None or not isinstance(params.get('name'),str) or not params['name'].strip(): raise ValueError('Укажите название профиля и цену деления')
                    work = lambda cancel, progress: self._profile_job(name,params,binding,division,cancel,progress)
                else:
                    grid = self._grid(params,state)
                    profile = self.profiles.load(params.get('profile_id'))
                    if profile['microscope'] != name: raise ValueError('Профиль другого микроскопа')
                    point = next((p for p in profile['points'] if p['z']==params['z']),None)
                    if point is None: raise ValueError('Для выбранного Z нет калибровки')
                    profile_point(profile,params['z'],[point['width'],point['height']],binding)
                    self._check_profile_calibration(profile,point)
                    existing = storage.list_session_images('research')
                    if existing and (not self._acquisition or self._acquisition['profile']['id'] != profile['id'] or self._acquisition['scale'] != point or self._acquisition['binding'] != binding):
                        raise ValueError('Начните новое исследование: серия содержит другой масштаб или ручные снимки')
                    if existing and set(existing) != {f['filename'] for f in self._acquisition['frames']}: raise ValueError('Состав серии изменился. Начните новое исследование')
                    work = lambda cancel, progress: self._scan_job(name,profile,point,binding,grid,cancel,progress)
                self._close_camera()
            else: raise ValueError('Неизвестное задание стола')
            return {'job': self.jobs.start(kind, work)}

    def _motion_job(self, cancel, command):
        try:
            check_cancel(cancel); result = command(); check_cancel(cancel)
            return result
        except Exception:
            if self.stage.snapshot().get('connected'): self.stage.stop()
            raise

    def _job_frame(self, camera, token, kind, z):
        return synthetic_frame(kind,z) if self.stage.settings['mode']=='simulator' else camera.read_fresh(token)

    def _settle(self, cancel):
        if cancel.wait(self.stage.settings['settle_ms']/1000): check_cancel(cancel)
        check_cancel(cancel)
        state = self.stage.snapshot()
        if not state.get('connected') or not state.get('homed') or state.get('state')!='IDLE': raise ValueError('Позиция стола потеряна; снимок отменён')

    def _job_camera(self, name):
        camera = CameraController()
        token = None if self.stage.settings['mode']=='simulator' else camera.open(self.registry.get(name)['camera_index'])
        return camera, token

    def _profile_job(self, name, params, binding, division, cancel, progress):
        identifier = uuid4().hex
        folder = self.profiles.root / identifier
        created = []; activated = False; camera = None
        try:
            camera,token = self._job_camera(name)
            xyz = self.stage.snapshot()['pos']
            points = []; progress(total=len(params['positions']))
            for z in params['positions']:
                self._motion_job(cancel, lambda: self.stage.move(xyz[0],xyz[1],z,cancel=cancel)); self._settle(cancel)
                frame = self._job_frame(camera,token,'profile',z)
                result, outputs = calibrate_scale_image(frame)
                self._settle_position([xyz[0],xyz[1],z])
                check_cancel(cancel)
                h,w = frame.shape[:2]
                storage.write_jpeg(folder/(str(z)+'.jpg'),frame)
                storage.write_jpeg(folder/(str(z)+'-checked.jpg'),outputs['calibrated'])
                points.append({'z':z,'width':w,'height':h,'coefficient':result['coefficient'],'division_um':division.value,
                               'division_price':division.name,'marks_count':result['marks_count'],'image':str(z)+'.jpg','captured_at':stamp()})
                progress(completed=len(points),z=z,preview=self._encode_preview(outputs['calibrated']))
            with self._lock:
                check_cancel(cancel)
                for point in points:
                    check_cancel(cancel)
                    cal = Calibration(name=f"{params['name'].strip()} · Z {point['z']}",microscope=name,coefficient=point['coefficient'],division_price=division.name)
                    point['calibration_id'] = db.save_calibration(cal); created.append(point['calibration_id'])
                    storage.write_jpeg(storage.CALIBRATION_DIR/str(point['calibration_id'])/'sources.jpg',storage.read_image(folder/point['image']))
                profile = {'id':identifier,'name':params['name'].strip(),'microscope':name,'binding':binding,'points':points,
                           'created_at':stamp(),'simulated':self.stage.settings['mode']=='simulator'}
                check_cancel(cancel)
                self.profiles.save(profile); activated = True
            return {'profile':profile}
        except Exception:
            if self.stage.snapshot().get('connected'): self.stage.stop()
            raise
        finally:
            if camera: camera.close()
            if not activated:
                for calid in created: db.delete_calibration(calid); storage.delete_calibration_files(calid)
                shutil.rmtree(folder,ignore_errors=True)

    def _check_profile_calibration(self, profile, point):
        cal = db.get_calibration(point['calibration_id'])
        if not cal or cal.microscope!=profile['microscope'] or cal.coefficient!=point['coefficient'] or cal.division_price!=point['division_price']:
            raise ValueError('Калибровка Z удалена или изменена. Создайте новый профиль Z')
        return cal

    def _scan_job(self, name, profile, point, binding, grid, cancel, progress):
        camera = None
        try:
            camera,token = self._job_camera(name)
            progress(total=len(grid))
            for index, xyz in enumerate(grid):
                self._motion_job(cancel,lambda: self.stage.move(*xyz, cancel=cancel)); self._settle(cancel)
                frame = self._job_frame(camera,token,'scan',xyz[2]); check_cancel(cancel)
                h,w = frame.shape[:2]
                profile_point(profile,xyz[2],[w,h],binding)
                self._settle_position(xyz)
                with self._lock:
                    check_cancel(cancel)
                    self._check_profile_calibration(profile,point)
                    if self._acquisition is None:
                        folder = self.profiles.root / profile['id']
                        scale = storage.read_image(folder / point['image'])
                        if scale is None: raise ValueError('Снимок эталона профиля отсутствует')
                        storage.write_jpeg(storage.SESSION_RES_DIR / 'scale.jpg', scale)
                        checked = folder / (str(point['z']) + '-checked.jpg')
                        if checked.exists(): storage.write_jpeg(storage.SESSION_RES_DIR / 'scale-checked.jpg',storage.read_image(checked))
                    filename = storage.save_session_frame(frame,'research')
                    if self._acquisition is None:
                        self._acquisition = {'version':1,'profile':copy.deepcopy(profile),'scale':copy.deepcopy(point),'binding':copy.deepcopy(binding),
                                             'simulated':self.stage.settings['mode']=='simulator','frames':[]}
                    self._acquisition['frames'].append({'filename':filename,'xyz':xyz[:],'width':w,'height':h,'captured_at':stamp()})
                    revision = self._changed('research')
                progress(completed=index+1,filename=filename,revision=revision,preview=self._encode_preview(frame),calibration_id=point['calibration_id'])
            return {'calibration_id':point['calibration_id'],'revision':revision,'frames':len(grid)}
        except Exception:
            if self.stage.snapshot().get('connected'): self.stage.stop()
            raise
        finally:
            if camera: camera.close()

    def _settle_position(self, xyz):
        state = self.stage.snapshot()
        if not state.get('connected') or not state.get('homed') or state.get('state')!='IDLE' or state.get('pos')!=xyz:
            raise ValueError('Координаты изменились во время съёмки')

    def _assert_acquisition_scale(self, cal):
        if not self._acquisition: return
        point = self._acquisition['scale']; profile = self._acquisition['profile']
        if not cal or cal.id!=point['calibration_id'] or cal.microscope!=profile['microscope'] or cal.coefficient!=point['coefficient'] or cal.division_price!=point['division_price']:
            raise ValueError('Для автоматической серии используйте сохранённую калибровку её Z')
        if set(storage.list_session_images('research'))!={f['filename'] for f in self._acquisition['frames']}:
            raise ValueError('Состав автоматической серии изменился. Начните новое исследование')
