import pytest
from backend import database as db
from backend.api import Api
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


@pytest.mark.parametrize('coefficient,division', [(0,'1 мкм'), (-1,'1 мкм'), (float('inf'),'1 мкм'), (1,''), (1,'garbage'), (1,'3 мкм')])
def test_analysis_rejects_invalid_calibration(api, coefficient, division):
    identifier = db.save_calibration(Calibration('C','M001',coefficient,division))
    result = api.execute_research(identifier)
    assert result['ok'] is False
    assert result['error']
