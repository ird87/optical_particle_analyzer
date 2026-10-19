"""One owner for the physical camera; stale preview requests cannot switch it."""
import sys
from threading import RLock
from uuid import uuid4

import cv2
import numpy as np

from backend.microscopes import validate_camera_index


class CameraError(Exception):
    pass


class CameraController:
    def __init__(self):
        self._lock = RLock()
        self._capture = None
        self._index = None
        self._token = None
        self._first_frame = None

    @staticmethod
    def _create(index):
        if sys.platform == 'win32':
            return cv2.VideoCapture(index, cv2.CAP_DSHOW)
        return cv2.VideoCapture(index)

    def open(self, index: int) -> str:
        validate_camera_index(index)
        with self._lock:
            self.close()
            try:
                self._capture = self._create(index)
                if not self._capture.isOpened():
                    raise CameraError('Камера не открылась. Проверьте подключение и выбранный индекс')
                success, frame = self._capture.read()
                if not success or frame is None or not frame.size:
                    raise CameraError('Камера открылась, но кадр не получен')
                self._first_frame = frame
                self._index = index
                self._token = uuid4().hex
                return self._token
            except Exception as error:
                self.close()
                raise CameraError(str(error)) from error

    def read(self, connection_id: str) -> np.ndarray:
        with self._lock:
            if not connection_id or connection_id != self._token:
                raise CameraError('Подключение камеры устарело. Подключите микроскоп снова')
            try:
                if self._first_frame is not None:
                    frame = self._first_frame
                    self._first_frame = None
                    return frame
                success, frame = self._capture.read()
                if not success or frame is None or not frame.size:
                    raise CameraError('Кадр не получен. Проверьте USB-подключение микроскопа')
                return frame
            except Exception as error:
                self.close()
                raise CameraError(str(error)) from error

    def close(self, connection_id: str | None = None) -> None:
        with self._lock:
            if connection_id is not None and connection_id != self._token:
                return
            capture = self._capture
            self._capture = self._index = self._token = self._first_frame = None
            if capture is not None:
                capture.release()

    def scan(self) -> list[dict]:
        with self._lock:
            found = []
            for index in range(10):
                if self._capture is not None and index == self._index:
                    found.append({'index': index, 'label': f'Камера {index}'})
                    continue
                probe = None
                try:
                    probe = self._create(index)
                    if probe.isOpened():
                        success, frame = probe.read()
                        if success and frame is not None and frame.size:
                            found.append({'index': index, 'label': f'Камера {index}'})
                except Exception:
                    # One failing driver must not hide the remaining devices.
                    pass
                finally:
                    if probe is not None:
                        probe.release()
            return found
