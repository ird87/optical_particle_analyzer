import math

import cv2
import numpy as np

from backend.logger import logger
from backend.storage import (
    SESSION_CAL_DIR,
    SESSION_RES_DIR,
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


def find_and_draw_contours(image: np.ndarray) -> np.ndarray:
    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    _, thresh = cv2.threshold(gray, 127, 255, cv2.THRESH_BINARY_INV)
    contours, _ = cv2.findContours(thresh, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    h, w = image.shape[:2]

    def within_bounds(cnt):
        for pt in cnt:
            x, y = pt[0]
            if x <= 0 or y <= 0 or x >= w - 1 or y >= h - 1:
                return False
        return True

    filtered = [c for c in contours if cv2.contourArea(c) > 100 and within_bounds(c)]
    cv2.drawContours(image, filtered, -1, (0, 0, 255), 2)
    return image


def pixels_to_real_units(pixels: float, coeff: float, division: float) -> float:
    if coeff == 0:
        return pixels
    return (pixels / coeff) * division


def analyze_contours(
    image: np.ndarray,
    start_number: int = 1,
    calibration_coefficient: float = 1.0,
    division_price_value: float = 1.0,
) -> tuple[np.ndarray, list[dict], int]:
    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    _, thresh = cv2.threshold(gray, 127, 255, cv2.THRESH_BINARY_INV)
    contours, _ = cv2.findContours(thresh, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    h, w = image.shape[:2]

    def within_bounds(cnt):
        for pt in cnt:
            x, y = pt[0]
            if x <= 0 or y <= 0 or x >= w - 1 or y >= h - 1:
                return False
        return True

    filtered = [c for c in contours if cv2.contourArea(c) > 100 and within_bounds(c)]
    results = []

    for cnt in filtered:
        M = cv2.moments(cnt)
        cx = int(M['m10'] / M['m00']) if M['m00'] != 0 else 0
        cy = int(M['m01'] / M['m00']) if M['m00'] != 0 else 0

        perimeter_px = cv2.arcLength(cnt, True)
        area_px = cv2.contourArea(cnt)
        rect = cv2.minAreaRect(cnt)
        width_px = min(rect[1])
        length_px = max(rect[1])
        dek_px = math.sqrt((4 * area_px) / math.pi)

        c, d = calibration_coefficient, division_price_value
        results.append({
            'contour_number': start_number,
            'perimeter': round(pixels_to_real_units(perimeter_px, c, d), 2),
            'area':      round(pixels_to_real_units(area_px, c ** 2, d ** 2), 2),
            'length':    round(pixels_to_real_units(length_px, c, d), 2),
            'width':     round(pixels_to_real_units(width_px, c, d), 2),
            'dek':       round(pixels_to_real_units(dek_px, c, d), 2),
            'cx': cx,
            'cy': cy,
        })

        cv2.putText(image, str(start_number), (cx, cy),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 255), 6)
        cv2.putText(image, str(start_number), (cx, cy),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 0, 0), 2)
        start_number += 1

    return image, results, start_number


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
) -> dict:
    """
    Обрабатывает все файлы из session/research/sources/.
    Результаты пишет в contrasted/, contours/, analyzed/.
    Возвращает {'contours': [...], 'averages': {...}}.
    """
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

        image = cv2.imread(str(src_path))
        if image is None:
            logger.error(f'Не удалось прочитать {src_path.name}')
            continue

        contrasted = increase_contrast(image.copy())
        cv2.imwrite(str(contrasted_dir / src_path.name), contrasted)

        contoured = find_and_draw_contours(contrasted.copy())
        cv2.imwrite(str(contours_dir / src_path.name), contoured)

        analyzed, contours, contour_number = analyze_contours(
            contrasted.copy(), contour_number,
            calibration_coefficient, division_price_value,
        )
        cv2.imwrite(str(analyzed_dir / src_path.name), analyzed)

        logger.info(f'{src_path.name}: найдено {len(contours)} контуров')
        all_contours.extend(contours)

    averages: dict[str, float] = {'perimeter': 0, 'area': 0, 'width': 0, 'length': 0, 'dek': 0}
    if all_contours:
        for key in averages:
            averages[key] = round(sum(c[key] for c in all_contours) / len(all_contours), 2)

    logger.info(f'Анализ завершён: итого {len(all_contours)} контуров')
    return {'contours': all_contours, 'averages': averages}


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

    src = cv2.imread(str(source_path))
    if src is None:
        raise ValueError('Не удалось прочитать sources.jpg')

    contrasted = increase_contrast(src)
    cv2.imwrite(str(SESSION_CAL_DIR / 'contrasted.jpg'), contrasted)

    binary = find_vertical_lines(contrasted)
    contours_img = contrasted.copy()
    xs = detect_black_strips_left_edges(binary, contours_img)
    cv2.imwrite(str(SESSION_CAL_DIR / 'contours.jpg'), contours_img)

    if len(xs) < 2:
        cv2.imwrite(str(SESSION_CAL_DIR / 'calibrated.jpg'), contrasted)
        logger.info('Калибровка: найдено менее 2 полос, коэффициент=0')
        return {'coefficient': 0.0}

    distances = [xs[i] - xs[i - 1] for i in range(1, len(xs))]
    avg_distance = sum(distances) / len(distances)

    final_img = contrasted.copy()
    h, w = final_img.shape[:2]

    y_blue = int(h * 0.6)
    cv2.line(final_img, (xs[0], y_blue), (xs[-1], y_blue), (255, 0, 0), 2)

    mid = len(distances) // 2
    x_s, x_e = xs[mid], xs[mid + 1]
    y_red = int(h * 0.5)
    cv2.line(final_img, (x_s, y_red), (x_e, y_red), (0, 0, 255), 2)

    label = f'{avg_distance:.3f}'
    pos = ((x_s + x_e) // 2, y_red - 10)
    cv2.putText(final_img, label, pos, cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 255, 255), 3)
    cv2.putText(final_img, label, pos, cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 0, 0), 1)

    cv2.imwrite(str(SESSION_CAL_DIR / 'calibrated.jpg'), final_img)

    coefficient = round(avg_distance, 3)
    logger.info(f'Калибровка завершена: коэффициент={coefficient}')
    return {'coefficient': coefficient}
