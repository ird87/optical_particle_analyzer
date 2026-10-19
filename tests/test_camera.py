import numpy as np
import pytest
from backend import camera


class FakeCapture:
    def __init__(self, opened=True, readable=True):
        self.opened = opened
        self.readable = readable
        self.released = False
        self.frame = np.full((80, 100, 3), 130, np.uint8)

    def isOpened(self):
        return self.opened and not self.released

    def read(self):
        if isinstance(self.readable, Exception):
            raise self.readable
        return self.readable, self.frame.copy() if self.readable else None

    def release(self):
        self.released = True


@pytest.fixture
def setup_camera(monkeypatch):
    devices = []
    def factory(*args):
        cap = FakeCapture()
        cap.arguments = args
        devices.append(cap)
        return cap
    monkeypatch.setattr(camera.cv2, 'VideoCapture', factory)
    return camera.CameraController(), devices


def test_connect_read_close_and_stale_token(setup_camera):
    controller, devices = setup_camera
    old = controller.open(0)
    assert controller.read(old).shape == (80, 100, 3)
    current = controller.open(1)
    assert devices[0].released
    controller.close(old)
    assert controller.read(current).shape == (80, 100, 3)
    with pytest.raises(camera.CameraError):
        controller.read(old)
    controller.close(current)
    assert devices[1].released


@pytest.mark.parametrize('opened,readable', [(False, True), (True, False), (True, RuntimeError('driver'))])
def test_bad_connection_always_releases_device(monkeypatch, opened, readable):
    cap = FakeCapture(opened, readable)
    monkeypatch.setattr(camera.cv2, 'VideoCapture', lambda *args: cap)
    with pytest.raises(camera.CameraError):
        camera.CameraController().open(0)
    assert cap.released


def test_disconnect_during_preview_and_reconnect(setup_camera):
    controller, devices = setup_camera
    token = controller.open(0)
    controller.read(token)
    devices[0].readable = False
    with pytest.raises(camera.CameraError):
        controller.read(token)
    assert devices[0].released
    new = controller.open(0)
    assert controller.read(new).size


def test_scan_keeps_active_camera_and_releases_probes(setup_camera):
    controller, devices = setup_camera
    token = controller.open(0)
    found = controller.scan()
    assert {entry['index'] for entry in found} == set(range(10))
    assert not devices[0].released
    assert all(cap.released for cap in devices[1:])
    assert controller.read(token).size


@pytest.mark.parametrize('platform,expected', [('win32', True), ('linux', False)])
def test_platform_camera_backend(monkeypatch, setup_camera, platform, expected):
    controller, devices = setup_camera
    monkeypatch.setattr(camera.sys, 'platform', platform)
    controller.open(0)
    assert (len(devices[0].arguments) == 2) is expected
