from django.urls import path, get_resolver
from . import views

from django.urls import path
from .views import home, upload_image, delete_image, process_images_analyze_all

urlpatterns = [
    path('', home, name='home'),
    path('upload_image/', upload_image, name='upload_image'),
    path('delete_image/', delete_image, name='delete_image'),
    path('api/researches/', views.research_list, name='research_list'),
    path('api/researches/<int:pk>/', views.get_research, name='get_research'),
    path('api/researches/<int:pk>/load/', views.load_research, name='load_research'),
    path('api/researches/<int:pk>/delete/', views.delete_research, name='delete_research'),
    path('api/researches/save/', views.save_research, name='save_research'),
    path('process_images/analyze_all/', process_images_analyze_all, name='process_images_analyze_all'),
]

