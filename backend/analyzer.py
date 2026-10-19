import math

import cv2
import numpy as np

from backend.logger import logger
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

def find_vertical_lines(img_bgr: np.ndarray) -> np.ndarray:
    gray = cv2.cvtColor(img_bgr, cv2.COLOR_BGR2GRAY)
    binary_inv = cv2.adaptiveThreshold(
        gray, 255,
        cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
        cv2.THRESH_BINARY_INV,
        blockSize=31,
        C=10,
    )
    kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (1, 7))
    return cv2.morphologyEx(binary_inv, cv2.MORPH_CLOSE, kernel, iterations=1)


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
    *, threshold_mode: str = 'fixed',
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

        detected = extract_particle_contours(contrasted, threshold_mode)
        contours, contour_number = measure_contours(
            detected, contour_number, calibration_coefficient, division_price_value,
        )
        contoured = draw_particle_contours(contrasted, detected)
        write_image(contours_dir / src_path.name, contoured)
        analyzed = draw_particle_contours(contrasted, detected, contours)
        write_image(analyzed_dir / src_path.name, analyzed)

        logger.info(f'{src_path.name}: найдено {len(contours)} контуров')
        all_contours.extend(contours)

    averages: dict[str, float] = {'perimeter': 0, 'area': 0, 'width': 0, 'length': 0, 'dek': 0}
    if all_contours:
        for key in averages:
            averages[key] = round(sum(c[key] for c in all_contours) / len(all_contours), 2)

    logger.info(f'Анализ завершён: итого {len(all_contours)} контуров')
    return {'contours': all_contours, 'averages': averages}


def estimate_scale_spacing(xs: list[int]) -> float:
    distances = np.diff(sorted(set(xs)))
    if len(distances) < 3:
        raise ValueError('Для калибровки нужно не менее четырёх штрихов шкалы')
    median = float(np.median(distances))
    consistent = distances[np.abs(distances - median) <= .2 * median]
    if len(consistent) < 3 or len(consistent) < .6 * len(distances):
        raise ValueError('Не удалось определить равномерный шаг шкалы')
    return float(np.median(consistent))


def run_calibration_analysis() -> dict:
    """
    Обрабатывает session/calibration/sources.jpg.
    Результаты пишет в contrasted.jpg, contours.jpg, calibrated.jpg.
    Возвращает {'coefficient': float}.
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

    binary = find_vertical_lines(contrasted)
    contours_img = contrasted.copy()
    xs = detect_black_strips_left_edges(binary, contours_img)
    write_image(SESSION_CAL_DIR / 'contours.jpg', contours_img)

    avg_distance = estimate_scale_spacing(xs)
    distances = [xs[i] - xs[i - 1] for i in range(1, len(xs))]

    final_img = contrasted.copy()
    h, w = final_img.shape[:2]

    y_blue = int(h * 0.6)
    cv2.line(final_img, (xs[0], y_blue), (xs[-1], y_blue), (255, 0, 0), 2)

    candidates = [i for i, distance in enumerate(distances) if abs(distance - avg_distance) <= .2 * avg_distance]
    mid = candidates[len(candidates) // 2]
    x_s, x_e = xs[mid], xs[mid + 1]
    y_red = int(h * 0.5)
    cv2.line(final_img, (x_s, y_red), (x_e, y_red), (0, 0, 255), 2)

    label = f'{avg_distance:.3f}'
    pos = ((x_s + x_e) // 2, y_red - 10)
    _draw_outlined_labels(final_img, [(label, pos)], font_scale=.7, thickness=1, outline_width=1)

    write_image(SESSION_CAL_DIR / 'calibrated.jpg', final_img)

    coefficient = round(avg_distance, 3)
    logger.info(f'Калибровка завершена: коэффициент={coefficient}')
    return {'coefficient': coefficient}
