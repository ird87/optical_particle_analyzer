"""Build the Windows application in a dedicated virtual environment."""

import os
import shutil
import subprocess
import sys
import tempfile
from datetime import datetime
from pathlib import Path
from uuid import uuid4


def publish_build(prepared: Path, destination: Path) -> None:
    """Keep the old application intact until packaging and data copying succeed."""
    sources = [path for path in (
        destination / '_internal' / 'data', destination / 'data',
    ) if path.exists()]
    if len(sources) > 1:
        raise RuntimeError(
            f'Two data folders found in {destination}. '
            'Keep the active data folder there and move the other to a safe location.'
        )
    if sources:
        shutil.copytree(sources[0], prepared / '_internal' / 'data')

    destination.parent.mkdir(parents=True, exist_ok=True)
    backup = None
    if destination.exists():
        backups = destination.parent / 'backups'
        backups.mkdir(exist_ok=True)
        stamp = datetime.now().strftime('%Y%m%d-%H%M%S')
        backup = backups / f'{destination.name}-{stamp}-{uuid4().hex[:8]}'
        destination.rename(backup)
        print(f'Previous build saved: {backup}', flush=True)
    try:
        prepared.rename(destination)
    except OSError as error:
        if backup is not None and not destination.exists():
            try:
                backup.rename(destination)
            except OSError:
                raise RuntimeError(
                    f'Cannot publish the build or restore its previous location. '
                    f'The previous application and data are safe in {backup}.'
                ) from error
        raise


def build_project(root: Path) -> Path:
    if sys.platform != 'win32':
        raise RuntimeError('Build the Windows exe on Windows with Python 3.10 or newer.')
    if sys.version_info < (3, 10):
        raise RuntimeError('Python 3.10 or newer is required.')

    root = root.resolve()
    destination = root / 'dist' / 'optical_analyzer'
    for required in ('requirements.txt', 'app.spec', 'tests'):
        if not (root / required).exists():
            raise RuntimeError(f'Missing build input: {root / required}')
    print('Close the application before rebuilding so its data can be copied safely.', flush=True)

    env = os.environ.copy()
    env.pop('PYTHONPATH', None)
    env.pop('PYTHONHOME', None)
    env['PYTHONUTF8'] = '1'
    env['PIP_DISABLE_PIP_VERSION_CHECK'] = '1'
    env['PYINSTALLER_CONFIG_DIR'] = str(root / 'build' / '.pyinstaller-cache')

    def run(command):
        print(f'Running: {subprocess.list2cmdline(command)}', flush=True)
        subprocess.run(command, cwd=root, check=True, env=env)

    interpreter = root / '.build-venv' / 'Scripts' / 'python.exe'
    if not interpreter.is_file():
        run([sys.executable, '-m', 'venv', str(root / '.build-venv')])
    python = str(interpreter)
    run([python, '-m', 'pip', 'install', '--upgrade', 'pip'])
    run([python, '-m', 'pip', 'install', '-r', str(root / 'requirements.txt')])
    run([python, '-m', 'pytest', str(root / 'tests'), '-q'])
    work = root / 'build'
    work.mkdir(exist_ok=True)
    with tempfile.TemporaryDirectory(prefix='exe-', dir=work) as temporary:
        stage = Path(temporary)
        run([
            python, '-m', 'PyInstaller', '--noconfirm', '--clean',
            '--distpath', str(stage / 'dist'), '--workpath', str(stage / 'work'),
            str(root / 'app.spec'),
        ])
        prepared = stage / 'dist' / 'optical_analyzer'
        output = prepared / 'optical_analyzer.exe'
        if not output.is_file():
            raise RuntimeError(f'Build finished without the expected exe: {output}')
        with output.open('rb') as executable:
            if executable.read(2) != b'MZ':
                raise RuntimeError(f'Invalid Windows exe: {output}')
        publish_build(prepared, destination)
    return destination / 'optical_analyzer.exe'


def main() -> int:
    try:
        output = build_project(Path(__file__).resolve().parents[1])
    except (OSError, RuntimeError, subprocess.CalledProcessError) as error:
        print(f'Build failed: {error}', file=sys.stderr)
        return 1
    print(f'Build complete: {output}')
    print('Copy the entire optical_analyzer folder, including _internal, to distribute it.')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
