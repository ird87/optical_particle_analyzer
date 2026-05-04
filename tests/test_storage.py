import base64
import shutil
from pathlib import Path

import pytest

import backend.storage as storage

FIXTURES = Path(__file__).parent / 'fixtures'
CAL_SRC  = FIXTURES / 'calibration' / 'sources.jpg'
RES_1    = FIXTURES / 'research' / '1.jpg'


@pytest.fixture(autouse=True)
def patched_paths(tmp_path, monkeypatch):
    """Перенаправляет все пути storage во временную папку."""
    data_dir        = tmp_path / 'data'
    session_dir     = data_dir / 'session'
    res_dir         = session_dir / 'research'
    cal_dir         = session_dir / 'calibration'
    research_dir    = data_dir / 'research'
    calibration_dir = data_dir / 'calibration'

    monkeypatch.setattr(storage, 'DATA_DIR',         data_dir)
    monkeypatch.setattr(storage, 'SESSION_DIR',      session_dir)
    monkeypatch.setattr(storage, 'SESSION_RES_DIR',  res_dir)
    monkeypatch.setattr(storage, 'SESSION_CAL_DIR',  cal_dir)
    monkeypatch.setattr(storage, 'RESEARCH_DIR',     research_dir)
    monkeypatch.setattr(storage, 'CALIBRATION_DIR',  calibration_dir)


# ---------------------------------------------------------------------------
# Очистка сессии
# ---------------------------------------------------------------------------

def test_clear_session():
    storage.clear_session()

    for folder in ('sources', 'contrasted', 'contours', 'analyzed'):
        p = storage.SESSION_RES_DIR / folder
        assert p.exists() and p.is_dir()
        assert list(p.iterdir()) == [], f'{folder} не пуст'

    assert storage.SESSION_CAL_DIR.exists()


# ---------------------------------------------------------------------------
# Сохранение и загрузка файлов исследования
# ---------------------------------------------------------------------------

def test_save_and_load_research_files():
    storage.clear_session()

    # Кладём тестовый файл в сессию
    src = storage.SESSION_RES_DIR / 'sources' / '1.jpg'
    shutil.copy(RES_1, src)

    storage.save_research_files(1)

    # Очищаем сессию и загружаем обратно
    storage.clear_session()
    assert not src.exists()

    storage.load_research_files(1)
    assert src.exists()
    assert src.stat().st_size == RES_1.stat().st_size


# ---------------------------------------------------------------------------
# base64
# ---------------------------------------------------------------------------

def test_image_to_base64():
    result = storage.image_to_base64(CAL_SRC)

    assert result.startswith('data:image/jpeg;base64,')

    b64_part = result.split(',', 1)[1]
    decoded  = base64.b64decode(b64_part)
    assert len(decoded) > 0
    # JPEG magic bytes
    assert decoded[:2] == b'\xff\xd8'
