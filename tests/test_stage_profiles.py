import copy
import numpy as np
import cv2
import pytest
from backend.stage_profiles import ProfileStore, profile_point
from backend.analyzer import calibrate_scale_image


def profile():
    return {'id':'example','name':'Оптика','microscope':'М002','binding':{'machine_id':'simulator','camera_index':0,'settings':{}},
            'points':[{'z':100,'width':320,'height':200,'coefficient':40.0,'division_um':10.0,'calibration_id':1,'image':'100.jpg'}]}


def test_pure_scale_detection():
    image=np.full((200,320,3),255,np.uint8)
    for x in range(40,281,40): cv2.line(image,(x,30),(x,170),(0,0,0),3)
    result, outputs=calibrate_scale_image(image)
    assert result['coefficient']==pytest.approx(40,abs=1)
    assert result['marks_count']>=4
    assert set(outputs)=={'contrasted','contours','calibrated'}


def test_profile_atomic_validation_and_exact_lookup(tmp_path):
    store=ProfileStore(tmp_path)
    p=profile();store.save(p)
    loaded=store.load('example');p['points'][0]['coefficient']=999
    assert loaded['points'][0]['coefficient']==40
    assert profile_point(loaded,100,[320,200],loaded['binding'])['division_um']==10
    for z,dimensions,binding in [(101,[320,200],loaded['binding']),(100,[640,400],loaded['binding']),(100,[320,200],{})]:
        with pytest.raises(ValueError):profile_point(loaded,z,dimensions,binding)
    invalid=copy.deepcopy(loaded);invalid['points'].append(copy.deepcopy(invalid['points'][0]))
    with pytest.raises(ValueError):store.save(invalid)
    assert store.load('example')==loaded
    assert len(store.list('М002'))==1
    assert store.list('other')==[]


@pytest.mark.parametrize('bad',[[],[{'z':0}],None])
def test_incomplete_profile_rejected(tmp_path,bad):
    p=profile();p['points']=bad
    with pytest.raises(ValueError):ProfileStore(tmp_path).save(p)
