"""One background stage operation; cancellation never waits for its worker lock."""
import copy
from threading import Event, RLock, Thread
from uuid import uuid4


class JobCancelled(RuntimeError):
    pass


def check_cancel(cancel):
    if cancel.is_set(): raise JobCancelled('Остановлено пользователем')


class StageJobs:
    def __init__(self):
        self._lock = RLock()
        self._cancel = Event()
        self._thread = None
        self._job = {'active': False, 'status': 'idle'}

    def snapshot(self):
        with self._lock: return copy.deepcopy(self._job)

    def start(self, kind, work):
        with self._lock:
            if self._job['active']: raise ValueError('Стол уже выполняет задание')
            self._cancel = Event()
            self._job = {'id': uuid4().hex, 'kind': kind, 'active': True, 'status': 'running', 'completed': 0, 'total': 0}
            self._thread = Thread(target=self._run, args=(work, self._cancel), daemon=True, name='opa-stage-job')
            self._thread.start()
            return self.snapshot()

    def _progress(self, **values):
        with self._lock: self._job.update(copy.deepcopy(values))

    def _run(self, work, cancel):
        try:
            result = work(cancel, self._progress)
            check_cancel(cancel)
            self._progress(result=result, status='done')
        except Exception as error:
            self._progress(status='cancelled' if cancel.is_set() else 'error', error=str(error))
        finally:
            self._progress(active=False)

    def cancel(self):
        with self._lock:
            self._cancel.set()
            if self._job['active']: self._job['status'] = 'stopping'

    def join(self, timeout=3):
        if self._thread: self._thread.join(timeout)
