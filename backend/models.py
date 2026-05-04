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
    DivisionPrice("10 мкм", 10),
]
