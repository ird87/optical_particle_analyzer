import base64
import json
import shutil
import os
import tempfile
from pathlib import Path

import cv2
import numpy as np

from backend.logger import logger, ROOT_DIR

# ---------------------------------------------------------------------------
# Пути
# ---------------------------------------------------------------------------

DATA_DIR         = ROOT_DIR / 'data'
SESSION_DIR      = DATA_DIR / 'session'
SESSION_RES_DIR  = SESSION_DIR / 'research'
SESSION_CAL_DIR  = SESSION_DIR / 'calibration'
RESEARCH_DIR     = DATA_DIR / 'research'
CALIBRATION_DIR  = DATA_DIR / 'calibration'

_RESEARCH_FOLDERS   = ('sources', 'contrasted', 'contours', 'analyzed')
_CALIBRATION_FILES  = ('sources.jpg', 'contrasted.jpg', 'contours.jpg', 'calibrated.jpg')


# ---------------------------------------------------------------------------
# Вспомогательные
# ---------------------------------------------------------------------------

def _recreate_dir(path: Path) -> None:
    if path.exists():
        shutil.rmtree(path)
    path.mkdir(parents=True)


def _copy_dir(src: Path, dst: Path) -> None:
    if src.exists():
        shutil.copytree(src, dst, dirs_exist_ok=True)
        logger.debug(f'Скопирована папка {src} -> {dst}')


def _copy_file(src: Path, dst: Path) -> None:
    if src.exists():
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src, dst)
        logger.debug(f'Скопирован файл {src.name} -> {dst}')


# ---------------------------------------------------------------------------
# Очистка сессии
# ---------------------------------------------------------------------------

def clear_session_research() -> None:
    for folder in _RESEARCH_FOLDERS:
        _recreate_dir(SESSION_RES_DIR / folder)
    logger.debug('Сессия исследования очищена')


def clear_session_calibration() -> None:
    _recreate_dir(SESSION_CAL_DIR)
    logger.debug('Сессия калибровки очищена')


def clear_session() -> None:
    clear_session_research()
    clear_session_calibration()
    logger.debug('Сессия полностью очищена')


def clear_research_outputs() -> None:
    for folder in ('contrasted', 'contours', 'analyzed'):
        _recreate_dir(SESSION_RES_DIR / folder)


def write_jpeg(path: Path, frame: np.ndarray) -> None:
    """Encode before replacing an existing source, including on Unicode paths."""
    write_image(path, frame, '.jpg')


def read_image(path: Path):
    raw = path.read_bytes()
    return cv2.imdecode(np.frombuffer(raw, np.uint8), cv2.IMREAD_COLOR) if raw else None


def write_image(path: Path, frame: np.ndarray, extension: str | None = None) -> None:
    success, encoded = cv2.imencode(extension or path.suffix, frame)
    if not success:
        raise OSError('Не удалось закодировать снимок')
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = None
    try:
        with tempfile.NamedTemporaryFile(dir=path.parent, delete=False) as stream:
            temporary = Path(stream.name)
            stream.write(encoded.tobytes())
        os.replace(temporary, path)
    finally:
        if temporary and temporary.exists():
            temporary.unlink()


def clear_calibration_outputs() -> None:
    for filename in _CALIBRATION_FILES[1:]:
        (SESSION_CAL_DIR / filename).unlink(missing_ok=True)


def save_session_frame(frame: np.ndarray, context: str) -> str:
    if context == 'research':
        folder = SESSION_RES_DIR / 'sources'
        folder.mkdir(parents=True, exist_ok=True)
        index = max((int(path.stem) for path in folder.iterdir() if path.stem.isdigit()), default=0) + 1
        filename = f'{index}.jpg'
        write_jpeg(folder / filename, frame)
    elif context == 'calibration':
        filename = 'sources.jpg'
        write_jpeg(SESSION_CAL_DIR / filename, frame)
        clear_calibration_outputs()
    else:
        raise ValueError('Неизвестный контекст съёмки')
    return filename


# ---------------------------------------------------------------------------
# Исследования
# ---------------------------------------------------------------------------

def save_research_files(research_id: int) -> None:
    dst_root = RESEARCH_DIR / str(research_id)
    _recreate_dir(dst_root)
    for folder in _RESEARCH_FOLDERS:
        _copy_dir(SESSION_RES_DIR / folder, dst_root / folder)
    logger.debug(f'Файлы исследования id={research_id} сохранены')


def load_research_files(research_id: int) -> None:
    clear_session_research()
    src_root = RESEARCH_DIR / str(research_id)
    for folder in _RESEARCH_FOLDERS:
        _copy_dir(src_root / folder, SESSION_RES_DIR / folder)
    logger.debug(f'Файлы исследования id={research_id} загружены в сессию')


def write_research_metadata(research_id: int, metadata: dict) -> None:
    destination = RESEARCH_DIR / str(research_id) / 'analysis.json'
    destination.parent.mkdir(parents=True, exist_ok=True)
    temporary = None
    try:
        with tempfile.NamedTemporaryFile(mode='w', encoding='utf-8', dir=destination.parent, delete=False) as stream:
            temporary = Path(stream.name)
            json.dump(metadata, stream, ensure_ascii=False, indent=2)
        os.replace(temporary, destination)
    finally:
        if temporary and temporary.exists():
            temporary.unlink()


def read_research_metadata(research_id: int) -> dict:
    path = RESEARCH_DIR / str(research_id) / 'analysis.json'
    if not path.exists():
        return {}
    try:
        value = json.loads(path.read_text(encoding='utf-8'))
        return value if isinstance(value, dict) else {}
    except (OSError, ValueError):
        logger.warning('Не удалось прочитать параметры анализа исследования %s', research_id)
        return {}


def delete_research_files(research_id: int) -> None:
    path = RESEARCH_DIR / str(research_id)
    if path.exists():
        shutil.rmtree(path)
        logger.debug(f'Папка исследования id={research_id} удалена')


# ---------------------------------------------------------------------------
# Калибровки
# ---------------------------------------------------------------------------

def save_calibration_files(calibration_id: int) -> None:
    dst_root = CALIBRATION_DIR / str(calibration_id)
    dst_root.mkdir(parents=True, exist_ok=True)
    for fname in _CALIBRATION_FILES:
        _copy_file(SESSION_CAL_DIR / fname, dst_root / fname)
    logger.debug(f'Файлы калибровки id={calibration_id} сохранены')


def load_calibration_files(calibration_id: int) -> None:
    clear_session_calibration()
    src_root = CALIBRATION_DIR / str(calibration_id)
    for fname in _CALIBRATION_FILES:
        _copy_file(src_root / fname, SESSION_CAL_DIR / fname)
    logger.debug(f'Файлы калибровки id={calibration_id} загружены в сессию')


def delete_calibration_files(calibration_id: int) -> None:
    path = CALIBRATION_DIR / str(calibration_id)
    if path.exists():
        shutil.rmtree(path)
        logger.debug(f'Папка калибровки id={calibration_id} удалена')


# ---------------------------------------------------------------------------
# Изображения
# ---------------------------------------------------------------------------

def list_session_images(context: str) -> list[str]:
    """Возвращает список имён файлов в session/<context>/sources/."""
    if context == 'research':
        folder = SESSION_RES_DIR / 'sources'
    else:
        folder = SESSION_CAL_DIR
    if not folder.exists():
        return []
    return sorted(f.name for f in folder.iterdir() if f.is_file())


def image_to_base64(path: Path) -> str:
    """Читает файл и возвращает data URI для использования в <img src=...>."""
    with open(path, 'rb') as f:
        data = base64.b64encode(f.read()).decode('utf-8')
    return f'data:image/jpeg;base64,{data}'


def get_session_image_b64(filename: str, folder: str, context: str) -> str:
    """
    Возвращает base64 изображения из сессии.
    context: 'research' | 'calibration'
    folder:  'sources' | 'contrasted' | 'contours' | 'analyzed'  (для research)
             имя файла без папки                                   (для calibration)
    """
    if context == 'research':
        path = SESSION_RES_DIR / folder / filename
    else:
        path = SESSION_CAL_DIR / filename
    if not path.exists():
        return ''
    return image_to_base64(path)
