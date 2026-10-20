import pytest
from backend import database as db
from backend.api import Api, _calibration_scale
from backend.models import Calibration


@pytest.fixture
def api(tmp_path, monkeypatch):
    monkeypatch.setattr(db, 'DB_PATH', tmp_path / 'app.db')
    db.init_db()
    return Api()


def test_analysis_rejects_missing_calibration(api):
    result = api.execute_research(999)
    assert result['ok'] is False
    assert result['error']


@pytest.mark.parametrize('label,micrometers', [
    ('1 мкм', 1), ('2 мкм', 2), ('5 мкм', 5), ('10 мкм', 10),
    ('20 мкм', 20), ('25 мкм', 25), ('50 мкм', 50), ('100 мкм', 100),
    ('200 мкм', 200), ('500 мкм', 500), ('1 мм (1000 мкм)', 1000),
])
def test_typical_division_prices_are_converted_to_micrometers(label, micrometers):
    scale = _calibration_scale(Calibration('Scale', 'М001', 118, label))
    assert scale == (118, micrometers)


@pytest.mark.parametrize('coefficient,division', [(0,'1 мкм'), (-1,'1 мкм'), (float('inf'),'1 мкм'), (1,''), (1,'garbage'), (1,'3 мкм')])
def test_analysis_rejects_invalid_calibration(api, coefficient, division):
    identifier = db.save_calibration(Calibration('C','M001',coefficient,division))
    result = api.execute_research(identifier)
    assert result['ok'] is False
    assert result['error']
