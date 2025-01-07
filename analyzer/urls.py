from django.urls import path, get_resolver
from . import views

from django.urls import path
from .views import home, upload_image, delete_image, research_list, get_research, load_research, delete_research, save_research, execute_research, calibration_list, \
    get_calibration, load_calibration, delete_calibration, save_calibration, execute_calibration

urlpatterns = [
    # Главная страница
    path('', home, name='home'),

    # Работа с изображениями
    path('upload_image/', upload_image, name='upload_image'),
    path('delete_image/', delete_image, name='delete_image'),

    # Работа с исследованиями
    path('api/researches/', research_list, name='research_list'),
    path('api/researches/<int:pk>/', get_research, name='get_research'),
    path('api/researches/<int:pk>/load/', load_research, name='load_research'),
    path('api/researches/<int:pk>/delete/', delete_research, name='delete_research'),
    path('api/researches/save/', save_research, name='save_research'),
    path('api/researches/execute/', execute_research, name='research_execute'),  # Переименованный маршрут

    # Работа с калибровкой
    path('api/calibrations/', calibration_list, name='calibration_list'),
    path('api/calibrations/<int:pk>/', get_calibration, name='get_calibration'),
    path('api/calibrations/<int:pk>/load/', load_calibration, name='load_calibration'),
    path('api/calibrations/<int:pk>/delete/', delete_calibration, name='delete_calibration'),
    path('api/calibrations/save/', save_calibration, name='save_calibration'),
    path('api/calibrations/execute/', execute_calibration, name='calibration_execute'),
]

