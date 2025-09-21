# accounts/urls.py
from django.urls import path
from . import views

urlpatterns = [
    path('register/tourist/', views.register_tourist, name='register_tourist'),
    path('register/police/', views.register_police, name='register_police'),
    path('login/', views.login_view, name='login'),
    path('logout/', views.logout_view, name='logout'),
    path('home/tourist/', views.tourist_home, name='tourist_home'),
    path('home/police/', views.police_home, name='police_home'),
    path('api/location/', views.api_location, name='api_location'),
    path('api/location/update/', views.update_location, name='update_location'),
    path('api/zones/', views.get_zones, name='get_zones'),
    path('api/sos/', views.api_sos, name='api_sos'),
    path('police/api/active_sos/', views.api_active_sos, name='api_active_sos'),  # we'll add view below
    path('police/fir/<int:sos_id>/pdf/', views.generate_fir_pdf, name='generate_fir_pdf'),
    path('api/sos/<int:sos_id>/upload_audio/', views.upload_sos_audio, name='upload_sos_audio'),
    path("dangerzones/", views.dangerzone_list, name="dangerzone_list"),
    path("dangerzones/add/", views.dangerzone_create, name="dangerzone_create"),
    path("dangerzones/<int:pk>/edit/", views.dangerzone_edit, name="dangerzone_edit"),
    path("dangerzones/<int:pk>/delete/", views.dangerzone_delete, name="dangerzone_delete"),


]
