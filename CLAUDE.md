# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Рабочий процесс (обязательно)

После прочтения этого файла **всегда читай `План.md`** — там находится пошаговый план реализации текущей ветки `claude`. Отмечай каждый выполненный пункт плана символом `[x]` сразу после его завершения, не дожидаясь конца сессии.

## Commands

```bash
# Activate virtual environment (required before all other commands)
source venv/bin/activate   # Linux/macOS
# venv\Scripts\activate    # Windows

# Run development server
python manage.py runserver

# Run on Raspberry Pi (opens browser automatically)
./run_on_raspberry_pi.sh

# Apply database migrations
python manage.py migrate

# Create new migrations after model changes
python manage.py makemigrations

# Merge all source files into merged_files.txt (dev utility)
python output.py
```

No test suite is configured for this project.

## Architecture

Django 5.2 backend + Vue.js 3 (CDN, no build step) frontend. SQLite database. OpenCV handles all image processing server-side.

### Pages and their Vue components

Each page is a Django template that mounts a Vue 3 app via `vue.global.prod.js` (loaded from `static/vue/`). Vue uses `[[ ]]` delimiters (not `{{ }}`) to avoid conflict with Django templates.

| URL | Template | Vue mixin |
|-----|----------|-----------|
| `/` | `home.html` | `home.vue.js` |
| `/analyze/` (inferred) | `analyze.html` | `analyze.vue.js` |
| `/calibration/` (inferred) | `calibration.html` | `calibration.vue.js` |
| `/results/` (inferred) | `results.html` | `results.vue.js` |

Static data (microscope list, division prices) is injected into templates via Django context processors (`analyzer/context_processors.py`) and read by Vue from the DOM.

### Image processing pipeline

All CV work happens in `analyzer/views.py` using OpenCV. For a **research** analysis:
1. Source images are uploaded to `media/research/in_work/sources/`
2. `execute_research` processes each image through three stages: contrast enhancement (CLAHE + Gaussian blur) → contour detection (threshold + `findContours`) → analysis (measurements + calibration conversion)
3. Results are written to `in_work/contrasted/`, `in_work/contours/`, `in_work/analyzed/`
4. `save_research` copies `in_work/` into `media/research/<id>/` and persists to DB

For **calibration**: a single image goes to `media/calibration/in_work/sources.jpg`, processed to detect vertical ruler stripes and compute a pixel/division coefficient.

### Data model

- `Calibration` — stores pixel-to-unit coefficient and division price (e.g. "1 мкм")
- `Research` — one analysis session; holds aggregate averages; FK to `Calibration`
- `ContourData` — one row per detected particle contour, FK to `Research`

Measurement conversion: `real_value = (pixels / calibration_coefficient) * division_price_value`. Area uses squared coefficients.

### Static microscope/division data

`MICROSCOPES` and `DIVISION_PRICES` lists in `analyzer/models.py` are hard-coded. To add a microscope or division price, edit those lists — no DB migration needed.

### Media layout

```
analyzer/media/
  research/
    in_work/          ← active working session
      sources/
      contrasted/
      contours/
      analyzed/
    <id>/             ← saved research (same subfolder structure)
  calibration/
    in_work/          ← active calibration session (single image, no subfolders)
    <id>/             ← saved calibration images
```

`home` view clears both `in_work` directories on every visit — this is intentional to start fresh.

### API surface

All endpoints are under `/api/` and return JSON. Mutation endpoints use `@csrf_exempt`. The `list_images` endpoint serves file listings for the Vue frontend to populate image pickers.
