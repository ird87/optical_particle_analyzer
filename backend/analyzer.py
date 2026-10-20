import math

import cv2
import numpy as np

from backend.logger import logger
from backend.segmentation import segment_particles, validate_options
from backend.storage import (
    SESSION_CAL_DIR,
    SESSION_RES_DIR,
    read_image,
    write_image,
)

# ---------------------------------------------------------------------------
# Низкоуровневые функции обработки
# ---------------------------------------------------------------------------

def increase_contrast(image: np.ndarray) -> np.ndarray:
    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8))
    contrasted = clahe.apply(gray)
    blurred = cv2.GaussianBlur(contrasted, (5, 5), 0)
    return cv2.cvtColor(blurred, cv2.COLOR_GRAY2BGR)


def extract_particle_contours(image: np.ndarray, threshold_mode: str = 'fixed') -> list[np.ndarray]:
    if threshold_mode not in ('fixed', 'otsu'):
        raise ValueError('Неизвестный метод выделения частиц')
    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    mode = cv2.THRESH_BINARY_INV
    if threshold_mode == 'otsu':
        mode |= cv2.THRESH_OTSU
    _, mask = cv2.threshold(gray, 127 if threshold_mode == 'fixed' else 0, 255, mode)
    contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    h, w = gray.shape
    filtered = []
    for contour in contours:
        x, y, cw, ch = cv2.boundingRect(contour)
        if cv2.contourArea(contour) > 100 and x > 0 and y > 0 and x + cw < w and y + ch < h:
            filtered.append(contour)
    return sorted(filtered, key=lambda contour: (cv2.boundingRect(contour)[1], cv2.boundingRect(contour)[0]))


def _validate_scale(coeff: float, division: float) -> None:
    if not all(math.isfinite(value) and value > 0 for value in (coeff, division)):
        raise ValueError('Коэффициент и цена деления должны быть конечными положительными числами')


def pixels_to_real_units(pixels: float, coeff: float, division: float) -> float:
    _validate_scale(coeff, division)
    return pixels / coeff * division


def measure_contours(
    contours: list[np.ndarray], start_number: int = 1,
    calibration_coefficient: float = 1.0, division_price_value: float = 1.0,
) -> tuple[list[dict], int]:
    _validate_scale(calibration_coefficient, division_price_value)
    scale = division_price_value / calibration_coefficient
    results = []
    for contour in contours:
        moments = cv2.moments(contour)
        area = cv2.contourArea(contour)
        width, length = sorted(cv2.minAreaRect(contour)[1])
        results.append({
            'contour_number': start_number,
            'perimeter': round(cv2.arcLength(contour, True) * scale, 2),
            'area': round(area * scale ** 2, 2),
            'width': round(width * scale, 2),
            'length': round(length * scale, 2),
            'dek': round(math.sqrt(4 * area / math.pi) * scale, 2),
            'cx': int(moments['m10'] / moments['m00']) if moments['m00'] else 0,
            'cy': int(moments['m01'] / moments['m00']) if moments['m00'] else 0,
        })
        start_number += 1
    return results, start_number


def _draw_outlined_labels(image, labels, font_scale, thickness, outline_width):
    if not labels:
        return
    # OpenCV 5 maps legacy text thickness to font weight. Two putText calls
    # no longer create an outline, so expand the actual glyph mask instead.
    mask = np.zeros(image.shape[:2], np.uint8)
    for text, position in labels:
        cv2.putText(mask, text, position, cv2.FONT_HERSHEY_SIMPLEX,
                    font_scale, 255, thickness)
    size = 2 * outline_width + 1
    kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (size, size))
    outline = cv2.dilate(mask, kernel)
    image[outline > 0] = (255, 255, 255)
    for text, position in labels:
        cv2.putText(image, text, position, cv2.FONT_HERSHEY_SIMPLEX,
                    font_scale, (0, 0, 0), thickness)


def draw_particle_contours(image: np.ndarray, contours: list[np.ndarray], results: list[dict] | None = None) -> np.ndarray:
    rendered = image.copy()
    cv2.drawContours(rendered, contours, -1, (0, 0, 255), 2)
    labels = [(str(result['contour_number']), (result['cx'], result['cy']))
              for result in results or []]
    _draw_outlined_labels(rendered, labels, font_scale=.5, thickness=2, outline_width=2)
    return rendered


def find_and_draw_contours(image: np.ndarray) -> np.ndarray:
    return draw_particle_contours(image, extract_particle_contours(image))


def analyze_contours(
    image: np.ndarray, start_number: int = 1,
    calibration_coefficient: float = 1.0, division_price_value: float = 1.0,
) -> tuple[np.ndarray, list[dict], int]:
    contours = extract_particle_contours(image)
    results, next_number = measure_contours(contours, start_number, calibration_coefficient, division_price_value)
    return draw_particle_contours(image, contours, results), results, next_number


# ---------------------------------------------------------------------------
# Функции калибровки
# ---------------------------------------------------------------------------

def _dark_stroke_mask(gray: np.ndarray, vertical: bool) -> np.ndarray:
    # Estimate the light background across the strokes. Subtracting the image
    # retains the filled dark stroke even under slowly varying illumination;
    # adaptive thresholding can instead split a broad stroke into two edges.
    across = gray.shape[1] if vertical else gray.shape[0]
    size = max(31, across // 3)
    kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (size, 1) if vertical else (1, size))
    smooth = cv2.GaussianBlur(gray, (5, 5), 0)
    dark = cv2.morphologyEx(smooth, cv2.MORPH_BLACKHAT, kernel)
    return cv2.threshold(dark, 0, 255, cv2.THRESH_BINARY | cv2.THRESH_OTSU)[1]


def find_vertical_lines(img_bgr: np.ndarray) -> np.ndarray:
    return _dark_stroke_mask(cv2.cvtColor(img_bgr, cv2.COLOR_BGR2GRAY), vertical=True)


def detect_black_strips_left_edges(binary: np.ndarray, draw_img: np.ndarray) -> list[int]:
    contours, _ = cv2.findContours(binary, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    h, w = draw_img.shape[:2]
    xs = []

    for cnt in contours:
        pts = cnt.reshape(-1, 2)
        x_min = int(np.min(pts[:, 0]))
        cw = int(np.max(pts[:, 0])) - x_min
        ch = int(np.max(pts[:, 1])) - int(np.min(pts[:, 1]))

        if cw > w * 0.7 or ch < 5:
            continue
        if ch / (cw + 1) < 6.0:
            continue

        cv2.drawContours(draw_img, [cnt], -1, (0, 0, 255), cv2.FILLED)
        xs.append(x_min)

    xs.sort()
    return xs


# ---------------------------------------------------------------------------
# Пайплайны
# ---------------------------------------------------------------------------

def run_research_analysis(
    calibration_coefficient: float = 1.0,
    division_price_value: float = 1.0,
    *, threshold_mode: str = 'fixed', segmentation_options: dict | None = None,
) -> dict:
    """
    Обрабатывает все файлы из session/research/sources/.
    Результаты пишет в contrasted/, contours/, analyzed/.
    Возвращает {'contours': [...], 'averages': {...}}.
    """
    _validate_scale(calibration_coefficient, division_price_value)
    sources_dir    = SESSION_RES_DIR / 'sources'
    contrasted_dir = SESSION_RES_DIR / 'contrasted'
    contours_dir   = SESSION_RES_DIR / 'contours'
    analyzed_dir   = SESSION_RES_DIR / 'analyzed'

    options = validate_options(segmentation_options) if segmentation_options is not None else None
    diagnostics = []
    all_contours: list[dict] = []
    contour_number = 1

    files = sorted(sources_dir.iterdir()) if sources_dir.exists() else []
    logger.info(
        f'Анализ: {len(files)} файлов, '
        f'коэфф={calibration_coefficient}, деление={division_price_value}'
    )

    for src_path in files:
        if not src_path.is_file():
            continue
        logger.info(f'Обработка {src_path.name}')

        image = read_image(src_path)
        if image is None:
            logger.error(f'Не удалось прочитать {src_path.name}')
            continue

        contrasted = increase_contrast(image.copy())
        write_image(contrasted_dir / src_path.name, contrasted)

        if options is None:
            detected = extract_particle_contours(contrasted, threshold_mode)
            diagnostic = {'method': 'legacy_' + threshold_mode, 'excluded_border': 0, 'excluded_small': 0, 'split_count': 0}
        else:
            segmented = segment_particles(image, options)
            detected = segmented['contours']
            diagnostic = {key: segmented[key] for key in ('method', 'excluded_border', 'excluded_small', 'split_count')}
        diagnostics.append({'filename': src_path.name, 'count': len(detected), **diagnostic})
        contours, contour_number = measure_contours(
            detected, contour_number, calibration_coefficient, division_price_value,
        )
        rendering = contrasted if options is None else image
        contoured = draw_particle_contours(rendering, detected)
        write_image(contours_dir / src_path.name, contoured)
        analyzed = draw_particle_contours(rendering, detected, contours)
        write_image(analyzed_dir / src_path.name, analyzed)

        logger.info(f'{src_path.name}: найдено {len(contours)} контуров')
        all_contours.extend(contours)

    averages: dict[str, float] = {'perimeter': 0, 'area': 0, 'width': 0, 'length': 0, 'dek': 0}
    if all_contours:
        for key in averages:
            averages[key] = round(sum(c[key] for c in all_contours) / len(all_contours), 2)

    logger.info(f'Анализ завершён: итого {len(all_contours)} контуров')
    return {'contours': all_contours, 'averages': averages, 'analysis_options': options, 'diagnostics': diagnostics}


def estimate_scale_spacing(xs: list[int]) -> float:
    distances = np.diff(sorted(set(xs)))
    if len(distances) < 3:
        raise ValueError('Для калибровки нужно не менее четырёх штрихов шкалы')
    median = float(np.median(distances))
    consistent = distances[np.abs(distances - median) <= .2 * median]
    if len(consistent) < 3 or len(consistent) < .6 * len(distances):
        raise ValueError('Не удалось определить равномерный шаг шкалы')
    return float(np.median(consistent))


def _scale_masks(image: np.ndarray, contrasted: np.ndarray):
    gray = cv2.cvtColor(contrasted, cv2.COLOR_BGR2GRAY)
    yield _dark_stroke_mask(gray, vertical=True)
    yield _dark_stroke_mask(gray, vertical=False)
    # Individual channels retain contrast on a tinted transparent background
    # which can disappear when the image is converted to grayscale.
    for channel in (gray, *cv2.split(image)):
        smooth = cv2.GaussianBlur(channel, (5, 5), 0)
        yield cv2.threshold(smooth, 0, 255, cv2.THRESH_BINARY_INV | cv2.THRESH_OTSU)[1]
    channels = image.astype(np.int16)
    for a, b in ((0, 1), (0, 2), (1, 2)):
        difference = channels[:, :, a] - channels[:, :, b]
        for sign in (1, -1):
            yield (difference * sign > 10).astype(np.uint8) * 255


def _detect_calibration_scale(image: np.ndarray, contrasted: np.ndarray):
    marked = contrasted.copy()
    positions = detect_black_strips_left_edges(find_vertical_lines(contrasted), marked)
    try:
        estimate_scale_spacing(positions)
        return 'vertical', sorted(set(positions)), marked
    except ValueError:
        pass

    best = None
    most_marks = len(set(positions))
    for mask in _scale_masks(image, contrasted):
        for orientation in ('vertical', 'horizontal'):
            vertical = orientation == 'vertical'
            along = image.shape[0] if vertical else image.shape[1]
            across = image.shape[1] if vertical else image.shape[0]
            length = max(15, along // 7)
            closing = np.ones((9, 3) if vertical else (3, 9), np.uint8)
            kernel = np.ones((length, 1) if vertical else (1, length), np.uint8)
            joined = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, closing)
            opened = cv2.morphologyEx(joined, cv2.MORPH_OPEN, kernel)
            contours, _ = cv2.findContours(opened, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
            strokes = []
            for contour in contours:
                x, y, w, h = cv2.boundingRect(contour)
                position, thickness, span, start = (x, w, h, y) if vertical else (y, h, w, x)
                # A clipped leading edge cannot define the distance accurately.
                if position > 0 and span >= length and thickness < across * .15 and span / (thickness + 1) >= 4:
                    strokes.append((position, start, start + span, contour))
            # Compare strokes on the same section of the ruler, rather than
            # treating unrelated scratches elsewhere in the image as ticks.
            seen = set()
            for stroke in strokes:
                anchor = (stroke[1] + stroke[2]) / 2
                group = [s for s in strokes if s[1] <= anchor <= s[2]]
                coordinates = tuple(sorted({s[0] for s in group}))
                if coordinates in seen:
                    continue
                seen.add(coordinates)
                most_marks = max(most_marks, len(coordinates))
                if not group or min(s[2] for s in group) - max(s[1] for s in group) < length / 2:
                    continue
                try:
                    pitch = estimate_scale_spacing(list(coordinates))
                except ValueError:
                    continue
                distances = np.diff(coordinates)
                fraction = float(np.mean(np.abs(distances - pitch) <= .2 * pitch))
                jitter = float(np.mean(np.abs(distances - pitch))) / pitch
                coverage = float(np.median([s[2] - s[1] for s in group])) / along
                score = (fraction, -jitter, len(coordinates), coverage)
                if best is None or score > best[0]:
                    best = (score, orientation, list(coordinates), [s[3] for s in group])
    if best is None:
        raise ValueError(
            f'Не удалось выделить равномерную шкалу: кандидатов штрихов — {most_marks}. '
            'Нужны не менее четырёх отчётливых штрихов с одинаковым шагом. '
            'Расположите их горизонтально или вертикально и уменьшите блики.'
        )
    _, orientation, positions, contours = best
    marked = contrasted.copy()
    cv2.drawContours(marked, contours, -1, (0, 0, 255), cv2.FILLED)
    return orientation, positions, marked


def run_calibration_analysis() -> dict:
    """
    Обрабатывает session/calibration/sources.jpg.
    Результаты пишет в contrasted.jpg, contours.jpg, calibrated.jpg.
    Возвращает коэффициент в пикселях на деление, число и ориентацию штрихов.
    """
    source_path = SESSION_CAL_DIR / 'sources.jpg'
    if not source_path.exists():
        raise FileNotFoundError('sources.jpg не найден в сессии калибровки')

    logger.info('Калибровка: начало обработки')

    src = read_image(source_path)
    if src is None:
        raise ValueError('Не удалось прочитать sources.jpg')

    contrasted = increase_contrast(src)
    write_image(SESSION_CAL_DIR / 'contrasted.jpg', contrasted)

    orientation, xs, contours_img = _detect_calibration_scale(src, contrasted)
    write_image(SESSION_CAL_DIR / 'contours.jpg', contours_img)

    avg_distance = estimate_scale_spacing(xs)
    distances = [xs[i] - xs[i - 1] for i in range(1, len(xs))]

    final_img = contrasted.copy()
    h, w = final_img.shape[:2]

    candidates = [i for i, distance in enumerate(distances) if abs(distance - avg_distance) <= .2 * avg_distance]
    mid = candidates[len(candidates) // 2]
    x_s, x_e = xs[mid], xs[mid + 1]
    if orientation == 'vertical':
        y_blue, y_red = int(h * .6), int(h * .5)
        cv2.line(final_img, (xs[0], y_blue), (xs[-1], y_blue), (255, 0, 0), 2)
        cv2.line(final_img, (x_s, y_red), (x_e, y_red), (0, 0, 255), 2)
        pos = ((x_s + x_e) // 2, y_red - 10)
    else:
        x_blue, x_red = int(w * .35), int(w * .45)
        cv2.line(final_img, (x_blue, xs[0]), (x_blue, xs[-1]), (255, 0, 0), 2)
        cv2.line(final_img, (x_red, x_s), (x_red, x_e), (0, 0, 255), 2)
        pos = (x_red + 10, (x_s + x_e) // 2)
    label = f'{avg_distance:.3f}'
    _draw_outlined_labels(final_img, [(label, pos)], font_scale=.7, thickness=1, outline_width=1)

    write_image(SESSION_CAL_DIR / 'calibrated.jpg', final_img)

    coefficient = round(avg_distance, 3)
    logger.info(f'Калибровка завершена: коэффициент={coefficient}, штрихов={len(xs)}, ориентация={orientation}')
    return {'coefficient': coefficient, 'marks_count': len(xs), 'orientation': orientation}
