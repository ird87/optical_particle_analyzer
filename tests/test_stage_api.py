import time
import threading
import pytest
from test_capture_api import api
from backend import storage


def wait(api, timeout=5):
    end=time.monotonic()+timeout
    while time.monotonic()<end:
        result=api.get_stage_state('М002')
        assert result['ok'],result
        job=result['job']
        if not job.get('active'):return job
        time.sleep(.01)
    raise AssertionError('job timed out')


def setup_stage(api):
    assert api.save_stage_settings('М002',{'mode':'simulator','settle_ms':0})['ok']
    assert api.start_stage_job('М002','connect',{})['ok']
    assert wait(api)['status']=='done'
    assert api.start_stage_job('М002','home',{})['ok']
    assert wait(api)['status']=='done'


def make_profile(api):
    assert api.start_stage_job('М002','profile',{'name':'Тест Z','positions':[100,200],'division_price':'10 мкм'})['ok']
    job=wait(api)
    assert job['status']=='done',job
    return job['result']['profile']


def test_full_simulated_acquisition_and_save_reload(api):
    setup_stage(api);p=make_profile(api)
    scan={'profile_id':p['id'],'z':100,'columns':2,'rows':1,'x':0,'y':0,'dx':1000,'dy':1000}
    assert api.start_stage_job('М002','scan',scan)['ok']
    job=wait(api);assert job['status']=='done',job
    assert len(storage.list_session_images('research'))==2
    point=p['points'][0]
    analysis=api.execute_research(point['calibration_id'])
    assert analysis['ok'],analysis
    saved=api.save_research({'id':0,'revision':analysis['revision'],'name':'Auto','employee':'Engineer','microscope':'М002','calibration_id':point['calibration_id']})
    assert saved['ok'],saved
    assert api.new_research()['ok']
    loaded=api.load_research(saved['id']);assert loaded['ok'],loaded
    acq=loaded['research']['acquisition']
    assert len(acq['frames'])==2
    assert acq['frames'][1]['xyz']==[1000,0,100]
    assert acq['scale']['coefficient']==point['coefficient']
    assert not api.execute_research(p['points'][1]['calibration_id'])['ok']
    assert not api.upload_image('extra.jpg','bad','research')['ok']


def test_stop_responsive_blocks_session_changes_and_keeps_frames(api):
    setup_stage(api);p=make_profile(api)
    api.stage._device.motion_delay=1
    assert api.start_stage_job('М002','scan',{'profile_id':p['id'],'z':100,'columns':2,'rows':1,'x':0,'y':0,'dx':1000,'dy':1000})['ok']
    assert not api.new_research()['ok']
    assert not api.connect_microscope('М002','research')['ok']
    start=time.monotonic();assert api.stop_stage()['ok'];assert time.monotonic()-start<.5
    assert wait(api)['status']=='cancelled'
    assert not api.stage.snapshot()['homed']
    assert not storage.list_session_images('research')


def test_profile_failure_never_activates_partial_and_camera_released(api,monkeypatch):
    setup_stage(api)
    import backend.stage_api as module
    def fail(*args):raise ValueError('no scale')
    monkeypatch.setattr(module,'calibrate_scale_image',fail)
    assert api.start_stage_job('М002','profile',{'name':'bad','positions':[100,200],'division_price':'10 мкм'})['ok']
    assert wait(api)['status']=='error'
    assert api.get_stage_state('М002')['profiles']==[]
    assert not api.stage.snapshot()['homed']


def test_scan_rejects_non_calibrated_z_and_manual_sources(api):
    setup_stage(api);p=make_profile(api)
    assert not api.start_stage_job('М002','scan',{'profile_id':p['id'],'z':150,'columns':1,'rows':1,'x':0,'y':0,'dx':100,'dy':100})['ok']
    (storage.SESSION_RES_DIR/'sources'/'old.jpg').write_bytes(b'old')
    assert not api.start_stage_job('М002','scan',{'profile_id':p['id'],'z':100,'columns':1,'rows':1,'x':0,'y':0,'dx':100,'dy':100})['ok']


def test_resolution_change_keeps_completed_frames_without_measuring_mixed_scale(api,monkeypatch):
    setup_stage(api);p=make_profile(api)
    original=api._job_frame;count=[0]
    def frame(*args):
        result=original(*args);count[0]+=1
        return result if count[0]==1 else result[:200,:200]
    monkeypatch.setattr(api,'_job_frame',frame)
    assert api.start_stage_job('М002','scan',{'profile_id':p['id'],'z':100,'columns':2,'rows':1,'x':0,'y':0,'dx':1000,'dy':1000})['ok']
    job=wait(api);assert job['status']=='error'
    assert job['completed']==1
    assert storage.list_session_images('research')==['1.jpg']
    assert len(api._acquisition['frames'])==1
    assert not api.stage.snapshot()['homed']
    assert api.execute_research(p['points'][0]['calibration_id'])['ok']


def test_stop_preserves_completed_frames(api,monkeypatch):
    setup_stage(api);p=make_profile(api)
    original=api._job_frame
    def frame(*args):
        result=original(*args)
        api.stage._device.motion_delay=1
        return result
    monkeypatch.setattr(api,'_job_frame',frame)
    assert api.start_stage_job('М002','scan',{'profile_id':p['id'],'z':100,'columns':3,'rows':1,'x':0,'y':0,'dx':1000,'dy':1000})['ok']
    deadline=time.monotonic()+2
    while api.jobs.snapshot()['completed']<1 and time.monotonic()<deadline:time.sleep(.005)
    assert api.jobs.snapshot()['completed']==1
    assert api.stop_stage()['ok']
    assert wait(api)['status']=='cancelled'
    assert storage.list_session_images('research')==['1.jpg']
    assert api._acquisition['frames'][0]['xyz']==[0,0,100]


def test_camera_owned_by_worker_is_closed_on_failure(api,monkeypatch):
    setup_stage(api);p=make_profile(api)
    closed=[]
    class BrokenCamera:
        def close(self):closed.append(True)
    monkeypatch.setattr(api,'_job_camera',lambda name:(BrokenCamera(),'token'))
    def fail(*args):raise OSError('camera unplugged')
    monkeypatch.setattr(api,'_job_frame',fail)
    assert api.start_stage_job('М002','scan',{'profile_id':p['id'],'z':100,'columns':1,'rows':1,'x':0,'y':0,'dx':1000,'dy':1000})['ok']
    assert wait(api)['status']=='error'
    assert closed==[True]
    assert not storage.list_session_images('research')
    assert not api.stage.snapshot()['homed']


def test_saved_research_contains_independent_scale_photo(api):
    setup_stage(api);p=make_profile(api)
    assert api.start_stage_job('М002','scan',{'profile_id':p['id'],'z':100,'columns':1,'rows':1,'x':0,'y':0,'dx':100,'dy':100})['ok']
    assert wait(api)['status']=='done'
    result=api.execute_research(p['points'][0]['calibration_id']);assert result['ok']
    saved=api.save_research({'id':0,'revision':result['revision'],'name':'scale snapshot','employee':'test','microscope':'М002','calibration_id':p['points'][0]['calibration_id']});assert saved['ok']
    photo=storage.RESEARCH_DIR/str(saved['id'])/'scale.jpg'
    assert photo.exists()
    original=photo.read_bytes()
    import shutil
    shutil.rmtree(api.profiles.root)
    assert api.new_research()['ok']
    assert not (storage.SESSION_RES_DIR/'scale.jpg').exists()
    assert api.load_research(saved['id'])['ok']
    assert (storage.SESSION_RES_DIR/'scale.jpg').read_bytes()==original
