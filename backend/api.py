import base64
from pathlib import Path

import backend.database as db
import backend.storage as storage
from backend.analyzer import run_calibration_analysis, run_research_analysis
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


class Api:
    """Публичные методы этого класса вызываются из JS через window.pywebview.api.*"""

    def __init__(self):
        # id=0 означает «ещё не сохранено»
        self.session = {'research_id': 0, 'calibration_id': 0}

    # -----------------------------------------------------------------------
    # Управление сессией
    # -----------------------------------------------------------------------

    def new_research(self) -> dict:
        logger.info('new_research')
        try:
            storage.clear_session_research()
            self.session['research_id'] = 0
            return {'ok': True}
        except Exception:
            logger.exception('Ошибка new_research')
            return {'ok': False}

    def new_calibration(self) -> dict:
        logger.info('new_calibration')
        try:
            storage.clear_session_calibration()
            self.session['calibration_id'] = 0
            return {'ok': True}
        except Exception:
            logger.exception('Ошибка new_calibration')
            return {'ok': False}

    # -----------------------------------------------------------------------
    # Работа с изображениями
    # -----------------------------------------------------------------------

    def upload_image(self, filename: str, b64_data: str, context: str) -> dict:
        logger.info(f'upload_image filename={filename} context={context}')
        try:
            # Убираем data URI префикс если есть
            if ',' in b64_data:
                b64_data = b64_data.split(',', 1)[1]
            raw = base64.b64decode(b64_data)

            if context == 'calibration':
                path = storage.SESSION_CAL_DIR / 'sources.jpg'
                storage.SESSION_CAL_DIR.mkdir(parents=True, exist_ok=True)
            else:
                path = storage.SESSION_RES_DIR / 'sources' / filename
                (storage.SESSION_RES_DIR / 'sources').mkdir(parents=True, exist_ok=True)

            path.write_bytes(raw)
            return {'ok': True, 'filename': filename}
        except Exception:
            logger.exception(f'Ошибка upload_image filename={filename}')
            return {'ok': False}

    def delete_image(self, filename: str, context: str) -> dict:
        logger.info(f'delete_image filename={filename} context={context}')
        try:
            if context == 'calibration':
                for name in ('sources.jpg', 'contrasted.jpg', 'contours.jpg', 'calibrated.jpg'):
                    p = storage.SESSION_CAL_DIR / name
                    if p.exists():
                        p.unlink()
            else:
                for folder in ('sources', 'contrasted', 'contours', 'analyzed'):
                    p = storage.SESSION_RES_DIR / folder / filename
                    if p.exists():
                        p.unlink()
            return {'ok': True}
        except Exception:
            logger.exception(f'Ошибка delete_image filename={filename}')
            return {'ok': False}

    def list_images(self, context: str) -> dict:
        logger.info(f'list_images context={context}')
        try:
            files = storage.list_session_images(context)
            return {'ok': True, 'files': files}
        except Exception:
            logger.exception('Ошибка list_images')
            return {'ok': False, 'files': []}

    def get_image(self, filename: str, folder: str, context: str) -> dict:
        logger.info(f'get_image filename={filename} folder={folder} context={context}')
        try:
            b64 = storage.get_session_image_b64(filename, folder, context)
            return {'ok': True, 'data': b64}
        except Exception:
            logger.exception(f'Ошибка get_image filename={filename}')
            return {'ok': False, 'data': ''}

    # -----------------------------------------------------------------------
    # Выполнение анализа
    # -----------------------------------------------------------------------

    def execute_research(self, calibration_id: int) -> dict:
        logger.info(f'execute_research calibration_id={calibration_id}')
        try:
            coeff, division = 1.0, 1.0
            if calibration_id and calibration_id > 0:
                cal = db.get_calibration(calibration_id)
                if cal:
                    coeff = cal.coefficient
                    division = float(cal.division_price.split()[0])

            result = run_research_analysis(coeff, division)
            return {'ok': True, **result}
        except Exception:
            logger.exception('Ошибка execute_research')
            return {'ok': False, 'contours': [], 'averages': {}}

    def execute_calibration(self) -> dict:
        logger.info('execute_calibration')
        try:
            result = run_calibration_analysis()
            return {'ok': True, **result}
        except Exception:
            logger.exception('Ошибка execute_calibration')
            return {'ok': False, 'coefficient': 0.0}

    # -----------------------------------------------------------------------
    # Калибровки
    # -----------------------------------------------------------------------

    def get_calibrations(self) -> dict:
        logger.info('get_calibrations')
        try:
            return {'ok': True, 'calibrations': [_cal_to_dict(c) for c in db.get_all_calibrations()]}
        except Exception:
            logger.exception('Ошибка get_calibrations')
            return {'ok': False, 'calibrations': []}

    def get_calibration(self, calibration_id: int) -> dict:
        logger.info(f'get_calibration id={calibration_id}')
        try:
            cal = db.get_calibration(calibration_id)
            return {'ok': True, 'calibration': _cal_to_dict(cal)} if cal else {'ok': False}
        except Exception:
            logger.exception(f'Ошибка get_calibration id={calibration_id}')
            return {'ok': False}

    def save_calibration(self, data: dict) -> dict:
        logger.info(f'save_calibration id={data.get("id", 0)} name={data.get("name")}')
        try:
            cal = Calibration(
                id=data.get('id', 0),
                name=data['name'],
                microscope=data['microscope'],
                coefficient=data['coefficient'],
                division_price=data['division_price'],
            )
            cal_id = db.save_calibration(cal)
            storage.save_calibration_files(cal_id)
            self.session['calibration_id'] = cal_id
            return {'ok': True, 'id': cal_id}
        except Exception:
            logger.exception('Ошибка save_calibration')
            return {'ok': False}

    def load_calibration(self, calibration_id: int) -> dict:
        logger.info(f'load_calibration id={calibration_id}')
        try:
            cal = db.get_calibration(calibration_id)
            if not cal:
                return {'ok': False}
            storage.load_calibration_files(calibration_id)
            self.session['calibration_id'] = calibration_id
            files = storage.list_session_images('calibration')
            return {'ok': True, 'calibration': _cal_to_dict(cal), 'files': files}
        except Exception:
            logger.exception(f'Ошибка load_calibration id={calibration_id}')
            return {'ok': False}

    def delete_calibration(self, calibration_id: int) -> dict:
        logger.info(f'delete_calibration id={calibration_id}')
        try:
            db.delete_calibration(calibration_id)
            storage.delete_calibration_files(calibration_id)
            return {'ok': True}
        except Exception:
            logger.exception(f'Ошибка delete_calibration id={calibration_id}')
            return {'ok': False}

    # -----------------------------------------------------------------------
    # Исследования
    # -----------------------------------------------------------------------

    def get_researches(self) -> dict:
        logger.info('get_researches')
        try:
            return {'ok': True, 'researches': [_res_to_dict(r) for r in db.get_all_researches()]}
        except Exception:
            logger.exception('Ошибка get_researches')
            return {'ok': False, 'researches': []}

    def get_research(self, research_id: int) -> dict:
        logger.info(f'get_research id={research_id}')
        try:
            res = db.get_research(research_id)
            if not res:
                return {'ok': False}
            contours = db.get_contours(research_id)
            return {'ok': True, 'research': _res_to_dict(res, contours)}
        except Exception:
            logger.exception(f'Ошибка get_research id={research_id}')
            return {'ok': False}

    def save_research(self, data: dict) -> dict:
        logger.info(f'save_research id={data.get("id", 0)} name={data.get("name")}')
        try:
            res = Research(
                id=data.get('id', 0),
                name=data['name'],
                employee=data['employee'],
                microscope=data['microscope'],
                calibration_id=data.get('calibration_id'),
                average_perimeter=data['average_perimeter'],
                average_area=data['average_area'],
                average_width=data['average_width'],
                average_length=data['average_length'],
                average_dek=data['average_dek'],
            )
            res_id = db.save_research(res)

            contours = [
                ContourData(
                    research_id=res_id,
                    contour_number=c['contour_number'],
                    perimeter=c['perimeter'],
                    area=c['area'],
                    width=c['width'],
                    length=c['length'],
                    dek=c['dek'],
                )
                for c in data.get('contours', [])
            ]
            db.save_contours(res_id, contours)
            storage.save_research_files(res_id)
            self.session['research_id'] = res_id
            return {'ok': True, 'id': res_id}
        except Exception:
            logger.exception('Ошибка save_research')
            return {'ok': False}

    def load_research(self, research_id: int) -> dict:
        logger.info(f'load_research id={research_id}')
        try:
            res = db.get_research(research_id)
            if not res:
                return {'ok': False}
            contours = db.get_contours(research_id)
            storage.load_research_files(research_id)
            self.session['research_id'] = research_id
            files = storage.list_session_images('research')
            return {
                'ok': True,
                'research': _res_to_dict(res, contours),
                'files': files,
            }
        except Exception:
            logger.exception(f'Ошибка load_research id={research_id}')
            return {'ok': False}

    def delete_research(self, research_id: int) -> dict:
        logger.info(f'delete_research id={research_id}')
        try:
            db.delete_research(research_id)
            storage.delete_research_files(research_id)
            return {'ok': True}
        except Exception:
            logger.exception(f'Ошибка delete_research id={research_id}')
            return {'ok': False}

    # -----------------------------------------------------------------------
    # Справочники
    # -----------------------------------------------------------------------

    def get_microscopes(self) -> dict:
        return {'ok': True, 'microscopes': [m.to_dict() for m in MICROSCOPES]}

    def get_division_prices(self) -> dict:
        return {'ok': True, 'division_prices': [d.to_dict() for d in DIVISION_PRICES]}
