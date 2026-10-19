import base64
import threading
import cv2
import numpy as np
import pytest
from backend import analyzer, database as db, storage
from backend.api import Api
from backend.models import Calibration


class Capture:
    def __init__(self):
        self.released = False
    def isOpened(self):
        return not self.released
    def read(self):
        frame = np.full((120, 180, 3), 240, np.uint8)
        cv2.rectangle(frame, (40,40), (80,80), (0,0,0), -1)
        return True, frame
    def release(self):
        self.released = True


@pytest.fixture
def api(tmp_path, monkeypatch):
    for attr, path in {'DATA_DIR': tmp_path, 'SESSION_DIR': tmp_path/'session',
                       'SESSION_RES_DIR': tmp_path/'session/research', 'SESSION_CAL_DIR': tmp_path/'session/calibration',
                       'RESEARCH_DIR': tmp_path/'research', 'CALIBRATION_DIR': tmp_path/'calibration'}.items():
        monkeypatch.setattr(storage, attr, path)
    monkeypatch.setattr(analyzer, 'SESSION_RES_DIR', storage.SESSION_RES_DIR)
    monkeypatch.setattr(analyzer, 'SESSION_CAL_DIR', storage.SESSION_CAL_DIR)
    monkeypatch.setattr(db, 'DB_PATH', tmp_path/'app.db')
    monkeypatch.setattr(cv2, 'VideoCapture', lambda *args: Capture())
    db.init_db()
    storage.clear_session()
    instance = Api()
    instance.save_custom_microscope({'name':'USB', 'type':'MANUAL', 'camera_index':0})
    yield instance
    if hasattr(instance, 'shutdown'):
        instance.shutdown()


def connect(api, context='research'):
    result = api.connect_microscope('USB', context)
    assert result['ok'], result
    return result


def test_capture_series_uses_free_names_and_full_resolution(api):
    folder = storage.SESSION_RES_DIR/'sources'
    (folder/'1.jpg').write_bytes(b'old1')
    (folder/'10.jpg').write_bytes(b'old10')
    state = connect(api)
    for expected in ('11.jpg','12.jpg'):
        result = api.capture_image(state['connection_id'], 'research', state['revision'])
        assert result['ok'], result
        assert result['filename'] == expected
        state['revision'] = result['revision']
        assert cv2.imread(str(folder/expected)).shape == (120,180,3)
    assert (folder/'1.jpg').read_bytes() == b'old1'


def test_capture_calibration_clears_old_outputs(api):
    for filename in ('contrasted.jpg','contours.jpg','calibrated.jpg'):
        (storage.SESSION_CAL_DIR/filename).write_bytes(b'old')
    state = connect(api, 'calibration')
    result = api.capture_image(state['connection_id'], 'calibration', state['revision'])
    assert result['ok'], result
    assert (storage.SESSION_CAL_DIR/'sources.jpg').exists()
    assert not (storage.SESSION_CAL_DIR/'calibrated.jpg').exists()


def test_capture_encoding_failure_preserves_old_calibration(api, monkeypatch):
    old = storage.SESSION_CAL_DIR/'sources.jpg'
    old.write_bytes(b'old')
    state = connect(api, 'calibration')
    monkeypatch.setattr(cv2, 'imencode', lambda *args: (False, None))
    assert api.capture_image(state['connection_id'],'calibration',state['revision'])['ok'] is False
    assert old.read_bytes() == b'old'


def test_stale_capture_cannot_write_into_new_session(api):
    state = connect(api)
    api.new_research()
    result = api.capture_image(state['connection_id'], 'research', state['revision'])
    assert result['ok'] is False
    assert list((storage.SESSION_RES_DIR/'sources').iterdir()) == []


def test_cross_context_and_invalid_revision_rejected(api):
    state = connect(api)
    for context, revision in [('calibration',state['revision']), ('research',-1), ('invalid',state['revision'])]:
        assert not api.capture_image(state['connection_id'], context, revision)['ok']
    assert not api.connect_microscope('М001','research')['ok']


def payload(revision, calibration):
    return {'id':0,'name':'Research','employee':'Test','microscope':'USB',
            'calibration_id':calibration,'revision':revision}


def test_analysis_save_load_and_stale_result_rejected(api):
    cal = db.save_calibration(Calibration('Scale','USB',10,'1 мкм'))
    state = connect(api)
    captured = api.capture_image(state['connection_id'],'research',state['revision'])
    analyzed = api.execute_research(cal)
    assert analyzed['ok'], analyzed
    saved = api.save_research(payload(analyzed['revision'], cal))
    assert saved['ok'], saved
    loaded = api.load_research(saved['id'])
    assert loaded['research']['contours']
    assert loaded['research']['average_area'] == analyzed['averages']['area']
    stale_payload = payload(loaded['revision'], cal)
    api.invalidate_research(loaded['revision'])
    assert not api.save_research(stale_payload)['ok']


def test_changed_calibration_rejects_previous_analysis(api):
    cal = Calibration('Scale','USB',10,'1 мкм')
    cal.id = db.save_calibration(cal)
    state = connect(api)
    api.capture_image(state['connection_id'],'research',state['revision'])
    analyzed = api.execute_research(cal.id)
    cal.coefficient = 20
    db.save_calibration(cal)
    assert not api.save_research(payload(analyzed['revision'], cal.id))['ok']


def test_upload_normalizes_png_and_rejects_bad_data(api):
    _, png = cv2.imencode('.png', Capture().read()[1])
    result = api.upload_image('1.jpg', base64.b64encode(png).decode(), 'research')
    assert result['ok']
    assert (storage.SESSION_RES_DIR/'sources/1.jpg').read_bytes()[:2] == b'\xff\xd8'
    assert not api.upload_image('../escape.jpg','AAAA','research')['ok']
    assert not api.upload_image('2.jpg',base64.b64encode(b'garbage').decode(),'research')['ok']


def test_capture_and_new_session_are_serialized(api, monkeypatch):
    state = connect(api)
    entered, proceed = threading.Event(), threading.Event()
    original = storage.save_session_frame
    def slow_save(*args):
        entered.set()
        assert proceed.wait(3)
        return original(*args)
    monkeypatch.setattr(storage,'save_session_frame',slow_save)
    results = []
    capture = threading.Thread(target=lambda: results.append(api.capture_image(state['connection_id'],'research',state['revision'])))
    capture.start()
    assert entered.wait(3)
    reset = threading.Thread(target=api.new_research)
    reset.start()
    proceed.set()
    capture.join(3); reset.join(3)
    assert not capture.is_alive() and not reset.is_alive()
    assert results[0]['ok']
    assert list((storage.SESSION_RES_DIR/'sources').iterdir()) == []


def test_end_to_end_calibration_capture_and_saved_series(api, monkeypatch):
    original = Capture.read
    def ruler(self):
        frame = np.full((200,300,3),255,np.uint8)
        for x in range(40,261,20):
            cv2.line(frame,(x,40),(x,160),(0,0,0),2)
        return True,frame
    monkeypatch.setattr(Capture,'read',ruler)
    state = connect(api,'calibration')
    captured = api.capture_image(state['connection_id'],'calibration',state['revision'])
    analyzed = api.execute_calibration()
    assert analyzed['ok'],analyzed
    assert analyzed['coefficient'] == pytest.approx(20,abs=.5)
    saved = api.save_calibration({'name':'Scale','microscope':'USB','coefficient':analyzed['coefficient'],
                                 'division_price':'1 мкм','revision':captured['revision']})
    assert saved['ok'],saved
    monkeypatch.setattr(Capture,'read',original)
    state = connect(api)
    for _ in range(2):
        captured = api.capture_image(state['connection_id'],'research',state['revision'])
        assert captured['ok'],captured
        state['revision'] = captured['revision']
    analyzed = api.execute_research(saved['id'])
    assert analyzed['ok'],analyzed
    assert len(analyzed['contours']) == 2
    result = api.save_research(payload(analyzed['revision'],saved['id']))
    assert result['ok'],result
    restored = api.load_research(result['id'])
    assert restored['ok']
    assert len(restored['files']) == len(restored['research']['contours']) == 2
    assert (storage.RESEARCH_DIR/str(result['id'])/'analyzed/1.jpg').exists()


def test_failed_disk_replace_preserves_calibration_and_revision(api, monkeypatch):
    (storage.SESSION_CAL_DIR/'sources.jpg').write_bytes(b'old source')
    (storage.SESSION_CAL_DIR/'calibrated.jpg').write_bytes(b'old output')
    state=connect(api,'calibration')
    def fail(*args):
        raise OSError('disk unavailable')
    monkeypatch.setattr(storage.os,'replace',fail)
    result=api.capture_image(state['connection_id'],'calibration',state['revision'])
    assert not result['ok']
    assert api.get_session_state('calibration')['revision'] == state['revision']
    assert (storage.SESSION_CAL_DIR/'sources.jpg').read_bytes() == b'old source'
    assert (storage.SESSION_CAL_DIR/'calibrated.jpg').read_bytes() == b'old output'


def test_bridge_signatures_survive_error_and_lock_wrapper(api):
    import inspect
    assert list(inspect.signature(api.capture_image).parameters) == ['connection_id','context','revision']
    assert inspect.getfullargspec(api.execute_research).args == ['self','calibration_id']


def test_delete_loaded_research_then_reanalyze_and_save_as_new(api):
    cal=db.save_calibration(Calibration('Scale','USB',10,'1 мкм'))
    state=connect(api)
    api.capture_image(state['connection_id'],'research',state['revision'])
    analyzed=api.execute_research(cal)
    saved=api.save_research(payload(analyzed['revision'],cal))
    assert saved['ok']
    api.load_research(saved['id'])
    deleted=api.delete_research(saved['id'])
    assert deleted['active'] is True
    assert deleted['revision'] == api.get_session_state('research')['revision']
    analyzed=api.execute_research(cal)
    assert analyzed['ok']
    saved_again=api.save_research(payload(analyzed['revision'],cal))
    assert saved_again['ok'],saved_again
    assert len(db.get_contours(saved_again['id'])) == 1


def test_deleted_loaded_calibration_becomes_new_unsaved_record(api):
    state=connect(api,'calibration')
    captured=api.capture_image(state['connection_id'],'calibration',state['revision'])
    data={'name':'Scale','microscope':'USB','coefficient':20,'division_price':'1 мкм','revision':captured['revision']}
    saved=api.save_calibration(data)
    assert saved['ok']
    loaded=api.load_calibration(saved['id'])
    deleted=api.delete_calibration(saved['id'])
    assert not api.save_calibration(dict(data,id=saved['id'],revision=loaded['revision']))['ok']
    assert deleted['active'] is True
    stale=dict(data,id=saved['id'],revision=deleted['revision'])
    assert not api.save_calibration(stale)['ok']
    recreated=api.save_calibration(dict(data,id=0,revision=deleted['revision']))
    assert recreated['ok'],recreated
    assert db.get_calibration(recreated['id']) is not None
