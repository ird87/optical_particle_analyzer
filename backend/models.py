from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Optional


@dataclass
class Calibration:
    name: str
    microscope: str
    coefficient: float
    division_price: str
    id: int = 0
    date: datetime = field(default_factory=datetime.now)


@dataclass
class Research:
    name: str
    employee: str
    microscope: str
    average_perimeter: float
    average_area: float
    average_width: float
    average_length: float
    average_dek: float
    id: int = 0
    calibration_id: Optional[int] = None
    date: datetime = field(default_factory=datetime.now)


@dataclass
class ContourData:
    research_id: int
    contour_number: int
    perimeter: float
    area: float
    width: float
    length: float
    dek: float


# --- Статические справочники ---

class MicroscopeType(Enum):
    DEFAULT = "По умолчанию"
    MANUAL = "Ручной"
    AUTOMATIC = "Автоматический"


@dataclass
class Microscope:
    name: str
    type: MicroscopeType

    def to_dict(self) -> dict:
        return {
            "name": self.name,
            "type": self.type.name,
            "type_localized": self.type.value,
        }


@dataclass
class DivisionPrice:
    name: str
    value: float

    def to_dict(self) -> dict:
        return {"name": self.name, "value": self.value}


MICROSCOPES: list[Microscope] = [
    Microscope("По умолчанию", MicroscopeType.DEFAULT),
    Microscope("М001", MicroscopeType.MANUAL),
    Microscope("М002", MicroscopeType.AUTOMATIC),
]

DIVISION_PRICES: list[DivisionPrice] = [
    DivisionPrice("1 мкм", 1),
    DivisionPrice("2 мкм", 2),
    DivisionPrice("5 мкм", 5),
    DivisionPrice("10 мкм", 10),
    DivisionPrice("20 мкм", 20),
    DivisionPrice("25 мкм", 25),
    DivisionPrice("50 мкм", 50),
    DivisionPrice("100 мкм", 100),
    DivisionPrice("200 мкм", 200),
    DivisionPrice("500 мкм", 500),
    DivisionPrice("1 мм (1000 мкм)", 1000),
]
