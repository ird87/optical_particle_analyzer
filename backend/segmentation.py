"""Particle masks from original pixels, independent of annotations and calibration."""
import math

import cv2
import numpy as np


DEFAULT_OPTIONS = {'mode': 'auto', 'min_area_px': 100.0, 'split_touching': False}


def validate_options(options=None):
    if options is None:
        return DEFAULT_OPTIONS.copy()
    if not isinstance(options, dict) or set(options) - set(DEFAULT_OPTIONS):
        raise ValueError('Некорректные параметры выделения частиц')
    result = {**DEFAULT_OPTIONS, **options}
    if result['mode'] not in ('auto', 'dark', 'light', 'color'):
        raise ValueError('Неизвестный режим выделения частиц')
    area = result['min_area_px']
    if isinstance(area, bool) or not isinstance(area, (int, float)) or not math.isfinite(area) or area < 1:
        raise ValueError('Минимальная площадь должна быть конечным числом не меньше 1 пикселя²')
    if type(result['split_touching']) is not bool:
        raise ValueError('Разделение частиц должно быть включено или выключено')
    result['min_area_px'] = float(area)
    return result


def _border_samples(array):
    size = max(1, min(array.shape[:2]) // 40)
    return np.concatenate((array[:size].reshape(-1, array.shape[2]),
                           array[-size:].reshape(-1, array.shape[2]),
                           array[:, :size].reshape(-1, array.shape[2]),
                           array[:, -size:].reshape(-1, array.shape[2])))


def _illumination_mask(gray):
    """Correct a linear light gradient only when frame edges support the fit."""
    h, w = gray.shape
    sample = cv2.resize(gray, (min(w, 160), min(h, 160)), interpolation=cv2.INTER_AREA)
    yy, xx = np.mgrid[:sample.shape[0], :sample.shape[1]].astype(np.float32)
    xx = 2 * xx / max(1, sample.shape[1] - 1) - 1
    yy = 2 * yy / max(1, sample.shape[0] - 1) - 1
    rim = max(1, min(sample.shape) // 40)
    edge = np.ones(sample.shape, bool)
    edge[rim:-rim, rim:-rim] = False
    design = np.column_stack((xx[edge], yy[edge], np.ones(edge.sum())))
    values = sample[edge].astype(np.float32)
    valid = np.ones(len(values), bool)
    for _ in range(3):
        coefficients, _, rank, _ = np.linalg.lstsq(design[valid], values[valid], rcond=None)
        if rank < 3:
            return None
        residual = values - design @ coefficients
        deviation = np.median(np.abs(residual - np.median(residual)))
        valid = np.abs(residual) <= max(8, 3 * deviation)
        if valid.sum() < .6 * len(values):
            return None
    if np.quantile(np.abs(residual), .8) > 8 or 2 * np.sum(np.abs(coefficients[:2])) < 20:
        return None
    background = (coefficients[0] * np.linspace(-1, 1, w)[None, :] +
                  coefficients[1] * np.linspace(-1, 1, h)[:, None] + coefficients[2])
    distance = np.clip(np.abs(gray.astype(np.float32) - background), 0, 255).astype(np.uint8)
    threshold, _ = cv2.threshold(distance, 0, 255, cv2.THRESH_BINARY | cv2.THRESH_OTSU)
    return np.uint8(distance > max(12, threshold)) * 255


def _foreground_mask(image, mode):
    smooth = cv2.GaussianBlur(image, (3, 3), 0)
    if mode in ('auto', 'color'):
        ab = cv2.cvtColor(smooth, cv2.COLOR_BGR2LAB)[:, :, 1:].astype(np.float32)
        background = np.median(_border_samples(ab), axis=0)
        distance = np.clip(np.linalg.norm(ab - background, axis=2), 0, 255).astype(np.uint8)
        threshold, _ = cv2.threshold(distance, 0, 255, cv2.THRESH_BINARY | cv2.THRESH_OTSU)
        mask = np.uint8(distance > max(12, threshold)) * 255
        foreground = distance[mask > 0]
        back = distance[mask == 0]
        separated = foreground.size and back.size and np.mean(foreground) - np.mean(back) >= 12
        colored_background = float(np.linalg.norm(background - 128)) >= 12
        if separated and np.mean(mask > 0) < .8 and (mode == 'color' or colored_background):
            return mask, 'lab_background'
        if mode == 'color':
            raise ValueError('Недостаточно цветового контраста. Выберите светлые или тёмные частицы')

    gray = cv2.cvtColor(smooth, cv2.COLOR_BGR2GRAY)
    if mode == 'auto':
        corrected = _illumination_mask(gray)
        if corrected is not None:
            return corrected, 'gray_corrected'
    _, light = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY | cv2.THRESH_OTSU)
    dark = cv2.bitwise_not(light)
    low, high = gray[dark > 0], gray[light > 0]
    if not low.size or not high.size or float(np.mean(high)) - float(np.mean(low)) < 12:
        return np.zeros_like(gray), 'gray_' + ('light' if mode == 'light' else 'dark')
    if mode == 'auto':
        # The material around the frame is a better background cue than the
        # smaller class: a single large particle may fill most of the image.
        dark_border = float(np.mean(_border_samples(dark[:, :, None]) > 0))
        light_border = 1 - dark_border
        mode = 'dark' if (dark_border, np.mean(dark > 0)) < (light_border, np.mean(light > 0)) else 'light'
    return (dark if mode == 'dark' else light), 'gray_' + mode


def _split_contour(contour, min_area):
    area = cv2.contourArea(contour)
    hull_area = cv2.contourArea(cv2.convexHull(contour))
    # Convex particles, including long grains, should not be cut into pieces.
    if not hull_area or area / hull_area > .96:
        return [contour]
    x, y, w, h = cv2.boundingRect(contour)
    offset = np.array([[[x - 2, y - 2]]], dtype=np.int32)
    mask = np.zeros((h + 4, w + 4), np.uint8)
    cv2.drawContours(mask, [contour - offset], -1, 255, -1)
    distance = cv2.distanceTransform(mask, cv2.DIST_L2, 5)
    distance = cv2.GaussianBlur(distance, (3, 3), 0)
    maximum = float(distance.max())
    if maximum < 3:
        return [contour]
    radius = max(3, int(maximum * .5))
    kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (2 * radius + 1, 2 * radius + 1))
    peaks = np.uint8((distance >= cv2.dilate(distance, kernel) - 1e-5) & (distance >= .45 * maximum))
    count, labels = cv2.connectedComponents(peaks)
    candidates = []
    for label in range(1, count):
        ys, xs = np.where(labels == label)
        index = int(np.argmax(distance[ys, xs]))
        candidates.append((float(distance[ys[index], xs[index]]), int(xs[index]), int(ys[index])))
    if len(candidates) > 64:
        return [contour]
    seeds = []
    for height, sx, sy in sorted(candidates, reverse=True):
        separate = True
        for previous, px, py in seeds:
            separation = math.hypot(sx - px, sy - py)
            if separation < max(6, .8 * maximum):
                separate = False
                break
            # Test the widest connecting path inside the particle. A straight
            # line can leave a single curved grain and falsely suggest a neck.
            core = np.uint8(distance >= .65 * min(height, previous))
            _, core_labels = cv2.connectedComponents(core)
            if core_labels[sy, sx] == core_labels[py, px]:
                separate = False
                break
        if separate:
            seeds.append((height, sx, sy))
    if len(seeds) < 2:
        return [contour]
    # Grow from eroded interiors, not point seeds. Equal erosion depth keeps
    # the boundary near the neck even when touching grains have different sizes.
    core = np.uint8(distance >= .65 * min(seed[0] for seed in seeds))
    _, core_labels = cv2.connectedComponents(core)
    seed_labels = [int(core_labels[sy, sx]) for _, sx, sy in seeds]
    if 0 in seed_labels or len(set(seed_labels)) != len(seeds):
        return [contour]
    core = np.uint8(np.isin(core_labels, seed_labels))
    _, markers = cv2.distanceTransformWithLabels(1 - core, cv2.DIST_L2, 5,
                                                 labelType=cv2.DIST_LABEL_CCOMP)
    region_labels = [int(markers[sy, sx]) for _, sx, sy in seeds]
    parts = []
    for label in region_labels:
        region = np.uint8((markers == label) & (mask > 0)) * 255
        contours, _ = cv2.findContours(region, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        if len(contours) != 1 or cv2.contourArea(contours[0]) <= min_area:
            return [contour]
        parts.append(contours[0] + offset)
    if sum(cv2.contourArea(c) for c in parts) < .85 * area:
        return [contour]
    return parts


def segment_particles(image, options=None):
    options = validate_options(options)
    if image is None or image.ndim != 3 or image.shape[2] != 3 or image.dtype != np.uint8:
        raise ValueError('Нужно цветное изображение в формате BGR uint8')
    mask, method = _foreground_mask(image, options['mode'])
    contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    height, width = mask.shape
    result, excluded_border, excluded_small, split_count = [], 0, 0, 0
    for contour in contours:
        if cv2.contourArea(contour) <= options['min_area_px']:
            excluded_small += 1
            continue
        x, y, w, h = cv2.boundingRect(contour)
        if x == 0 or y == 0 or x + w >= width or y + h >= height:
            excluded_border += 1
            continue
        parts = _split_contour(contour, options['min_area_px']) if options['split_touching'] else [contour]
        split_count += len(parts) - 1
        result.extend(parts)
    result.sort(key=lambda c: (cv2.boundingRect(c)[1], cv2.boundingRect(c)[0]))
    accepted = np.zeros_like(mask)
    if result:
        cv2.drawContours(accepted, result, -1, 255, -1)
    return {'contours': result, 'mask': accepted, 'method': method,
            'excluded_border': excluded_border, 'excluded_small': excluded_small,
            'split_count': split_count, 'options': options}
