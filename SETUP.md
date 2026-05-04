# Настройка окружения (Windows, PyCharm)

## Очистить старые пакеты

В терминале PyCharm (venv активирован):

```
pip uninstall django asgiref sqlparse Pillow opencv-python -y
```

Если не уверен что установлено — сначала посмотри:
```
pip list
```

---

## Установить новые пакеты

```
pip install -r requirements.txt
```

Установится:
- `pywebview` — десктопное окно с HTML/JS
- `opencv-python-headless` — OpenCV без Qt (обработка изображений)
- `numpy` — числа и массивы
- `pytest` — тесты
- `pyinstaller` — сборка .exe

---

## Запуск приложения

```
python main.py
```

Откроется окно приложения. При первом запуске создаётся папка `data/` рядом с проектом.

---

## Запуск тестов

```
python -m pytest tests/ -v
```

Все 14 тестов должны пройти. Тесты используют фикстуры из `tests/fixtures/` и не требуют запущенного приложения.

---

## Сборка .exe

```
pyinstaller app.spec
```

Результат: `dist\optical_analyzer\optical_analyzer.exe`  
Папку `dist\optical_analyzer\` можно скопировать на любой Windows-компьютер — Python там не нужен.
