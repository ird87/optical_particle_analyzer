import shutil
from pathlib import Path

import cv2
import math
import numpy as np
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


def test_pipeline_measures_unannotated_rectangle(tmp_path, monkeypatch):
    for name in ('sources', 'contrasted', 'contours', 'analyzed'):
        (tmp_path / name).mkdir()
    image = np.full((160, 160, 3), 255, np.uint8)
    cv2.rectangle(image, (40, 40), (80, 100), (0, 0, 0), -1)
    cv2.imwrite(str(tmp_path / 'sources' / '1.png'), image)
    monkeypatch.setattr(analyzer, 'SESSION_RES_DIR', tmp_path)
    monkeypatch.setattr(analyzer, 'increase_contrast', lambda image: image)
    result = analyzer.run_research_analysis()['contours']
    assert len(result) == 1
    assert result[0]['area'] == 2400
    assert result[0]['perimeter'] == 200
    assert result[0]['width'] == 40
    assert result[0]['length'] == 60
    assert result[0]['dek'] == 55.28


def test_rendering_does_not_change_measurements_or_merge_neighbors():
    image = np.full((150, 150, 3), 255, np.uint8)
    cv2.rectangle(image, (20, 30), (50, 90), (0, 0, 0), -1)
    cv2.rectangle(image, (53, 30), (83, 90), (0, 0, 0), -1)
    original = image.copy()
    contours = analyzer.extract_particle_contours(image)
    results, _ = analyzer.measure_contours(contours)
    rendered = analyzer.draw_particle_contours(image, contours, results)
    assert len(results) == 2
    assert [r['area'] for r in results] == [1800, 1800]
    assert np.array_equal(image, original)
    assert not np.array_equal(image, rendered)
    assert analyzer.measure_contours(contours)[0] == results


def test_pipeline_outlines_edge_particles_without_measuring_them(tmp_path, monkeypatch):
    for folder in ('sources', 'contrasted', 'contours', 'analyzed'):
        (tmp_path / folder).mkdir()
    image = np.full((200, 260, 3), (180, 90, 50), np.uint8)
    cv2.circle(image, (70, 100), 25, (225, 230, 235), -1)
    cv2.circle(image, (255, 100), 30, (225, 230, 235), -1)
    cv2.imwrite(str(tmp_path / 'sources' / '1.png'), image)
    monkeypatch.setattr(analyzer, 'SESSION_RES_DIR', tmp_path)
    result = analyzer.run_research_analysis(segmentation_options={})
    assert len(result['contours']) == 1
    assert result['diagnostics'][0]['excluded_border'] == 1
    assert result['diagnostics'][0]['border_highlighted'] is True
    rendered = cv2.imread(str(tmp_path / 'analyzed' / '1.png'))
    assert np.any(np.all(rendered[:, 220:] == (0, 165, 255), axis=2))
    assert not np.any(np.all(rendered[:, :120] == (0, 165, 255), axis=2))


def test_particle_numbers_keep_white_outline_on_dark_background():
    image = np.zeros((80, 140, 3), np.uint8)
    rendered = analyzer.draw_particle_contours(image, [], [
        {'contour_number': 10, 'cx': 30, 'cy': 50},
    ])
    preview = cv2.resize(rendered, (70, 40), interpolation=cv2.INTER_AREA)
    assert np.any(np.all(preview > 220, axis=2)), 'Number outline disappears in the preview'
    assert not np.any(image), 'Drawing must not modify the measurement image'


def test_circle_metrics_and_squared_area_scale():
    image = np.full((160, 160, 3), 255, np.uint8)
    cv2.circle(image, (80, 80), 30, (0, 0, 0), -1)
    contours = analyzer.extract_particle_contours(image)
    normal, _ = analyzer.measure_contours(contours)
    scaled, _ = analyzer.measure_contours(contours, calibration_coefficient=10)
    assert normal[0]['area'] == pytest.approx(math.pi * 900, rel=.05)
    assert normal[0]['dek'] == pytest.approx(60, rel=.03)
    for key in ('perimeter', 'width', 'length', 'dek'):
        assert scaled[0][key] == pytest.approx(normal[0][key] / 10, abs=.01)
    assert scaled[0]['area'] == pytest.approx(normal[0]['area'] / 100, abs=.01)


@pytest.mark.parametrize('brightness', [0, 255])
def test_blank_noise_and_border_particles(brightness):
    blank = np.full((100, 100, 3), brightness, np.uint8)
    assert analyzer.extract_particle_contours(blank) == []
    image = np.full((100, 100, 3), 255, np.uint8)
    cv2.rectangle(image, (0, 10), (30, 60), (0, 0, 0), -1)
    cv2.circle(image, (60, 60), 2, (0, 0, 0), -1)
    assert analyzer.extract_particle_contours(image) == []


@pytest.mark.parametrize('value', [0, -1, float('nan'), float('inf')])
@pytest.mark.parametrize('parameter', ['calibration_coefficient', 'division_price_value'])
def test_invalid_scale_rejected(value, parameter):
    with pytest.raises(ValueError):
        analyzer.measure_contours([], **{parameter: value})


@pytest.mark.parametrize('xs', [[0,10,20,40,50,60], [0,10,20,25,30,40,50]])
def test_scale_spacing_resists_missing_and_false_stripes(xs):
    assert analyzer.estimate_scale_spacing(xs) == 10


@pytest.mark.parametrize('xs', [[], [0,10], [0,4,14,39,79], [10,10,10]])
def test_scale_spacing_rejects_insufficient_or_inconsistent_stripes(xs):
    with pytest.raises(ValueError):
        analyzer.estimate_scale_spacing(xs)


def test_calibration_detects_known_pitch(tmp_path, monkeypatch):
    image = np.full((200, 300, 3), 255, np.uint8)
    for x in range(40, 261, 20):
        cv2.line(image, (x, 40), (x, 160), (0, 0, 0), 2)
    cv2.imwrite(str(tmp_path / 'sources.jpg'), image)
    monkeypatch.setattr(analyzer, 'SESSION_CAL_DIR', tmp_path)
    assert analyzer.run_calibration_analysis()['coefficient'] == pytest.approx(20, abs=.5)


@pytest.mark.parametrize('orientation', ['horizontal', 'vertical'])
@pytest.mark.parametrize('red_background', [False, True])
def test_calibration_detects_five_black_ticks_with_connected_ruler(tmp_path, monkeypatch, orientation, red_background):
    image = np.full((320, 480, 3), (45, 80, 170) if red_background else (230, 230, 230), np.uint8)
    cv2.line(image, (30, 0), (30, 319), (15, 15, 15), 6)
    for y, length in zip([40, 100, 160, 220, 280], [280, 220, 220, 220, 280]):
        cv2.line(image, (30, y), (length, y), (15, 15, 15), 6)
    if orientation == 'vertical':
        image = cv2.rotate(image, cv2.ROTATE_90_CLOCKWISE)
    cv2.imwrite(str(tmp_path / 'sources.jpg'), image)
    monkeypatch.setattr(analyzer, 'SESSION_CAL_DIR', tmp_path)
    result = analyzer.run_calibration_analysis()
    assert result['coefficient'] == pytest.approx(60, abs=1)
    assert result['orientation'] == orientation
    assert result['marks_count'] >= 4


def test_calibration_handles_black_ticks_on_red_background_with_glare(tmp_path, monkeypatch):
    image = np.full((480, 640, 3), (35, 80, 155), np.float32)
    cv2.line(image, (20, 0), (20, 479), (10, 10, 10), 12)
    for y, length in zip([-5, 115, 235, 355, 475], [330, 420, 330, 330, 330]):
        cv2.line(image, (20, y), (length, y), (12, 12, 12), 22)
    yy, xx = np.mgrid[:480, :640]
    glare = .65 * np.exp(-((xx - 170) ** 2 + (yy - 410) ** 2) / (2 * 140 ** 2))
    image = image * (1 - glare[:, :, None]) + 255 * glare[:, :, None]
    image += np.random.default_rng(42).normal(0, 5, image.shape)
    image = np.clip(image, 0, 255).astype(np.uint8)
    cv2.imwrite(str(tmp_path / 'sources.jpg'), image)
    monkeypatch.setattr(analyzer, 'SESSION_CAL_DIR', tmp_path)
    result = analyzer.run_calibration_analysis()
    assert result['coefficient'] == pytest.approx(120, abs=2)
    assert result['orientation'] == 'horizontal'


def test_calibration_rejects_only_three_horizontal_ticks(tmp_path, monkeypatch):
    image = np.full((240, 400, 3), 240, np.uint8)
    for y in [40, 100, 160]:
        cv2.line(image, (40, y), (320, y), (0, 0, 0), 6)
    cv2.imwrite(str(tmp_path / 'sources.jpg'), image)
    monkeypatch.setattr(analyzer, 'SESSION_CAL_DIR', tmp_path)
    with pytest.raises(ValueError):
        analyzer.run_calibration_analysis()


@pytest.mark.parametrize('orientation', ['horizontal', 'vertical'])
@pytest.mark.parametrize('thickness', [26, 30, 36, 40])
@pytest.mark.parametrize('count', [3, 4, 5])
def test_broad_tick_edges_are_not_counted_as_separate_ticks(tmp_path, monkeypatch, orientation, thickness, count):
    image = np.full((360, 480, 3), 240, np.uint8)
    for y in range(40, 40 + 60 * count, 60):
        cv2.line(image, (40, y), (380, y), (0, 0, 0), thickness)
    if orientation == 'vertical':
        image = cv2.rotate(image, cv2.ROTATE_90_CLOCKWISE)
    cv2.imwrite(str(tmp_path / 'sources.jpg'), image)
    monkeypatch.setattr(analyzer, 'SESSION_CAL_DIR', tmp_path)
    if count < 4:
        with pytest.raises(ValueError):
            analyzer.run_calibration_analysis()
    else:
        result = analyzer.run_calibration_analysis()
        assert result['coefficient'] == pytest.approx(60, abs=1)
        assert result['marks_count'] == count
        assert result['orientation'] == orientation


@pytest.mark.parametrize('pitch', [6, 12])
def test_calibration_detects_dense_horizontal_scale(tmp_path, monkeypatch, pitch):
    image = np.full((240, 400, 3), 240, np.uint8)
    cv2.line(image, (40, 0), (40, 239), (0, 0, 0), 2)
    for y in range(30, 211, pitch):
        cv2.line(image, (40, y), (310, y), (0, 0, 0), 1)
    cv2.imwrite(str(tmp_path / 'sources.jpg'), image)
    monkeypatch.setattr(analyzer, 'SESSION_CAL_DIR', tmp_path)
    assert analyzer.run_calibration_analysis()['coefficient'] == pytest.approx(pitch, abs=.5)


@pytest.mark.parametrize('positions', [[40, 85, 170, 260], [40, 100, 160]])
def test_irregular_red_ruler_is_not_accepted(tmp_path, monkeypatch, positions):
    image = np.full((320, 480, 3), (30, 80, 170), np.uint8)
    for y in positions:
        cv2.line(image, (40, y), (310, y), (0, 0, 0), 6)
    cv2.imwrite(str(tmp_path / 'sources.jpg'), image)
    monkeypatch.setattr(analyzer, 'SESSION_CAL_DIR', tmp_path)
    with pytest.raises(ValueError):
        analyzer.run_calibration_analysis()


def test_calibration_rejects_empty_image(tmp_path, monkeypatch):
    cv2.imwrite(str(tmp_path / 'sources.jpg'), np.full((150, 150, 3), 255, np.uint8))
    monkeypatch.setattr(analyzer, 'SESSION_CAL_DIR', tmp_path)
    with pytest.raises(ValueError):
        analyzer.run_calibration_analysis()


@pytest.mark.parametrize('foreground,background', [(80,210), (155,230), (30,100)])
def test_otsu_measures_particle_at_different_exposures(foreground, background):
    image = np.full((200, 200, 3), background, np.uint8)
    cv2.rectangle(image, (60, 60), (100, 120), (foreground,) * 3, -1)
    contours = analyzer.extract_particle_contours(analyzer.increase_contrast(image), 'otsu')
    results, _ = analyzer.measure_contours(contours)
    assert len(results) == 1
    assert results[0]['area'] == pytest.approx(2400, rel=.06)


def test_comparison_cli_writes_metrics_and_previews(tmp_path):
    import subprocess
    import sys
    import json
    result = subprocess.run([sys.executable, 'scripts/compare_segmentation.py', '--output', str(tmp_path)],
                            capture_output=True, text=True)
    assert result.returncode == 0, result.stderr
    report = json.loads((tmp_path / 'metrics.json').read_text())
    assert 'bright' in report['synthetic']
    assert report['synthetic']['bright']['otsu']['count'] == 1
    assert 'area_error' in report['synthetic']['bright']['otsu']
    assert len(report['fixtures']) == 2
    assert list(tmp_path.glob('*.png'))


def test_pipeline_rejects_output_write_failure(tmp_path, monkeypatch):
    for name in ('sources','contrasted','contours','analyzed'):
        (tmp_path/name).mkdir()
    image = np.full((100,100,3),255,np.uint8)
    cv2.rectangle(image,(20,20),(60,60),(0,0,0),-1)
    cv2.imwrite(str(tmp_path/'sources/1.jpg'),image)
    monkeypatch.setattr(analyzer,'SESSION_RES_DIR',tmp_path)
    monkeypatch.setattr(cv2,'imencode',lambda *args:(False,None))
    with pytest.raises(OSError):
        analyzer.run_research_analysis()
