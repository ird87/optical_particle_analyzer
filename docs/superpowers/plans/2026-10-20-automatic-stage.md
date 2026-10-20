# Automatic XYZ Stage Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [x]`) syntax for tracking.

**Goal:** Связать Arduino XYZ, проверенные масштабы Z и автоматическую съёмку с существующим анализатором.

**Architecture:** Отдельные контроллер стола, транспорт, профиль масштаба и координатор съёмки. Прошивка и симулятор обслуживают общий протокол; долгие работы не блокируют STOP/API. Одна серия имеет один проверенный Z, каждый кадр хранит контекст масштаба.

**Tech Stack:** Python 3.10+, OpenCV 5, pySerial 3.5, Vue 3, Arduino AVR, AccelStepper.

**Spec:** `docs/superpowers/specs/2026-10-20-automatic-stage-design.md`

## Global Constraints

- Сохранить OpenCV 5 и совместимость существующих исследований и ручного режима.
- Не подключаться к реальным COM-портам и не двигать оборудование в автоматических тестах.
- Реальное движение запрещено, пока инженер не настроил профиль прошивки.
- Один Z и один снимок масштаба на автоматическую серию; никаких выдуманных коэффициентов.
- Общий Api lock нельзя удерживать в ожидании движения/паузы.

## Review Focus

- Перезапуск Arduino/устаревший DONE не разрешает снимок или продолжение.
- STOP доступен во время HOME/MOVE/калибровки/сетки.
- Потеря соединения и неотпускающийся концевик ограничены по времени/пути.
- Изменение масштаба/разрешения не смешивает разные измерения в одной серии.
- Частичная ошибка не удаляет готовые кадры и не активирует незавершённый профиль.

### Task 1: Stage protocol, controller and simulator

**Files:** `backend/stage.py`, `tests/test_stage.py`, `requirements.txt`.

**Interfaces:** `StageController.connect(settings) -> dict`, `home()`, `move(x,y,z)`, `stop()`, `snapshot() -> dict`, `close()`; транспорт сериализует команды/ответы с id. `SimulatedStage` реализует тот же интерфейс без порта.

- [x] Написать тесты протокола, пределов, неизвестного нуля, ошибок, STOP и устаревших ответов; подтвердить RED.
- [x] Реализовать конечные таймауты, отдельное владение соединением и симулятор.
- [x] Проверить GREEN и текущие тесты; сохранить задачу отдельным коммитом.

### Task 2: Configurable Arduino firmware

**Files:** `firmware/optical_stage/optical_stage.ino`, `firmware/optical_stage/stage_config.h`, `firmware/README.md`.

**Interfaces:** Команды/ответы Task 1; основной Nano и настройки Uno/Mega, A4988/DRV8825, STEP/DIR, концевиков и travel.

- [x] Зафиксировать примеры разговора протокола в тестах Task 1.
- [x] Реализовать неблокирующее движение, ограниченный homing ZXY, watchdog, STOP и отказ до настройки инженером.
- [x] Компилировать для Nano, Uno и Mega; проверить отсутствие blocking runToPosition/delay в движении.
- [x] Документировать подключение, выбор драйвера/платы, удержание Z и инженерную проверку.

### Task 3: Z scale profiles

**Files:** `backend/stage_profiles.py`, `backend/analyzer.py`, `tests/test_stage_profiles.py`.

**Interfaces:** Чистое распознавание шкалы из массива; `ProfileStore.save/load/list`; координатор создаёт профиль только после проверки всех Z.

- [x] Тесты известных шкал, неверного Z/разрешения, неполного профиля, атомарности и сохранённого снимка масштаба; RED.
- [x] Вынести распознавание шкалы без файловых побочных эффектов, сохранить прежний wrapper калибровки.
- [x] Реализовать запись профиля и строгий выбор точного Z; GREEN.

### Task 4: Jobs, capture and acquisition provenance

**Files:** `backend/stage_jobs.py`, `backend/camera.py`, `backend/storage.py`, `backend/api.py`, `tests/test_stage_api.py`.

**Interfaces:** Асинхронные start/status/stop для home/move/profile/scan; кадры содержат XYZ и snapshot масштаба.

- [x] Тесты MOVE/DONE/пауза/снимок, отмены, освобождения камеры и запрета смешения масштабов; RED.
- [x] Реализовать фоновые задания и свежий захват без cached первого кадра; добавить профили/порт/симулятор к API.
- [x] Сериализовать только короткие изменения сессии; блокировать несовместимые действия на backend.
- [x] Сохранять/загружать provenance вместе с исследованием; проверить старые записи и частичный сбой; GREEN.

### Task 5: Settings, calibration and scan UI

**Files:** `gui/components/StagePanel.js`, `gui/api.js`, `gui/index.html`, `gui/views/SettingsView.js`, `gui/views/CalibrationView.js`, `gui/views/AnalyzeView.js`, `tests/gui/`.

- [x] Проверки отключённого оборудования, симулятора, STOP и изменения выбранной сессии; RED.
- [x] Добавить выбор контроллера, управление/концевики, мастер Z и сетку с прогрессом.
- [x] Связать профиль с выбранной калибровкой, показывать ограничение перекрывающихся кадров; GREEN.

### Task 6: Integration and engineer handoff

**Files:** `SETUP.md`, firmware documentation, build dependencies/spec if needed.

- [x] Выполнить полный pytest на Linux/Windows и JavaScript/DOM проверки.
- [x] Пройти полный сценарий на симуляторе: подключение → ноль → шкала Z → сетка → анализ → сохранение → загрузка.
- [ ] Проверить компиляцию прошивки и сборку exe; реальное оборудование обозначить как не проверенное.
- [ ] Провести независимое ревью; исправить существенные замечания; отправить коммиты в claude.
