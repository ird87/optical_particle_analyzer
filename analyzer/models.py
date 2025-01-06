from django.db import models
from enum import Enum


class Calibration(models.Model):
    """
    Модель для описания калибровки
    """
    id = models.AutoField(primary_key=True)  # Уникальный идентификатор калибровки
    name = models.CharField(max_length=255)  # Название калибровки
    microscope = models.CharField(max_length=255)  # Название микроскопа
    coefficient = models.FloatField()  # Коэффициент калибровки

    def __str__(self):
        return f"{self.name} ({self.microscope})"


class Research(models.Model):
    """
    Модель для описания исследования
    """
    id = models.AutoField(primary_key=True)  # Уникальный идентификатор исследования
    name = models.TextField()  # Название исследования
    date = models.DateTimeField(auto_now_add=True)  # Дата создания
    employee = models.CharField(max_length=255)  # Кто выполнил исследование
    microscope = models.CharField(max_length=255)  # Название микроскопа
    calibration = models.ForeignKey(Calibration, on_delete=models.SET_NULL, null=True, blank=True)  # Калибровка

    # Средние характеристики
    average_perimeter = models.FloatField()  # Средний периметр
    average_area = models.FloatField()  # Средняя площадь
    average_width = models.FloatField()  # Средняя ширина
    average_length = models.FloatField()  # Средняя длина
    average_dek = models.FloatField()  # Средний диаметр эквивалент круга

    def __str__(self):
        return f"Research {self.id}: {self.name[:50]}"



class ContourData(models.Model):
    """
    Модель для данных по каждому найденному контуру
    """
    research = models.ForeignKey(Research, on_delete=models.CASCADE, related_name='contours')
    contour_number = models.PositiveIntegerField()  # Номер контура
    perimeter = models.FloatField()  # Периметр
    area = models.FloatField()  # Площадь
    width = models.FloatField()  # Ширина
    length = models.FloatField()  # Длина
    dek = models.FloatField()  # Диаметр эквивалент круга

    def __str__(self):
        return f"Contour {self.contour_number} in Research {self.research.id}"


class MicroscopeType(Enum):
    DEFAULT = "По умолчанию"
    MANUAL = "Ручной"
    AUTOMATIC = "Автоматический"


class Microscope:
    def __init__(self, name, microscope_type):
        self.name = name
        self.type = microscope_type

    def __str__(self):
        return f"{self.name} ({self.type.value})"

    def to_dict(self):
        return {
            "name": self.name,
            "type": self.type.name,        # Оригинальное значение (DEFAULT, MANUAL, AUTOMATIC)
            "type_localized": self.type.value,  # Локализованное значение ("По умолчанию", "Ручной", "Автоматический")
        }


MICROSCOPES = [
    Microscope("По умолчанию", MicroscopeType.DEFAULT),
    Microscope("М001", MicroscopeType.MANUAL),
    Microscope("М002", MicroscopeType.AUTOMATIC),
]