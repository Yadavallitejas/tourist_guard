# accounts/admin.py
from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from .models import CustomUser, TouristProfile, EmergencyContact, PoliceProfile

@admin.register(CustomUser)
class CustomUserAdmin(UserAdmin):
    fieldsets = UserAdmin.fieldsets + (
        ('Role', {'fields': ('role',)}),
    )

admin.site.register(TouristProfile)
admin.site.register(EmergencyContact)
admin.site.register(PoliceProfile)
