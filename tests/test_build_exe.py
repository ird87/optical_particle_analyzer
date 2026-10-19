import subprocess
from pathlib import Path

import pytest
from scripts import build_exe


@pytest.fixture
def project(tmp_path, monkeypatch):
    root = tmp_path / 'project with spaces'
    root.mkdir()
    (root / 'requirements.txt').write_text('pyinstaller>=6.0\n')
    (root / 'app.spec').write_text('# spec\n')
    (root / 'tests').mkdir()
    monkeypatch.setattr(build_exe.sys, 'platform', 'win32')
    return root


def runner(root, commands, fail=None, produce_exe=True):
    def run(command, *, cwd, check, env):
        assert cwd == root and check is True
        assert 'PYTHONPATH' not in env and 'PYTHONHOME' not in env
        commands.append(command)
        if fail and fail in command:
            raise subprocess.CalledProcessError(7, command)
        if command[1:3] == ['-m','venv']:
            interpreter = root / '.build-venv/Scripts/python.exe'
            interpreter.parent.mkdir(parents=True)
            interpreter.write_bytes(b'interpreter')
        if 'PyInstaller' in command and produce_exe:
            output = root / 'dist/optical_analyzer/optical_analyzer.exe'
            output.parent.mkdir(parents=True, exist_ok=True)
            output.write_bytes(b'MZ executable')
        return subprocess.CompletedProcess(command, 0)
    return run


def test_build_creates_isolated_environment_tests_then_packages(project, monkeypatch):
    commands = []
    monkeypatch.setenv('PYTHONPATH','external packages')
    monkeypatch.setattr(build_exe.subprocess,'run',runner(project,commands))
    result = build_exe.build_project(project)
    assert result == project / 'dist/optical_analyzer/optical_analyzer.exe'
    assert commands[0][1:3] == ['-m','venv']
    assert any('-r' in command and str(project/'requirements.txt') in command for command in commands)
    test_index = next(i for i, command in enumerate(commands) if 'pytest' in command)
    package_index = next(i for i, command in enumerate(commands) if 'PyInstaller' in command)
    assert test_index < package_index
    assert commands[package_index][-1] == str(project/'app.spec')
    assert '--noconfirm' in commands[package_index] and '--clean' in commands[package_index]
    assert all(command[0] == str(project/'.build-venv/Scripts/python.exe') for command in commands[1:])


@pytest.mark.parametrize('failure', ['pip','pytest','PyInstaller'])
def test_build_stops_on_failed_step(project, monkeypatch, failure):
    commands=[]
    monkeypatch.setattr(build_exe.subprocess,'run',runner(project,commands,fail=failure))
    with pytest.raises(subprocess.CalledProcessError):
        build_exe.build_project(project)
    assert failure in commands[-1]
    if failure != 'PyInstaller':
        assert not any('PyInstaller' in command for command in commands)


def test_missing_executable_is_not_reported_as_success(project, monkeypatch):
    monkeypatch.setattr(build_exe.subprocess,'run',runner(project,[],produce_exe=False))
    with pytest.raises(RuntimeError,match='exe'):
        build_exe.build_project(project)


def test_existing_build_environment_is_reused(project, monkeypatch):
    interpreter=project/'.build-venv/Scripts/python.exe'
    interpreter.parent.mkdir(parents=True)
    interpreter.write_bytes(b'existing')
    commands=[]
    monkeypatch.setattr(build_exe.subprocess,'run',runner(project,commands))
    build_exe.build_project(project)
    assert not any(command[1:3] == ['-m','venv'] for command in commands)


def test_non_windows_build_fails_before_creating_files(tmp_path, monkeypatch):
    monkeypatch.setattr(build_exe.sys,'platform','linux')
    with pytest.raises(RuntimeError,match='Windows'):
        build_exe.build_project(tmp_path)
    assert list(tmp_path.iterdir()) == []


@pytest.mark.parametrize('relative', ['data', '_internal/data'])
def test_build_preserves_existing_application_data(project, monkeypatch, relative):
    data = project / 'dist/optical_analyzer' / relative
    data.mkdir(parents=True)
    saved = data / 'research.sqlite3'
    saved.write_bytes(b'user research')
    commands = []
    monkeypatch.setattr(build_exe.subprocess, 'run', runner(project, commands))
    with pytest.raises(RuntimeError, match='data'):
        build_exe.build_project(project)
    assert not commands
    assert saved.read_bytes() == b'user research'
