import cv2
import numpy as np
import pytest

from backend.segmentation import segment_particles, validate_options


def scene(light=True, colored=False, noise=0):
    yy, xx = np.mgrid[:280, :420]
    if colored:
        background = np.stack((165 + 15 * xx / 420, 85 + 20 * yy / 280, 55 + 15 * xx / 420), axis=2)
    else:
        background = np.full((280, 420, 3), 40 if light else 225, dtype=float)
    truth = np.zeros((280, 420), np.uint8)
    cv2.circle(truth, (85, 80), 28, 255, -1)
    cv2.rectangle(truth, (195, 45), (260, 110), 255, -1)
    cv2.ellipse(truth, (305, 205), (45, 23), 20, 0, 360, 255, -1)
    image = background.copy()
    image[truth > 0] = (220, 230, 235) if light else (15, 15, 15)
    image += np.random.default_rng(14).normal(0, noise, image.shape)
    return np.clip(image, 0, 255).astype(np.uint8), truth


def mask_from(contours, shape):
    mask = np.zeros(shape, np.uint8)
    cv2.drawContours(mask, contours, -1, 255, -1)
    return mask > 0


@pytest.mark.parametrize('light', [False, True])
@pytest.mark.parametrize('colored', [False, True])
def test_auto_finds_objects_with_both_polarities_and_keeps_geometry(light, colored):
    image, truth = scene(light, colored, noise=4)
    original = image.copy()
    result = segment_particles(image)
    assert len(result['contours']) == 3
    detected = mask_from(result['contours'], truth.shape)
    overlap = (detected & (truth > 0)).sum() / (detected | (truth > 0)).sum()
    assert overlap > .96
    np.testing.assert_array_equal(image, original)


@pytest.mark.parametrize('mode,light', [('dark', False), ('light', True), ('color', True)])
def test_explicit_modes_find_known_particles(mode, light):
    image, _ = scene(light, colored=mode == 'color')
    assert len(segment_particles(image, {'mode': mode})['contours']) == 3


def test_uniform_noisy_background_does_not_become_particles():
    image = np.clip(180 + np.random.default_rng(1).normal(0, 3, (280, 420, 3)), 0, 255).astype(np.uint8)
    assert segment_particles(image)['contours'] == []


def test_noise_is_filtered_and_border_particles_are_reported():
    image, _ = scene(True, True, 5)
    cv2.circle(image, (0, 190), 25, (230, 230, 230), -1)
    for x, y in [(150, 160), (170, 200), (380, 50)]:
        cv2.circle(image, (x, y), 2, (230, 230, 230), -1)
    result = segment_particles(image)
    assert len(result['contours']) == 3
    assert result['excluded_border'] == 1
    assert result['excluded_small'] >= 3


@pytest.mark.parametrize('light', [True, False])
def test_narrow_neck_is_split_without_losing_circle_measurements(light):
    image = np.full((220, 320, 3), 35 if light else 235, np.uint8)
    color = (225, 225, 225) if light else (20, 20, 20)
    cv2.circle(image, (105, 110), 38, color, -1)
    cv2.circle(image, (185, 110), 38, color, -1)
    cv2.line(image, (140, 110), (150, 110), color, 5)
    unsplit = segment_particles(image, {'split_touching': False})
    result = segment_particles(image, {'split_touching': True})
    assert len(unsplit['contours']) == 1
    assert len(result['contours']) == 2
    assert result['split_count'] == 1
    for contour in result['contours']:
        assert cv2.contourArea(contour) == pytest.approx(np.pi * 38 ** 2, rel=.04)


@pytest.mark.parametrize('split', [False, True])
def test_elongated_and_convex_single_particles_are_not_split(split):
    image = np.full((300, 440, 3), 230, np.uint8)
    cv2.ellipse(image, (110, 100), (75, 18), 0, 0, 360, (20, 20, 20), -1)
    triangle = np.array([[250, 230], [280, 50], [390, 230]], np.int32)
    cv2.fillPoly(image, [triangle], (20, 20, 20))
    assert len(segment_particles(image, {'split_touching': split})['contours']) == 2


def test_close_separate_particles_are_not_joined():
    image = np.full((160, 220, 3), 30, np.uint8)
    for x in [80, 123]:
        cv2.circle(image, (x, 80), 20, (230, 230, 230), -1)
    assert len(segment_particles(image, {'split_touching': False})['contours']) == 2


def test_minimum_area_is_configurable():
    image = np.full((200, 240, 3), 230, np.uint8)
    cv2.circle(image, (80, 100), 20, (20, 20, 20), -1)
    cv2.circle(image, (160, 100), 4, (20, 20, 20), -1)
    assert len(segment_particles(image)['contours']) == 1
    assert len(segment_particles(image, {'min_area_px': 20})['contours']) == 2


@pytest.mark.parametrize('options', [None, {}, {'mode': 'auto'}])
def test_defaults_are_stable(options):
    result = validate_options(options)
    assert result == {'mode': 'auto', 'min_area_px': 100.0, 'split_touching': False}


@pytest.mark.parametrize('options', [[], {'mode': 'bad'}, {'min_area_px': float('nan')},
    {'min_area_px': True}, {'min_area_px': 0}, {'min_area_px': -1}, {'split_touching': 'yes'}, {'unknown': 1}])
def test_bad_options_are_rejected(options):
    with pytest.raises(ValueError):
        validate_options(options)


def test_small_colored_border_mark_does_not_hide_dark_particles_on_neutral_background():
    image, _ = scene(False)
    cv2.rectangle(image, (412, 230), (419, 260), (0, 220, 220), -1)
    result = segment_particles(image)
    assert result['method'] == 'gray_dark'
    assert len(result['contours']) == 3


@pytest.mark.parametrize('split', [False, True])
def test_single_horseshoe_is_not_assumed_to_be_several_grains(split):
    image = np.full((260, 300, 3), 230, np.uint8)
    cv2.ellipse(image, (150, 130), (80, 65), 0, 0, 280, (20, 20, 20), 24)
    assert len(segment_particles(image, {'split_touching': split})['contours']) == 1


@pytest.mark.parametrize('light', [False, True])
def test_auto_corrects_smooth_linear_illumination_without_losing_size(light):
    gray = np.tile(np.linspace(140, 230, 200), (200, 1)).astype(np.uint8)
    gray[60:121, 60:101] = 250 if light else 100
    result = segment_particles(cv2.cvtColor(gray, cv2.COLOR_GRAY2BGR))
    assert len(result['contours']) == 1
    assert cv2.contourArea(result['contours'][0]) == pytest.approx(2400, rel=.03)


def test_illumination_gradient_alone_is_not_a_particle():
    gray = np.tile(np.linspace(140, 230, 200), (200, 1)).astype(np.uint8)
    assert segment_particles(cv2.cvtColor(gray, cv2.COLOR_GRAY2BGR))['contours'] == []


@pytest.mark.parametrize('radii', [(40, 20), (60, 30)])
def test_splitting_different_sizes_does_not_transfer_large_grain_area_to_small_one(radii):
    large, small = radii
    image = np.full((300, 400, 3), 230, np.uint8)
    cx, cy = 90, 140
    second = cx + large + small + 4
    cv2.circle(image, (cx, cy), large, (20, 20, 20), -1)
    cv2.circle(image, (second, cy), small, (20, 20, 20), -1)
    cv2.line(image, (cx + large - 2, cy), (second - small + 2, cy), (20, 20, 20), 5)
    result = segment_particles(image, {'split_touching': True})
    assert len(result['contours']) == 2
    for area, radius in zip(sorted(cv2.contourArea(c) for c in result['contours']), [small, large]):
        assert area == pytest.approx(np.pi * radius ** 2, rel=.07)


def test_split_preserves_background_gap_between_grains_connected_at_both_sides():
    image = np.full((270, 300, 3), 230, np.uint8)
    color = (20, 20, 20)
    cv2.circle(image, (150, 85), 45, color, -1)
    cv2.circle(image, (150, 185), 35, color, -1)
    for x in (128, 172):
        cv2.line(image, (x, 120), (x, 165), color, 4)
    result = segment_particles(image, {'split_touching': True})
    assert len(result['contours']) == 2
    assert all(cv2.boundingRect(c)[3] < 115 for c in result['contours'])


@pytest.mark.parametrize('minimum,expected', [(100, 2), (400, 1)])
def test_attached_small_fragment_is_split_before_area_filtering(minimum, expected):
    image = np.full((230, 320, 3), 230, np.uint8)
    color = (20, 20, 20)
    cv2.circle(image, (110, 115), 42, color, -1)
    cv2.circle(image, (170, 115), 9, color, -1)
    cv2.line(image, (149, 115), (164, 115), color, 3)
    result = segment_particles(image, {'split_touching': True, 'min_area_px': minimum})
    assert len(result['contours']) == expected
    large = max(result['contours'], key=cv2.contourArea)
    assert cv2.boundingRect(large)[2] < 95
    assert cv2.contourArea(large) == pytest.approx(np.pi * 42 ** 2, rel=.04)
    if minimum == 400:
        assert result['excluded_small'] >= 1


def test_split_cluster_handles_different_neck_widths():
    image = np.full((260, 280, 3), 230, np.uint8)
    color = (20, 20, 20)
    cv2.circle(image, (100, 85), 40, color, -1)
    cv2.circle(image, (100, 185), 28, color, -1)
    cv2.line(image, (100, 122), (100, 160), color, 20)
    cv2.circle(image, (160, 85), 9, color, -1)
    cv2.line(image, (138, 85), (154, 85), color, 3)
    result = segment_particles(image, {'split_touching': True})
    assert len(result['contours']) == 3


def test_small_grain_between_two_large_grains_keeps_its_whole_body():
    image = np.full((280, 320, 3), 230, np.uint8)
    color = (20, 20, 20)
    cv2.circle(image, (150, 80), 50, color, -1)
    cv2.circle(image, (175, 195), 32, color, -1)
    cv2.circle(image, (110, 165), 12, color, -1)
    for start, end in [((172, 120), (175, 168)), ((130, 123), (113, 155)), ((119, 169), (148, 184))]:
        cv2.line(image, start, end, color, 3)
    result = segment_particles(image, {'split_touching': True})
    assert len(result['contours']) == 3
    small = min(result['contours'], key=cv2.contourArea)
    assert cv2.contourArea(small) == pytest.approx(np.pi * 12 ** 2, rel=.2)
