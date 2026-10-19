# Microscope Capture Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [x]`) syntax for tracking.

**Goal:** Реализовать настройку подключения микроскопов, предпросмотр, ручное накопление снимков и съёмку шкалы.

**Architecture:** Один контроллер владеет камерой, реестр хранит микроскопы и привязки, Api связывает захват с ревизией рабочей сессии. Общий компонент предпросмотра используется настройками, исследованием и калибровкой. Автоматическое перемещение подключается отдельной будущей работой.

**Tech Stack:** Python 3.10+, OpenCV VideoCapture, SQLite, Vue 3 без сборщика, локальные Bootstrap и Chart.js, pytest, Node.js для тестов логики интерфейса.

**Spec:** `docs/superpowers/specs/2026-10-19-microscopes-and-analysis-design.md`. Выполнять после плана `2026-10-19-analysis.md`; формат измерений и успешных API ответов сохраняется.

## Global Constraints

- Приоритетная платформа — Windows; DirectShow на Windows и стандартный backend OpenCV на остальных платформах.
- Управление приводом разрабатывает инженер отдельно. Съёмка по таймеру не заменяет управление перемещением.
- Существующий microscopes.json сохраняет совместимость; встроенные М001 и М002 сохраняют названия.
- После перезапуска записи сохраняются, камера автоматически не открывается.
- Предпросмотр последовательно запрашивает кадры с ограниченной частотой. Полноразмерный снимок сохраняется отдельно от уменьшенного предпросмотра.
- Тесты используют временные каталоги и БД. Пользовательские CLAUDE.md, изображения и текущая data не изменяются миграциями тестов.

## Review Focus

- Запоздалый кадр после смены вкладки или исследования не должен открывать старый предпросмотр либо попасть в новую сессию; проверки задач 3 и 4.
- Открытое устройство без доступного кадра считается ошибкой, все неуспешные открытия освобождаются; проверка задачи 2.
- Поиск устройств во время предпросмотра не закрывает действующее подключение; проверка задачи 2.
- Повторяющиеся названия и перенумерация USB не должны привязать калибровку к другому микроскопу; проверка задачи 1.
- После нового кадра или смены калибровки прежние результаты нельзя сохранить как актуальные, включая прямой вызов Python API; проверка задачи 3.

## File Structure

- Create: `backend/microscopes.py` — реестр, валидация и сохранение привязок.
- Create: `backend/camera.py` — владение VideoCapture, поиск и безопасное чтение.
- Modify: `backend/storage.py` — сохранение JPEG и очистка производных изображений.
- Modify: `backend/api.py` — методы камеры и согласование с ревизией сессии.
- Modify: `main.py` — освобождение камеры при завершении.
- Create: `gui/components/CameraPanel.js` — общий предпросмотр и запрос снимка.
- Modify: `gui/api.js`, `gui/index.html`, `gui/views/SettingsView.js`, `gui/views/AnalyzeView.js`, `gui/views/CalibrationView.js`, `gui/views/HomeView.js` — управление подключением, съёмка и актуальность результатов.
- Create: `tests/test_microscopes.py`, `tests/test_camera.py`, `tests/test_capture_api.py`, `tests/gui/camera.test.js` — проверки поведения без физической камеры.
- Modify: `SETUP.md`, `app.spec` — запуск, проверка оборудования и включение новых модулей в сборку.

### Task 1: Реестр и привязки микроскопов

**Files:** `backend/microscopes.py`, `backend/api.py`, `tests/test_microscopes.py`.

**Interfaces:**
- Produces: `MicroscopeRegistry(data_dir: Path)`, методы `list() -> list[dict]`, `get(name: str) -> dict`, `save(data: dict) -> int`, `bind(name: str, camera_index: int) -> None`, `delete(microscope_id: int) -> None`.
- Entries retain name, type, type_localized, custom and custom id; add nullable camera_index to built-ins. DEFAULT cannot bind a camera. Bindings of built-ins use `microscope_bindings.json`; custom entries retain existing `microscopes.json` format.
- Api preserves `get_microscopes`, `save_custom_microscope`, `delete_custom_microscope` and adds `bind_microscope(name: str, camera_index: int) -> dict`.

- [x] Добавить тесты сохранения и чтения старого microscopes.json, отсутствующего файла, пользовательского микроскопа, привязки встроенного М001 и смены индекса камеры после переподключения.
- [x] Добавить тесты пустого и совпадающего без регистра имени, совпадения со встроенным именем, неизвестного типа, отрицательного/дробного/логического индекса и повреждённого JSON; ожидать конкретную ошибку без перезаписи повреждённого файла.
- [x] Запустить `pytest tests/test_microscopes.py -q` через проверочное окружение и убедиться в падении до реализации.
- [x] Реализовать реестр с блокировкой изменения и атомарной записью JSON через временный файл в том же каталоге. Сохранить исторические имена; удаление не меняет БД исследований.
- [x] Делегировать справочные API реестру, возвращать ok/error. Выполнить тесты реестра и прежние тесты БД.
- [x] Проверить diff и сохранить отдельный коммит при доступной записи в Git.

### Task 2: Контроллер камеры

**Files:** `backend/camera.py`, `tests/test_camera.py`.

**Interfaces:**
- Produces: `CameraController()`, `open(index: int) -> str`, `read(connection_id: str) -> np.ndarray`, `close(connection_id: str | None = None) -> None`, `scan() -> list[dict]`.
- Token identifies one connection; stale tokens raise `CameraError`. open requires successful read and retains that first frame for the first preview. read returns a full-size frame; encoding belongs to Api/storage. scan examines indices 0 through 9 and includes the active camera without reopening it.
- Produces: `CameraError(Exception)` with human-readable Russian messages.

- [x] Добавить подмену VideoCapture и проверки открытия, успешного кадра, повторного открытия, разных backend по платформе и освобождения при каждом неуспешном пути.
- [x] Проверить пустой кадр при isOpened=True, исключение read, отключение, повторное подключение, устаревший token и scan при активной камере. После потери кадра устройство должно быть освобождено.
- [x] Выполнить `pytest tests/test_camera.py -q` до реализации, затем реализовать методы с RLock и повторить тесты.
- [x] Проверить, что read не выдаёт сохранённый старый кадр после ошибки подключения, scan всегда освобождает временные устройства, а close со старым token не закрывает новую камеру.
- [x] Проверить diff и сохранить отдельный коммит при доступной записи в Git.

### Task 3: Сохранение снимков и ревизии сессии

**Files:** `backend/storage.py`, `backend/api.py`, `main.py`, `tests/test_capture_api.py`, `tests/test_storage.py`.

**Interfaces:**
- Consumes: Registry и CameraController задач 1 и 2; текущие модели и функции анализа.
- Produces: `storage.save_session_frame(frame: np.ndarray, context: str) -> str`, принимающий research/calibration, возвращающий имя JPEG. Для research выбирать max числового stem + 1; для calibration использовать sources.jpg и удалить прежние производные файлы после успешной записи.
- Api adds `connect_microscope(name: str, context: str) -> dict`, `get_camera_frame(connection_id: str) -> dict`, `disconnect_camera(connection_id: str) -> dict`, `capture_image(connection_id: str, context: str, revision: int) -> dict`, `get_session_state(context: str) -> dict`, `invalidate_research(revision: int) -> dict`, `shutdown() -> None`.
- Connect accepts settings/research/calibration; returns connection_id and revision. Preview returns data URI, captures return filename and updated revision. Only research/calibration accept capture. Camera ownership includes context.
- Session revisions are monotonic integers per context. new/load/upload/delete responses and analysis responses include revision. Successful research analysis caches its revision, calibration signature and results; save_research requires data.revision to match and rejects stale or changed calibration. Loaded research restores a valid cached result.

- [x] Добавить тесты двух снимков с существующими 1.jpg и 10.jpg: ожидать 11.jpg и 12.jpg, неизменность старых файлов и полноразмерные JPEG. При отказе кодирования или записи файл и успешный ответ отсутствуют.
- [x] Добавить тест снимка шкалы: source заменён, contrasted/contours/calibrated удалены. Сбой записи сохраняет прежний source и производные изображения.
- [x] Добавить проверки неизвестного context, неверного owner/token, отсутствующей привязки, захвата после new/load и отложенного запроса со старой revision. Тесты синхронизации используют threading.Event, без случайных sleep.
- [x] Проверить прямое сохранение устаревшего анализа после upload/delete/invalidate, обновления или удаления калибровки. Проверить загрузку сохранённого исследования и сохранение после повторного анализа.
- [x] Выполнить новые тесты до реализации.
- [x] Реализовать кодирование cv2.imencode('.jpg'), временный файл и атомарную замену. Не доверять имени из JS при захвате. При upload нормализовать исходное изображение в JPEG и отклонять нечитаемые данные, чтобы .jpg соответствовал содержимому.
- [x] Добавить сессионный RLock в Api; порядок блокировок всегда session, затем camera. Сериализовать чтение и сохранение снимка с операциями new/load/analysis. Проверить revision до операции и возвращать новую только при успешном изменении.
- [x] Использовать один CameraController для scan, get_test_frame и новых методов. Предпросмотр уменьшать до максимальной стороны 800 пикселей; полноразмерный кадр записи не уменьшать. Добавить finally в main для api.shutdown после завершения webview.
- [x] Выполнить тесты camera, storage, capture_api и весь Python набор. Проверить diff и сохранить отдельный коммит при доступной записи в Git.

### Task 4: Настройки и общий интерфейс съёмки

**Files:** `gui/components/CameraPanel.js`, `gui/api.js`, `gui/index.html`, `gui/views/SettingsView.js`, `gui/views/AnalyzeView.js`, `gui/views/CalibrationView.js`, `gui/views/HomeView.js`, `tests/gui/camera.test.js`.

**Interfaces:**
- Consumes: все методы Api задачи 3 через одноимённые camelCase обёртки api.js; root researchRevision, calibrationRevision и текущие результаты.
- Produces: Vue component `CameraPanel` с props microscope/context/active/revision и событиями captured({filename, revision})/error(message). Последовательный опрос раз в 200 мс через setTimeout после завершения запроса, локальный generation для игнорирования старых Promise.
- Settings uses the same component with context=settings, без кнопки снимка. Research allows manual captures. Calibration supports a single replacement capture for manual/automatic types. Automatic research start remains disabled with text «Автоматическое перемещение ещё не подключено».

- [x] Создать Node тесты с подменой api и таймеров: старт/стоп, один запрос в полёте, stale ответ после закрытия, переключение контекста, ошибка чтения, размонтирование и успешное событие captured. Использовать встроенные assert и vm; команда `node --harmony-optional-chaining --harmony-nullish tests/gui/camera.test.js` совместима с доступным Node 12.
- [x] Проверить, что сохранение после добавления/удаления кадра отключается, новая шкала сбрасывает coefficient, а восстановление сохранённого исследования не вызывает ложной инвалидизации. Пользовательские изменения выбора обрабатывать отдельно от программного восстановления формы. Отдельно проверить позднюю готовность pywebview: mount и начальные API вызовы выполняются только после появления bridge, даже если прошло 500 мс.
- [x] Запустить тесты до реализации. Создать CameraPanel и подключить его скрипт в index.html до views; зарегистрировать компонент до mount. Останавливать предпросмотр при active=false, смене microscope/context и unmounted.
- [x] В настройках добавить подключение/отключение и изменение привязки существующей записи, состояние ошибки и успешного чтения. После изменения справочника восстановить выбранный объект по имени, не сохранять старую ссылку Vue.
- [x] В AnalyzeView подключить CameraPanel и обработчик captured: добавить файл, обновить revision, сбросить результаты и кеш производных изображений. При удалении и загрузке с диска использовать revision ответа Api. Исправить watcher selectedResearch так, чтобы завершение анализа не запускало разрушительное повторное восстановление формы.
- [x] В CalibrationView подключить предпросмотр, captured и замену source; обновлять revision и очищать coefficient/кеш после успешной замены. Сохранять только при заполненных microscope/division и конечном положительном coefficient.
- [x] В HomeView и root согласовать new/load/revision и invalidateResearch; обработать Promise ошибки через try/finally, чтобы busy и таймеры восстанавливались.
- [x] Выполнить Node тесты и проверку синтаксиса всех собственных JS и inline script. Проверить diff и сохранить отдельный коммит при доступной записи в Git.

### Task 5: Проверка всего потока и инструкция инженеру

**Files:** `SETUP.md`, `app.spec`, тесты предыдущих задач при обнаружении пробелов.

**Interfaces:** Consumes: вся реализованная цепочка registry, camera, Api, UI и исправленный анализатор первого плана. Produces: команды запуска и проверки, описание точки будущего подключения привода.

- [x] Выполнить полный Python набор, Node тесты, проверку Python/JS синтаксиса и локальных ссылок index.html. Зафиксировать фактическое число проверок и ограничения окружения.
- [x] Проверить сквозной сценарий с подменой камеры: добавить микроскоп, подключить, снять шкалу, сохранить калибровку, создать исследование, накопить серию, анализировать и сохранить, загрузить результат. Проверить переключение вкладок и потерю устройства в середине сценария.
- [x] Добавить новые Python модули в hiddenimports app.spec. Отдельно отметить существующее отсутствие app.ico; сборку считать проверенной только после реального успешного запуска PyInstaller.
- [x] Описать в SETUP.md подключение и перепривязку камеры, съёмку и новые сообщения об ошибках. Для инженера описать будущую последовательность «перемещение → подтверждение остановки → capture_image с актуальной revision» и обязанность остановки привода; не добавлять неподтверждённый протокол устройства.
- [x] Провести итоговое ревью diff по обеим спецификациям поведения и проверкам гонок. Реальное оборудование проверить на Windows отдельно: предпросмотр, разрешение, серия, шкала, отключение кабеля и восстановление.
- [x] Сохранить итоговые изменения при доступной записи в Git и сообщить, что проверено автоматически и что требует физического микроскопа.
