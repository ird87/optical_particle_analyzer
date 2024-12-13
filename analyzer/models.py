from django.db import models

class Research(models.Model):
    """
    Модель для описания исследования
    """
    id = models.AutoField(primary_key=True)  # Уникальный идентификатор исследования
    description = models.TextField()  # Описание исследования
    date = models.DateTimeField(auto_now_add=True)  # Дата создания
    performed_by = models.CharField(max_length=255)  # Кто выполнил исследование
    device = models.CharField(max_length=255)  # Используемый прибор

    # Средние характеристики
    average_perimeter = models.FloatField()  # Средний периметр
    average_area = models.FloatField()  # Средняя площадь
    average_width = models.FloatField()  # Средняя ширина
    average_length = models.FloatField()  # Средняя длина
    average_dek = models.FloatField()  # Средний диаметр эквивалент круга

    def __str__(self):
        return f"Research {self.id}: {self.description[:50]}"


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
