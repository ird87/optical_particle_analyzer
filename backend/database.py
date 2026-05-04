import sqlite3
from contextlib import contextmanager
from datetime import datetime
from typing import Optional

from backend.logger import logger, ROOT_DIR
from backend.models import Calibration, ContourData, Research

DB_PATH = ROOT_DIR / 'data' / 'app.db'


@contextmanager
def _connect():
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute('PRAGMA foreign_keys = ON')
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def init_db() -> None:
    with _connect() as conn:
        conn.executescript("""
            CREATE TABLE IF NOT EXISTS calibration (
                id            INTEGER PRIMARY KEY AUTOINCREMENT,
                name          TEXT    NOT NULL,
                microscope    TEXT    NOT NULL,
                coefficient   REAL    NOT NULL,
                division_price TEXT   NOT NULL,
                date          TEXT    NOT NULL
            );

            CREATE TABLE IF NOT EXISTS research (
                id                 INTEGER PRIMARY KEY AUTOINCREMENT,
                name               TEXT NOT NULL,
                employee           TEXT NOT NULL,
                microscope         TEXT NOT NULL,
                calibration_id     INTEGER REFERENCES calibration(id) ON DELETE SET NULL,
                average_perimeter  REAL NOT NULL,
                average_area       REAL NOT NULL,
                average_width      REAL NOT NULL,
                average_length     REAL NOT NULL,
                average_dek        REAL NOT NULL,
                date               TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS contour_data (
                id             INTEGER PRIMARY KEY AUTOINCREMENT,
                research_id    INTEGER NOT NULL REFERENCES research(id) ON DELETE CASCADE,
                contour_number INTEGER NOT NULL,
                perimeter      REAL    NOT NULL,
                area           REAL    NOT NULL,
                width          REAL    NOT NULL,
                length         REAL    NOT NULL,
                dek            REAL    NOT NULL
            );
        """)
    logger.info('БД инициализирована')


# ---------------------------------------------------------------------------
# Calibration
# ---------------------------------------------------------------------------

def _row_to_calibration(row: sqlite3.Row) -> Calibration:
    return Calibration(
        id=row['id'],
        name=row['name'],
        microscope=row['microscope'],
        coefficient=row['coefficient'],
        division_price=row['division_price'],
        date=datetime.fromisoformat(row['date']),
    )


def get_all_calibrations() -> list[Calibration]:
    with _connect() as conn:
        rows = conn.execute('SELECT * FROM calibration ORDER BY date DESC').fetchall()
    return [_row_to_calibration(r) for r in rows]


def get_calibration(calibration_id: int) -> Optional[Calibration]:
    with _connect() as conn:
        row = conn.execute('SELECT * FROM calibration WHERE id = ?', (calibration_id,)).fetchone()
    return _row_to_calibration(row) if row else None


def save_calibration(cal: Calibration) -> int:
    now = datetime.now().isoformat()
    try:
        with _connect() as conn:
            if cal.id == 0:
                cur = conn.execute(
                    'INSERT INTO calibration (name, microscope, coefficient, division_price, date) '
                    'VALUES (?, ?, ?, ?, ?)',
                    (cal.name, cal.microscope, cal.coefficient, cal.division_price, now),
                )
                return cur.lastrowid
            else:
                conn.execute(
                    'UPDATE calibration SET name=?, microscope=?, coefficient=?, division_price=?, date=? '
                    'WHERE id=?',
                    (cal.name, cal.microscope, cal.coefficient, cal.division_price, now, cal.id),
                )
                return cal.id
    except Exception as e:
        logger.error(f'Ошибка сохранения калибровки: {e}')
        raise


def delete_calibration(calibration_id: int) -> None:
    try:
        with _connect() as conn:
            conn.execute('DELETE FROM calibration WHERE id = ?', (calibration_id,))
    except Exception as e:
        logger.error(f'Ошибка удаления калибровки id={calibration_id}: {e}')
        raise


# ---------------------------------------------------------------------------
# Research
# ---------------------------------------------------------------------------

def _row_to_research(row: sqlite3.Row) -> Research:
    return Research(
        id=row['id'],
        name=row['name'],
        employee=row['employee'],
        microscope=row['microscope'],
        calibration_id=row['calibration_id'],
        average_perimeter=row['average_perimeter'],
        average_area=row['average_area'],
        average_width=row['average_width'],
        average_length=row['average_length'],
        average_dek=row['average_dek'],
        date=datetime.fromisoformat(row['date']),
    )


def get_all_researches() -> list[Research]:
    with _connect() as conn:
        rows = conn.execute('SELECT * FROM research ORDER BY date DESC').fetchall()
    return [_row_to_research(r) for r in rows]


def get_research(research_id: int) -> Optional[Research]:
    with _connect() as conn:
        row = conn.execute('SELECT * FROM research WHERE id = ?', (research_id,)).fetchone()
    return _row_to_research(row) if row else None


def save_research(research: Research) -> int:
    now = datetime.now().isoformat()
    try:
        with _connect() as conn:
            if research.id == 0:
                cur = conn.execute(
                    'INSERT INTO research '
                    '(name, employee, microscope, calibration_id, '
                    ' average_perimeter, average_area, average_width, average_length, average_dek, date) '
                    'VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)',
                    (research.name, research.employee, research.microscope, research.calibration_id,
                     research.average_perimeter, research.average_area, research.average_width,
                     research.average_length, research.average_dek, now),
                )
                return cur.lastrowid
            else:
                conn.execute(
                    'UPDATE research SET name=?, employee=?, microscope=?, calibration_id=?, '
                    'average_perimeter=?, average_area=?, average_width=?, average_length=?, average_dek=?, date=? '
                    'WHERE id=?',
                    (research.name, research.employee, research.microscope, research.calibration_id,
                     research.average_perimeter, research.average_area, research.average_width,
                     research.average_length, research.average_dek, now, research.id),
                )
                return research.id
    except Exception as e:
        logger.error(f'Ошибка сохранения исследования: {e}')
        raise


def delete_research(research_id: int) -> None:
    try:
        with _connect() as conn:
            conn.execute('DELETE FROM research WHERE id = ?', (research_id,))
    except Exception as e:
        logger.error(f'Ошибка удаления исследования id={research_id}: {e}')
        raise


# ---------------------------------------------------------------------------
# ContourData
# ---------------------------------------------------------------------------

def get_contours(research_id: int) -> list[ContourData]:
    with _connect() as conn:
        rows = conn.execute(
            'SELECT * FROM contour_data WHERE research_id = ? ORDER BY contour_number',
            (research_id,),
        ).fetchall()
    return [
        ContourData(
            research_id=r['research_id'],
            contour_number=r['contour_number'],
            perimeter=r['perimeter'],
            area=r['area'],
            width=r['width'],
            length=r['length'],
            dek=r['dek'],
        )
        for r in rows
    ]


def save_contours(research_id: int, contours: list[ContourData]) -> None:
    try:
        with _connect() as conn:
            conn.execute('DELETE FROM contour_data WHERE research_id = ?', (research_id,))
            conn.executemany(
                'INSERT INTO contour_data '
                '(research_id, contour_number, perimeter, area, width, length, dek) '
                'VALUES (?, ?, ?, ?, ?, ?, ?)',
                [(research_id, c.contour_number, c.perimeter, c.area, c.width, c.length, c.dek)
                 for c in contours],
            )
    except Exception as e:
        logger.error(f'Ошибка сохранения контуров для исследования id={research_id}: {e}')
        raise


def delete_contours(research_id: int) -> None:
    try:
        with _connect() as conn:
            conn.execute('DELETE FROM contour_data WHERE research_id = ?', (research_id,))
    except Exception as e:
        logger.error(f'Ошибка удаления контуров для исследования id={research_id}: {e}')
        raise
