import shutil
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
            dist = Path(command[command.index('--distpath') + 1])
            output = dist / 'optical_analyzer/optical_analyzer.exe'
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


def previous_build(project, relative='_internal/data'):
    app = project / 'dist/optical_analyzer'
    data = app / relative
    data.mkdir(parents=True)
    (data / 'app.db').write_bytes(b'user research')
    (data / 'research').mkdir()
    (data / 'research/image.jpg').write_bytes(b'image')
    (app / 'optical_analyzer.exe').write_bytes(b'MZ old version')
    return app


@pytest.mark.parametrize('relative', ['data', '_internal/data'])
def test_rebuild_automatically_archives_old_version_and_carries_data(project, monkeypatch, relative):
    old_app = previous_build(project, relative)
    commands = []
    monkeypatch.setattr(build_exe.subprocess, 'run', runner(project, commands))
    output = build_exe.build_project(project)
    assert output.read_bytes() == b'MZ executable'
    assert (old_app / '_internal/data/app.db').read_bytes() == b'user research'
    assert (old_app / '_internal/data/research/image.jpg').read_bytes() == b'image'
    backups = list((project / 'dist/backups').iterdir())
    assert len(backups) == 1
    assert (backups[0] / 'optical_analyzer.exe').read_bytes() == b'MZ old version'
    assert (backups[0] / relative / 'app.db').read_bytes() == b'user research'


def test_each_rebuild_preserves_latest_data_and_creates_distinct_backup(project, monkeypatch):
    app = previous_build(project)
    monkeypatch.setattr(build_exe.subprocess, 'run', runner(project, []))
    build_exe.build_project(project)
    (app / '_internal/data/app.db').write_bytes(b'new research')
    build_exe.build_project(project)
    assert (app / '_internal/data/app.db').read_bytes() == b'new research'
    backups = list((project / 'dist/backups').iterdir())
    assert len(backups) == 2
    assert {p.joinpath('_internal/data/app.db').read_bytes() for p in backups} == {
        b'user research', b'new research',
    }


@pytest.mark.parametrize('failure', ['pip', 'pytest', 'PyInstaller', 'missing_exe'])
def test_failed_rebuild_leaves_previous_application_in_place(project, monkeypatch, failure):
    app = previous_build(project)
    monkeypatch.setattr(build_exe.subprocess, 'run', runner(
        project, [], fail=failure, produce_exe=failure != 'missing_exe',
    ))
    with pytest.raises((RuntimeError, subprocess.CalledProcessError)):
        build_exe.build_project(project)
    assert (app / 'optical_analyzer.exe').read_bytes() == b'MZ old version'
    assert (app / '_internal/data/app.db').read_bytes() == b'user research'
    assert not list((project / 'dist').glob('backups/*'))


def test_failed_data_copy_leaves_previous_application_in_place(project, monkeypatch):
    app = previous_build(project)
    monkeypatch.setattr(build_exe.subprocess, 'run', runner(project, []))
    def fail_copy(*args, **kwargs):
        raise OSError('disk full')
    monkeypatch.setattr(shutil, 'copytree', fail_copy)
    with pytest.raises(OSError, match='disk full'):
        build_exe.build_project(project)
    assert (app / 'optical_analyzer.exe').read_bytes() == b'MZ old version'
    assert (app / '_internal/data/app.db').read_bytes() == b'user research'


def test_failed_publish_restores_previous_application(project, monkeypatch):
    app = previous_build(project)
    monkeypatch.setattr(build_exe.subprocess, 'run', runner(project, []))
    rename = Path.rename
    def fail_publish(path, target):
        if path != app and Path(target) == app and path.parent.name != 'backups':
            raise PermissionError('publish blocked')
        return rename(path, target)
    monkeypatch.setattr(Path, 'rename', fail_publish)
    with pytest.raises(PermissionError, match='publish blocked'):
        build_exe.build_project(project)
    assert (app / 'optical_analyzer.exe').read_bytes() == b'MZ old version'
    assert (app / '_internal/data/app.db').read_bytes() == b'user research'


def test_ambiguous_data_folders_do_not_overwrite_either_database(project, monkeypatch):
    app = previous_build(project)
    (app / 'data').mkdir()
    (app / 'data/app.db').write_bytes(b'other research')
    monkeypatch.setattr(build_exe.subprocess, 'run', runner(project, []))
    with pytest.raises(RuntimeError, match='Two data folders'):
        build_exe.build_project(project)
    assert (app / '_internal/data/app.db').read_bytes() == b'user research'
    assert (app / 'data/app.db').read_bytes() == b'other research'
    assert (app / 'optical_analyzer.exe').read_bytes() == b'MZ old version'


def test_locked_previous_build_is_left_intact(project, monkeypatch):
    app = previous_build(project)
    monkeypatch.setattr(build_exe.subprocess, 'run', runner(project, []))
    rename = Path.rename
    def fail_backup(path, target):
        if path == app:
            raise PermissionError('application still running')
        return rename(path, target)
    monkeypatch.setattr(Path, 'rename', fail_backup)
    with pytest.raises(PermissionError, match='application still running'):
        build_exe.build_project(project)
    assert (app / 'optical_analyzer.exe').read_bytes() == b'MZ old version'
    assert (app / '_internal/data/app.db').read_bytes() == b'user research'
