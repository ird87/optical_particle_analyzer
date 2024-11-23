from django.urls import path, get_resolver
from . import views

urlpatterns = [
    path('', views.home, name='home'),
    path('upload_image/', views.upload_image, name='upload_image'),
    path('process_contrast/', views.process_contrast, name='process_contrast'),
    path('process_contour/', views.process_contour, name='process_contour'),
    path('process_analyze/', views.process_analyze, name='process_analyze'),

]
