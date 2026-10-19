"""Compare segmentation without claiming accuracy on unlabelled photographs."""
import argparse
import json
import sys
from pathlib import Path

import cv2
import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from backend.analyzer import (increase_contrast, extract_particle_contours,
                              measure_contours, draw_particle_contours)


def synthetic_scenes():
    scenes = {}
    for name, foreground, background in [('normal', 80, 210), ('bright', 155, 230), ('dim', 30, 100)]:
        image = np.full((200, 200, 3), background, np.uint8)
        cv2.rectangle(image, (60, 60), (100, 120), (foreground,) * 3, -1)
        scenes[name] = image
    gradient = np.tile(np.linspace(140, 230, 200), (200, 1))
    gradient[60:121, 60:101] = 100
    scenes['gradient'] = cv2.cvtColor(gradient.astype(np.uint8), cv2.COLOR_GRAY2BGR)
    noise = np.random.default_rng(42).normal(0, 5, (200, 200, 3))
    scenes['noise'] = np.clip(scenes['normal'].astype(float) + noise, 0, 255).astype(np.uint8)
    return scenes


def compare(image, output, name, known=False):
    prepared = increase_contrast(image)
    report = {}
    previews = [image.copy()]
    for mode in ('fixed', 'otsu'):
        contours = extract_particle_contours(prepared, mode)
        results, _ = measure_contours(contours)
        metrics = {'count': len(results)}
        if known:
            largest = max(results, key=lambda r: r['area']) if results else None
            for key, expected in [('area', 2400), ('width', 40), ('length', 60)]:
                metrics[key + '_error'] = round(abs(largest[key] - expected) / expected, 4) if largest else None
        report[mode] = metrics
        previews.append(draw_particle_contours(image, contours, results))
    height = min(500, image.shape[0])
    width = round(image.shape[1] * height / image.shape[0])
    resized = []
    for label, preview in zip(('source', 'fixed 127', 'Otsu'), previews):
        preview = cv2.resize(preview, (width, height))
        cv2.putText(preview, label, (10, 24), cv2.FONT_HERSHEY_SIMPLEX, .7, (0, 0, 255), 2)
        resized.append(preview)
    if not cv2.imwrite(str(output / (name + '.png')), np.hstack(resized)):
        raise OSError('Could not write comparison preview')
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=True)
    report = {'opencv': cv2.__version__, 'preprocessing': 'CLAHE 2.0 8x8 + Gaussian 5x5',
              'synthetic': {}, 'fixtures': {},
              'limitations': 'Photographs have no reference annotations. Counts do not measure accuracy.'}
    for name, image in synthetic_scenes().items():
        report['synthetic'][name] = compare(image, args.output, name, known=True)
    for path in sorted((Path(__file__).resolve().parents[1] / 'tests/fixtures/research').glob('*.jpg')):
        image = cv2.imread(str(path))
        if image is None:
            raise ValueError(f'Cannot read {path}')
        report['fixtures'][path.name] = compare(image, args.output, 'fixture-' + path.stem)
    (args.output / 'metrics.json').write_text(json.dumps(report, ensure_ascii=False, indent=2), 'utf-8')
    print(args.output / 'metrics.json')


if __name__ == '__main__':
    main()
