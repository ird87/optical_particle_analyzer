"""Build the Windows application in a dedicated virtual environment."""

import os
import subprocess
import sys
from pathlib import Path


def build_project(root: Path) -> Path:
    if sys.platform != 'win32':
        raise RuntimeError('Build the Windows exe on Windows with Python 3.10 or newer.')
    if sys.version_info < (3, 10):
        raise RuntimeError('Python 3.10 or newer is required.')

    root = root.resolve()
    destination = root / 'dist' / 'optical_analyzer'
    for data in (destination / 'data', destination / '_internal' / 'data'):
        if data.exists():
            raise RuntimeError(
                f'Existing application data found: {data}. '
                f'Move the entire previous application folder ({destination}) '
                'to another location before rebuilding.'
            )
    for required in ('requirements.txt', 'app.spec', 'tests'):
        if not (root / required).exists():
            raise RuntimeError(f'Missing build input: {root / required}')

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
    run([
        python, '-m', 'PyInstaller', '--noconfirm', '--clean',
        '--distpath', str(root / 'dist'), '--workpath', str(root / 'build'),
        str(root / 'app.spec'),
    ])

    output = root / 'dist' / 'optical_analyzer' / 'optical_analyzer.exe'
    if not output.is_file():
        raise RuntimeError(f'Build finished without the expected exe: {output}')
    with output.open('rb') as executable:
        if executable.read(2) != b'MZ':
            raise RuntimeError(f'Invalid Windows exe: {output}')
    return output


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
