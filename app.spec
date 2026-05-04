# -*- mode: python ; coding: utf-8 -*-
"""
PyInstaller spec-файл для сборки Оптического анализатора частиц под Windows.

Сборка:
    pip install pyinstaller
    pyinstaller app.spec

Результат: dist/optical_analyzer/optical_analyzer.exe
"""

from PyInstaller.utils.hooks import collect_all

# Собираем все файлы cv2 (DLL, данные, бинарники)
cv2_datas, cv2_binaries, cv2_hiddenimports = collect_all('cv2')

a = Analysis(
    ['main.py'],
    pathex=[],
    binaries=cv2_binaries,
    datas=[
        # Статика GUI
        ('gui', 'gui'),
        # Тестовые фикстуры (для возможности запуска тестов из бандла)
        ('tests/fixtures', 'tests/fixtures'),
        # Данные cv2 (каскады, шрифты и т.д.)
        *cv2_datas,
    ],
    hiddenimports=[
        *cv2_hiddenimports,
        'backend.api',
        'backend.analyzer',
        'backend.database',
        'backend.logger',
        'backend.models',
        'backend.storage',
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        # Исключаем Django и всё что не нужно в десктопном приложении
        'django',
        'tkinter',
        'matplotlib',
        'scipy',
        'pandas',
        'IPython',
        'notebook',
    ],
    noarchive=False,
)

pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='optical_analyzer',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,          # Без консольного окна
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon='app.ico',
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name='optical_analyzer',
)
