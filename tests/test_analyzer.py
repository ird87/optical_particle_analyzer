import shutil
from pathlib import Path

import cv2
import pytest

from backend import analyzer

FIXTURES = Path(__file__).parent / 'fixtures'
CAL_SRC  = FIXTURES / 'calibration' / 'sources.jpg'
RES_1    = FIXTURES / 'research' / '1.jpg'
RES_2    = FIXTURES / 'research' / '2.jpg'


def _load(path: Path):
    img = cv2.imread(str(path))
    assert img is not None, f'Не удалось загрузить {path}'
    return img


# ---------------------------------------------------------------------------
# Низкоуровневые функции
# ---------------------------------------------------------------------------

def test_increase_contrast():
    img = _load(RES_1)
    h, w = img.shape[:2]
    result = analyzer.increase_contrast(img.copy())
    assert result.shape[:2] == (h, w)


def test_find_and_draw_contours():
    img = _load(RES_1)
    result = analyzer.find_and_draw_contours(img.copy())
    assert result is not None
    assert result.shape == img.shape


def test_analyze_contours_returns_results():
    img       = _load(RES_1)
    contrasted = analyzer.increase_contrast(img.copy())
    _, results, _ = analyzer.analyze_contours(contrasted)
    assert len(results) > 0
    for r in results:
        for key in ('perimeter', 'area', 'width', 'length', 'dek'):
            assert key in r, f'Отсутствует ключ {key}'


def test_analyze_contours_with_calibration():
    img        = _load(RES_1)
    contrasted = analyzer.increase_contrast(img.copy())

    _, res1, _  = analyzer.analyze_contours(contrasted.copy(),
                                            calibration_coefficient=1.0,
                                            division_price_value=1.0)
    _, res10, _ = analyzer.analyze_contours(contrasted.copy(),
                                            calibration_coefficient=10.0,
                                            division_price_value=1.0)

    assert len(res1) > 0 and len(res10) > 0
    # Периметр масштабируется обратно пропорционально коэффициенту
    ratio = res1[0]['perimeter'] / res10[0]['perimeter']
    assert abs(ratio - 10.0) < 1.0, f'Ожидалось ~10, получено {ratio:.3f}'


# ---------------------------------------------------------------------------
# Пайплайны
# ---------------------------------------------------------------------------

def test_run_calibration_analysis(tmp_path, monkeypatch):
    cal_dir = tmp_path / 'calibration'
    cal_dir.mkdir()
    shutil.copy(CAL_SRC, cal_dir / 'sources.jpg')

    monkeypatch.setattr(analyzer, 'SESSION_CAL_DIR', cal_dir)

    result = analyzer.run_calibration_analysis()

    assert 'coefficient' in result
    assert result['coefficient'] >= 0
    assert (cal_dir / 'contrasted.jpg').exists()
    assert (cal_dir / 'contours.jpg').exists()
    assert (cal_dir / 'calibrated.jpg').exists()


def test_run_research_analysis(tmp_path, monkeypatch):
    res_dir = tmp_path / 'research'
    for folder in ('sources', 'contrasted', 'contours', 'analyzed'):
        (res_dir / folder).mkdir(parents=True)
    shutil.copy(RES_1, res_dir / 'sources' / '1.jpg')
    shutil.copy(RES_2, res_dir / 'sources' / '2.jpg')

    monkeypatch.setattr(analyzer, 'SESSION_RES_DIR', res_dir)

    result = analyzer.run_research_analysis()

    assert 'contours' in result
    assert len(result['contours']) > 0
    assert 'averages' in result
    for folder in ('contrasted', 'contours', 'analyzed'):
        assert (res_dir / folder / '1.jpg').exists(), f'{folder}/1.jpg не создан'
