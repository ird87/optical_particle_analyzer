import pytest

import backend.database as database
from backend.models import Calibration, ContourData, Research


@pytest.fixture(autouse=True)
def isolated_db(tmp_path, monkeypatch):
    """Каждый тест получает свежую пустую БД во временной папке."""
    monkeypatch.setattr(database, 'DB_PATH', tmp_path / 'test.db')
    database.init_db()


# ---------------------------------------------------------------------------
# init_db
# ---------------------------------------------------------------------------

def test_init_db():
    # Повторный вызов не должен падать (CREATE TABLE IF NOT EXISTS)
    database.init_db()


# ---------------------------------------------------------------------------
# Calibration
# ---------------------------------------------------------------------------

def test_save_and_get_calibration():
    cal = Calibration(name='Cal1', microscope='M001',
                      coefficient=42.5, division_price='1 мкм')
    cal_id = database.save_calibration(cal)
    assert cal_id > 0

    loaded = database.get_calibration(cal_id)
    assert loaded is not None
    assert loaded.name == 'Cal1'
    assert loaded.microscope == 'M001'
    assert loaded.coefficient == 42.5
    assert loaded.division_price == '1 мкм'


def test_delete_calibration():
    cal = Calibration(name='ToDel', microscope='M001',
                      coefficient=1.0, division_price='1 мкм')
    cal_id = database.save_calibration(cal)
    database.delete_calibration(cal_id)
    assert database.get_calibration(cal_id) is None


# ---------------------------------------------------------------------------
# Research + ContourData
# ---------------------------------------------------------------------------

def _make_research(**kwargs):
    defaults = dict(
        name='Test', employee='User', microscope='M001',
        average_perimeter=1.0, average_area=2.0,
        average_width=3.0, average_length=4.0, average_dek=5.0,
    )
    defaults.update(kwargs)
    return Research(**defaults)


def test_save_and_get_research():
    res_id = database.save_research(_make_research(name='R1'))
    assert res_id > 0

    contours = [
        ContourData(research_id=res_id, contour_number=1,
                    perimeter=10.0, area=20.0, width=5.0, length=8.0, dek=6.0),
        ContourData(research_id=res_id, contour_number=2,
                    perimeter=11.0, area=21.0, width=5.5, length=8.5, dek=6.5),
    ]
    database.save_contours(res_id, contours)

    loaded = database.get_research(res_id)
    assert loaded is not None
    assert loaded.name == 'R1'
    assert loaded.average_dek == 5.0

    loaded_contours = database.get_contours(res_id)
    assert len(loaded_contours) == 2
    assert loaded_contours[0].perimeter == 10.0
    assert loaded_contours[1].contour_number == 2


def test_delete_research_cascades_contours():
    res_id = database.save_research(_make_research(name='Cascade'))
    database.save_contours(res_id, [
        ContourData(research_id=res_id, contour_number=1,
                    perimeter=1.0, area=1.0, width=1.0, length=1.0, dek=1.0),
    ])

    database.delete_research(res_id)

    assert database.get_research(res_id) is None
    assert database.get_contours(res_id) == []
