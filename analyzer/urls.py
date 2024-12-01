from django.urls import path, get_resolver
from . import views

urlpatterns = [
    path('', views.home, name='home'),
    path('upload_image/', views.upload_image, name='upload_image'),
    path('delete_image/', views.delete_image, name='delete_image'),
    path('list_images/', views.list_images, name='list_images'),
    path('process_images/<str:action>/', views.process_images, name='process_images'),
]
