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
    path('api/sos/', views.api_sos, name='api_sos'),
    path('police/api/active_sos/', views.api_active_sos, name='api_active_sos'),  # we'll add view below
    path('police/fir/<int:sos_id>/pdf/', views.generate_fir_pdf, name='generate_fir_pdf'),

]
